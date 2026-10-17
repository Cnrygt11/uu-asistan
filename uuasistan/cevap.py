"""Cevap üretimi: soru -> arama (turkish-e5-large + modernbert-tr-reranker) -> dil modeli.

Arama ve dil modeli `Asistan`'a fonksiyon olarak verilir; böylece mantık GPU olmadan
sahte fonksiyonlarla test edilebilir. Gerçek modeller `gercek_asistan()` ile kurulur.
"""
import datetime as dt
import json
import re

from . import DATA

YOGUN_MODEL = "turkish-e5-large"
YENIDEN_SIRALAYICI = "modernbert-tr-reranker"
DIL_MODELI = "Qwen/Qwen3-8B"
ADAY_SAYISI = 30  # yoğun aramadan yeniden sıralamaya giden aday
PARCA_SAYISI = 8  # dil modeline verilen parça (Adım 2: recall@10 = 0.941)

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def egitim_yili(gun: dt.date) -> str:
    """Eğitim-öğretim yılı Eylül'de başlar."""
    y = gun.year if gun.month >= 9 else gun.year - 1
    return f"{y}-{y + 1}"


def sistem_istemi(gun: dt.date) -> str:
    return f"""Sen Bursa Uludağ Üniversitesi önlisans ve lisans öğrencilerine eğitim-öğretim mevzuatı hakkında yardım eden bir asistansın.

Bugün {gun.day} {AYLAR[gun.month - 1]} {gun.year}; {egitim_yili(gun)} eğitim-öğretim yılındayız.

Kurallar:
1. Yalnızca KAYNAKLAR bölümündeki maddelere dayan. Kaynaklarda olmayan bir bilgiyi, sayıyı, tarihi ya da tutarı asla uydurma. Cevap kaynaklarda yoksa bunu açıkça söyle ve öğrenciyi doğru birime (Öğrenci İşleri, bölüm başkanlığı, ilgili yüksekokul) yönlendir.
2. Kullandığın her kural için kaynağını belge adı ve madde numarasıyla göster, örneğin (Belge adı, Madde N).
3. Öğrenciye "sen" diye hitap et. Kısa, net ve samimi yaz.
4. Cevap öğrencinin durumuna göre değişiyorsa ve öğrenci bu bilgiyi vermediyse, cevap vermeden önce yalnızca o bilgiyi sor. Örnekler: kural fakülteye göre farklıysa fakültesini; kural kayıt tarihine göre farklıysa (üniversiteye ya da bir programa) ne zaman kaydolduğunu sor. Bilgi zaten verilmişse tekrar sorma.
5. Öğrenci hakkında yalnızca öğrencinin kendi söylediklerini bilirsin; bu bilgiye dayanırken bunu belirt ("2023'te kayıt olduğunu söylediğin için..."). Öğrenci kayıtlarına erişimin yok.
6. Bir kaynak eski olabilir ya da güncelliği şüpheliyse bunu belirt.
7. Kaynaklarda geçen "Önlisans ve Lisans Öğretim Yönetmeliği" ifadesi, bugün yürürlükte olan Önlisans ve Lisans Eğitim Öğretim Yönetmeliği anlamına gelir.
8. Lisansüstü (yüksek lisans, doktora) konularında bilgin yok; öğrenciyi ilgili enstitüye yönlendir.
9. Öğrenci hangi dilde sorduysa o dilde cevap ver."""


def kaynak_metni(parcalar: list) -> str:
    bloklar = []
    for n, p in enumerate(parcalar, 1):
        ek = []
        if p.get("guncellik"):
            ek.append(f"güncellik: {p['guncellik']}")
        if p.get("kayit_yili_en_gec"):
            ek.append(f"yalnızca {p['kayit_yili_en_gec']} ve öncesinde kayıt olanlara uygulanır")
        baslik = f"[{n}] {p['belge_adi']}, Madde {p['madde']}" + (f" ({p['baslik']})" if p["baslik"] else "")
        bloklar.append(baslik + (f" [{'; '.join(ek)}]" if ek else "") + "\n" + p["metin"])
    return "KAYNAKLAR:\n\n" + "\n\n".join(bloklar)


