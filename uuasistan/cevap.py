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

# Netleştirme: sonucu öğrencinin durumuna göre değişen kurallar data/kosullar.json'da etiketli. Aramanın ilk
# sıradaki parçası etiketliyse ve öğrenci gereken bilgiyi vermediyse cevap üretilmez, sabit soru sorulur.
# Kararı dil modeline bıraktığımız denemeler başarısızdı: istemle 0/6; ayrı karar adımında 1/6 doğru, 12/78 gereksiz soru.
NETLESTIRME_SORULARI = {
    "fakulte": "Bu konudaki kural fakülteye ya da yüksekokula göre değişiyor. Hangi fakültede ya da yüksekokulda okuyorsun?",
    "kayit_yili": "Bu konudaki kural üniversiteye kayıt yılına göre değişiyor. Üniversiteye hangi yıl kaydoldun?",
    "cap_yandal_kayit_tarihi": "Bu konudaki kural çift anadal ya da yan dal programına kayıt tarihine göre değişiyor. Programa hangi dönem kaydoldun?",
}
_YIL = r"\b(?:19|20)\d{2}\b"
# Öğrencinin bilgiyi verdiğini gösteren ifadeler; eşleşirse tekrar sorulmaz.
SOYLENDI = {
    "fakulte": re.compile(r"(?i)fakülte|yüksekokul|\bmyo\b|konservatuvar|iibf|İİBF"),
    "kayit_yili": re.compile(_YIL),
    "cap_yandal_kayit_tarihi": re.compile(_YIL),
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
1. Yalnızca KAYNAKLAR bölümündeki maddelere dayan. Kaynaklarda olmayan bir bilgiyi, sayıyı, tarihi, tutarı, karar ya da birim adını asla uydurma. Cevap kaynaklarda yoksa bunu açıkça söyle ve öğrenciyi doğru birime (Öğrenci İşleri, bölüm başkanlığı, ilgili yüksekokul) yönlendir.
2. Kaynaklarda sorunun cevabını doğrudan veren bir kural cümlesi varsa, cevabına o cümleyi tırnak içinde aynen alıntılayarak başla; ardından parantez içinde belgenin adını ve madde numarasını yaz. Böyle bir cümle yoksa alıntı yapma; soruyla ilgisiz bir cümleyi asla alıntılama. Sonra alıntıyla tutarlı sonucu en fazla üç cümleyle söyle. Toplam en fazla beş cümle; madde işaretli liste, başlık, "Sonuç" bölümü yazma, aynı bilgiyi tekrarlama, daha fazla anlatmayı teklif etme.
3. Kuralı dikkatle oku: "aşağıda sayılanlar hariç" ya da "... dışında" diye başlayan bir kural, listede sayılanlara uygulanmaz, listede olmayanlara uygulanır. Öğrencinin birimi listede mi, ona göre karar ver. Bir hüküm öğrencinin kaydolduğu tarihe göre eski kuralların uygulanacağını söylüyorsa, öğrencinin söylediği tarihi bu hükümle karşılaştır; eski kurallar kaynaklarda yoksa ayrıntı verme, öğrenciyi doğru birime yönlendir.
4. Öğrenciye her zaman "sen" diye hitap et; "siz", "-iniz", "-sınız" gibi ifadeler kullanma. Samimi ve net ol.
5. Cevap öğrencinin durumuna göre değişiyorsa öğrencinin söylediği bilgiyi kullan; söylemediği bir durumu varsayma.
6. Öğrenci hakkında yalnızca öğrencinin kendi söylediklerini bilirsin; bu bilgiye dayanırken bunu belirt ("... olduğunu söylediğin için"). Öğrenci kayıtlarına erişimin yok.
7. Bir kaynak eski olabilir ya da güncelliği şüpheliyse bunu belirt.
8. Kaynaklarda geçen "Önlisans ve Lisans Öğretim Yönetmeliği" ifadesi, bugün yürürlükte olan Önlisans ve Lisans Eğitim Öğretim Yönetmeliği anlamına gelir.
9. Lisansüstü (yüksek lisans, doktora) konularında bilgin yok; öğrenciyi ilgili enstitüye yönlendir.
10. Soru hangi dilde sorulduysa cevabı o dilde yaz: İngilizce soruya İngilizce cevap ver (alıntı Türkçe kalabilir)."""


def kosul_kurallari() -> dict:
    """{(belge, madde, fıkra | None): kural}; fıkra None ise maddenin tamamı etiketlidir."""
    kurallar = json.loads((DATA / "kosullar.json").read_text("utf-8"))["kurallar"]
    return {(k["belge"], k["madde"], k.get("fikra")): k for k in kurallar}


def parca_kurali(parca: dict, kurallar: dict) -> dict | None:
    for f in (None, *parca.get("fikralar", [])):
        if (k := kurallar.get((parca["belge"], parca["madde"], f))) is not None:
            return k
    return None


def netlestirme_konusu(diyalog: list, parca: dict, kurallar: dict) -> str | None:
    """Cevaptan önce sorulması gereken konu; gerek yoksa None."""
    kural = parca_kurali(parca, kurallar)
    if kural is None:
        return None
    asistan = [m["metin"] for m in diyalog if m["rol"] == "asistan"]
    if asistan and asistan[-1] in NETLESTIRME_SORULARI.values():
        return None  # az önce sorduk: öğrencinin yanıtıyla cevap verilir, aynı soru tekrarlanmaz
    ogrenci = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
    return None if SOYLENDI[kural["konu"]].search(ogrenci) else kural["konu"]


def bagli_ekle(secilen: list, parcalar: list, kurallar: dict) -> list:
    """Seçilen kuralları değiştiren hükümleri (geçici maddeler, yürürlük tarihi) sona ekler; arama bunları kaçırabiliyor."""
    kimlik = {p["id"]: p for p in parcalar}
    sonuc = list(secilen)
    for p in secilen:
        for pid in (parca_kurali(p, kurallar) or {}).get("bagli", []):
            if all(q["id"] != pid for q in sonuc):
                sonuc.append(kimlik[pid])
    return sonuc


def kaynak_metni(parcalar: list, kurallar: dict | None = None) -> str:
    bloklar = []
    for n, p in enumerate(parcalar, 1):
        ek = []
        if p.get("guncellik"):
            ek.append(f"güncellik: {p['guncellik']}")
        if p.get("kayit_yili_en_gec"):
            ek.append(f"yalnızca {p['kayit_yili_en_gec']} ve öncesinde kayıt olanlara uygulanır")
        baslik = f"[{n}] {p['belge_adi']}, Madde {p['madde']}" + (f" ({p['baslik']})" if p["baslik"] else "")
        if ek:
            baslik += f" [{'; '.join(ek)}]"
        if kurallar and (k := parca_kurali(p, kurallar)) and k.get("okuma_notu"):
            baslik += f"\n(Okuma notu; yönetmelik metni değildir, alıntılama: {k['okuma_notu']})"
        bloklar.append(baslik + "\n" + p["metin"])
    return "KAYNAKLAR:\n\n" + "\n\n".join(bloklar)


def mesajlar(diyalog: list, parcalar: list, gun: dt.date, kurallar: dict | None = None) -> list:
    """diyalog: [{"rol": "ogrenci"|"asistan", "metin": ...}]; kaynaklar son öğrenci mesajına eklenir."""
    sonuc = [{"role": "system", "content": sistem_istemi(gun)}]
    for i, m in enumerate(diyalog):
        icerik = m["metin"]
        if i == len(diyalog) - 1:
            icerik = f"{kaynak_metni(parcalar, kurallar)}\n\nSORU:\n{icerik}"
        sonuc.append({"role": "user" if m["rol"] == "ogrenci" else "assistant", "content": icerik})
    return sonuc


class Asistan:
    def __init__(self, parcalar: list, getir, uret, gun: dt.date | None = None, kurallar: dict | None = None):
        """getir(sorgu) -> parça indeksleri (en alakalı önce); uret(mesajlar) -> (metin, üretilen token sayısı)."""
        self.parcalar = parcalar
        self.getir = getir
        self.uret = uret
        self.gun = gun or dt.date.today()
        self.kurallar = kosul_kurallari() if kurallar is None else kurallar

    def cevapla(self, diyalog: list) -> tuple:
        """(cevap, kullanılan parçalar, ölçüm). Arama sorgusu öğrencinin bütün mesajlarından oluşur."""
        sorgu = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
        t0 = time.perf_counter()
        secilen = [self.parcalar[i] for i in self.getir(sorgu)[:PARCA_SAYISI]]
        t1 = time.perf_counter()
        olcum = {"arama_sn": round(t1 - t0, 3)}
        if secilen and (konu := netlestirme_konusu(diyalog, secilen[0], self.kurallar)):
            return NETLESTIRME_SORULARI[konu], secilen, olcum | {"netlestirme": konu}
        secilen = bagli_ekle(secilen, self.parcalar, self.kurallar)
        cevap, token = self.uret(mesajlar(diyalog, secilen, self.gun, self.kurallar))
        t2 = time.perf_counter()
        return cevap, secilen, olcum | {"uretim_sn": round(t2 - t1, 3), "token": token}


def atif_yapilan_maddeler(cevap: str) -> set:
    """Cevapta geçen madde numaraları ("Madde 18", "m.18", "Geçici Madde 4")."""
    sonuc = {f"Geçici {n}" for n in re.findall(r"(?i)geçici\s+madde\s+(\d+)", cevap)}
    temiz = re.sub(r"(?i)geçici\s+madde\s+\d+", " ", cevap)
    sonuc |= set(re.findall(r"(?i)\b(?:madde|m\.)\s*(\d+)", temiz))
    return sonuc


def arama_kur(cihaz: str = "cuda") -> tuple:
    """(parcalar, getir): turkish-e5-large ile 30 aday, modernbert-tr-reranker ile sıralama; arama modelleri fp16."""
    import torch

    from .arama import YENIDEN_SIRALAYICILAR, YOGUN_MODELLER, Yogun, YenidenSiralayici

    parcalar = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    metinler = [p["arama_metni"] for p in parcalar]
    yogun = Yogun(metinler, YOGUN_MODELLER[YOGUN_MODEL], cihaz=cihaz, yarim=True)
    ys = YenidenSiralayici(YENIDEN_SIRALAYICILAR[YENIDEN_SIRALAYICI], cihaz=cihaz, yarim=True)
    torch.cuda.empty_cache()  # fp32 yüklemeden kalan ayrılmış belleği bırak

    def getir(sorgu: str) -> list:
        adaylar = yogun.ara_toplu([sorgu], ADAY_SAYISI)[0]
        return ys.sirala(sorgu, adaylar, metinler)

    return parcalar, getir


def gercek_asistan(model: str = "qwen3-8b", cihaz: str = "cuda", tohum: int = 0) -> Asistan:
    """Colab'da (GPU) gerçek modellerle asistanı kurar. vLLM önce yüklenir; fp16 arama modelleri kalan belleğe sığar."""
    from vllm import LLM, SamplingParams

    ad, sablon_ek = DIL_MODELLERI[model]
    # Bellek (L4, 22 GB): ilk denemede vLLM %85'i aldı, fp32 arama modelleri kalan 3 GB'ı doldurdu ve ilk soruda OOM.
    # KV önbelleği sabit 1 GiB (8B'de ~7.000, 30B'de ~10.000 token; istem en fazla ~5.000 token: 8 parça × 1.500 karakter + 600 cevap) ve ön doldurma 2.048'lik
    # parçalarla yapılır (etkinleştirme belleği ~1 GB'tan ~0,25 GB'a); arama modelleri fp16 (~3 GB yerine ~1,5 GB).
    llm = LLM(model=ad, max_model_len=6144, kv_cache_memory_bytes=1 << 30, max_num_batched_tokens=2048, seed=tohum)
    tok = llm.get_tokenizer()
    # İki model kartının önerisi; açgözlü çözümleme uzun metinde tekrar döngüsüne yol açıyor. Sabit tohum: tekrarlanabilirlik.
    ornekleme = SamplingParams(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, max_tokens=600, seed=tohum)
    parcalar, getir = arama_kur(cihaz)

    def uret(msj: list) -> tuple:
        istem = tok.apply_chat_template(msj, tokenize=False, add_generation_prompt=True, **sablon_ek)
        cikti = llm.generate([istem], ornekleme, use_tqdm=False)[0].outputs[0]
        return cikti.text.strip(), len(cikti.token_ids)

    return Asistan(parcalar, getir, uret)
