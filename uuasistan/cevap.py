"""Cevap üretimi: soru -> arama (turkish-e5-large + modernbert-tr-reranker) -> dil modeli (vLLM).

Arama ve dil modeli `Asistan`'a fonksiyon olarak verilir; böylece mantık GPU olmadan
sahte fonksiyonlarla test edilebilir. Gerçek modeller `gercek_asistan()` ile kurulur.
"""
import datetime as dt
import json
import re
import time

from . import DATA

YOGUN_MODEL = "turkish-e5-large"
YENIDEN_SIRALAYICI = "modernbert-tr-reranker"
ADAY_SAYISI = 30  # yoğun aramadan yeniden sıralamaya giden aday
PARCA_SAYISI = 8  # dil modeline verilen parça (Adım 2: recall@10 = 0.941)

# (Hugging Face adı, sohbet şablonuna ek argümanlar). Örnekleme ayarları iki model kartında da aynı.
DIL_MODELLERI = {
    "qwen3-8b": ("Qwen/Qwen3-8B", {"enable_thinking": False}),
    # Qwen3-30B-A3B-Instruct-2507'nin 4-bit (w4a16) hali: 16,7 GB, orijinalin kalitesinin ~%99'u.
    # MoE: token başına ~3B parametre çalışır; L4'te yoğun 8B'den hızlı olması beklenir.
    "qwen3-30b-a3b": ("RedHatAI/Qwen3-30B-A3B-Instruct-2507-quantized.w4a16", {}),
}

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
2. Cevap kaynaklarda varsa, cevabına sorunun cevabını veren kural cümlesini kaynaktan tırnak içinde aynen alıntılayarak başla ve ardından parantez içinde belgenin adını ve madde numarasını yaz. Sonucu ancak bu alıntıdan sonra, alıntıyla tutarlı şekilde söyle.
3. Kısa yaz: alıntı dahil en fazla beş cümle. Kaynaklarda olmayan konularda ek açıklama yapma, daha fazla anlatmayı teklif etme.
4. Öğrenciye "sen" diye hitap et; samimi ve net ol.
5. Cevap öğrencinin durumuna göre değişiyorsa ve öğrenci bu bilgiyi vermediyse, henüz cevap verme; yalnızca o bilgiyi sor. Örnekler: kural fakülteye göre farklıysa fakültesini; kural kayıt tarihine göre farklıysa (üniversiteye ya da bir programa) ne zaman kaydolduğunu sor. Bilgi zaten verilmişse tekrar sorma.
6. Öğrenci hakkında yalnızca öğrencinin kendi söylediklerini bilirsin; bu bilgiye dayanırken bunu belirt ("... olduğunu söylediğin için"). Öğrenci kayıtlarına erişimin yok.
7. Bir kaynak eski olabilir ya da güncelliği şüpheliyse bunu belirt.
8. Kaynaklarda geçen "Önlisans ve Lisans Öğretim Yönetmeliği" ifadesi, bugün yürürlükte olan Önlisans ve Lisans Eğitim Öğretim Yönetmeliği anlamına gelir.
9. Lisansüstü (yüksek lisans, doktora) konularında bilgin yok; öğrenciyi ilgili enstitüye yönlendir.
10. Soru hangi dilde sorulduysa cevabı o dilde yaz: İngilizce soruya İngilizce cevap ver (alıntı Türkçe kalabilir)."""


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
        """getir(sorgu) -> parça indeksleri (en alakalı önce); uret(mesajlar) -> (metin, üretilen token sayısı)."""
        self.parcalar = parcalar
        self.getir = getir
        self.uret = uret
        self.gun = gun or dt.date.today()

    def cevapla(self, diyalog: list) -> tuple:
        """(cevap, kullanılan parçalar, ölçüm). Arama sorgusu öğrencinin bütün mesajlarından oluşur."""
        sorgu = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
        t0 = time.perf_counter()
        secilen = [self.parcalar[i] for i in self.getir(sorgu)[:PARCA_SAYISI]]
        t1 = time.perf_counter()
        cevap, token = self.uret(mesajlar(diyalog, secilen, self.gun))
        t2 = time.perf_counter()
        return cevap, secilen, {"arama_sn": round(t1 - t0, 3), "uretim_sn": round(t2 - t1, 3), "token": token}


def atif_yapilan_maddeler(cevap: str) -> set:
    """Cevapta geçen madde numaraları ("Madde 18", "m.18", "Geçici Madde 4")."""
    sonuc = {f"Geçici {n}" for n in re.findall(r"(?i)geçici\s+madde\s+(\d+)", cevap)}
    temiz = re.sub(r"(?i)geçici\s+madde\s+\d+", " ", cevap)
    sonuc |= set(re.findall(r"(?i)\b(?:madde|m\.)\s*(\d+)", temiz))
    return sonuc


def gercek_asistan(model: str = "qwen3-8b", cihaz: str = "cuda") -> Asistan:
    """Colab'da (GPU) gerçek modellerle asistanı kurar. vLLM önce yüklenir; aramalar kalan belleğe sığar."""
    from vllm import LLM, SamplingParams

    from .arama import YENIDEN_SIRALAYICILAR, YOGUN_MODELLER, Yogun, YenidenSiralayici

    ad, sablon_ek = DIL_MODELLERI[model]
    llm = LLM(model=ad, gpu_memory_utilization=0.85, max_model_len=8192, seed=0)
    tok = llm.get_tokenizer()
    # İki model kartının önerisi; açgözlü çözümleme tekrar döngüsüne yol açıyor. Sabit tohum: tekrarlanabilirlik.
    ornekleme = SamplingParams(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, max_tokens=600, seed=0)

    parcalar = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    metinler = [p["arama_metni"] for p in parcalar]
    yogun = Yogun(metinler, YOGUN_MODELLER[YOGUN_MODEL], cihaz=cihaz)
    ys = YenidenSiralayici(YENIDEN_SIRALAYICILAR[YENIDEN_SIRALAYICI], cihaz=cihaz)

    def getir(sorgu: str) -> list:
        adaylar = yogun.ara_toplu([sorgu], ADAY_SAYISI)[0]
        return ys.sirala(sorgu, adaylar, metinler)

    def uret(msj: list) -> tuple:
        istem = tok.apply_chat_template(msj, tokenize=False, add_generation_prompt=True, **sablon_ek)
        cikti = llm.generate([istem], ornekleme, use_tqdm=False)[0].outputs[0]
        return cikti.text.strip(), len(cikti.token_ids)

    return Asistan(parcalar, getir, uret)