def mesajlar(diyalog: list, parcalar: list, gun: dt.date) -> list:
    """diyalog: [{"rol": "ogrenci"|"asistan", "metin": ...}]; kaynaklar son öğrenci mesajına eklenir."""
    sonuc = [{"role": "system", "content": sistem_istemi(gun)}]
    for i, m in enumerate(diyalog):
        icerik = m["metin"]
        if i == len(diyalog) - 1:
            icerik = f"{kaynak_metni(parcalar)}\n\nSORU:\n{icerik}"
        sonuc.append({"role": "user" if m["rol"] == "ogrenci" else "assistant", "content": icerik})
    return sonuc


class Asistan:
    def __init__(self, parcalar: list, getir, uret, gun: dt.date | None = None):
        """getir(sorgu) -> parça indeksleri (en alakalı önce); uret(mesajlar) -> metin."""
        self.parcalar = parcalar
        self.getir = getir
        self.uret = uret
        self.gun = gun or dt.date.today()

    def cevapla(self, diyalog: list) -> tuple:
        """(cevap, kullanılan parçalar). Arama sorgusu öğrencinin bütün mesajlarından oluşur."""
        sorgu = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
        secilen = [self.parcalar[i] for i in self.getir(sorgu)[:PARCA_SAYISI]]
        return self.uret(mesajlar(diyalog, secilen, self.gun)), secilen


def atif_yapilan_maddeler(cevap: str) -> set:
    """Cevapta geçen madde numaraları ("Madde 18", "m.18", "Geçici Madde 4")."""
    sonuc = {f"Geçici {n}" for n in re.findall(r"(?i)geçici\s+madde\s+(\d+)", cevap)}
    temiz = re.sub(r"(?i)geçici\s+madde\s+\d+", " ", cevap)
    sonuc |= set(re.findall(r"(?i)\b(?:madde|m\.)\s*(\d+)", temiz))
    return sonuc


def gercek_asistan(cihaz: str = "cuda") -> Asistan:
    """Colab'da (GPU) gerçek modellerle asistanı kurar."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from .arama import YENIDEN_SIRALAYICILAR, YOGUN_MODELLER, Yogun, YenidenSiralayici

    parcalar = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    metinler = [p["arama_metni"] for p in parcalar]
    yogun = Yogun(metinler, YOGUN_MODELLER[YOGUN_MODEL], cihaz=cihaz)
    ys = YenidenSiralayici(YENIDEN_SIRALAYICILAR[YENIDEN_SIRALAYICI], cihaz=cihaz)

    def getir(sorgu: str) -> list:
        adaylar = yogun.ara_toplu([sorgu], ADAY_SAYISI)[0]
        return ys.sirala(sorgu, adaylar, metinler)

    tok = AutoTokenizer.from_pretrained(DIL_MODELI)
    model = AutoModelForCausalLM.from_pretrained(DIL_MODELI, torch_dtype="auto").to(cihaz).eval()

    def uret(msj: list) -> str:
        # Model kartındaki kullanım: şablon önce metne, sonra token'a. Düşünme modu kapalı.
        metin = tok.apply_chat_template(msj, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        girdi = tok([metin], return_tensors="pt").to(cihaz)
        # Model kartı açgözlü çözümlemeyi yasaklıyor (tekrar döngüsü); düşünmesiz mod önerisi.
        # Tekrarlanabilirlik için her üretimde sabit tohum.
        torch.manual_seed(0)
        with torch.no_grad():
            cikti = model.generate(**girdi, max_new_tokens=600, do_sample=True, temperature=0.7, top_p=0.8, top_k=20, min_p=0.0)
        return tok.decode(cikti[0, girdi["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    return Asistan(parcalar, getir, uret)
