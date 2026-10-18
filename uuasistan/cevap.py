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

# Netleştirme ayrı bir adımda kararlaştırılır: istemdeki "önce sor" kuralına model iki koşuda da hiç uymadı (0/6).
# Karar kısıtlı JSON çıktısıyla verilir (önce kısa gerekçe, sonra karar); soru metni sabittir.
# İlk deneme (gerekçesiz, 8 parça) neredeyse her soruda soru sordu, fakültesini söyleyen öğrenciye bile.
NETLESTIRME_SORULARI = {
    "fakulte": "Bu konudaki kural fakülteye ya da yüksekokula göre değişiyor. Hangi fakültede ya da yüksekokulda okuyorsun?",
    "kayit_tarihi": "Bu konudaki kural kayıt tarihine göre değişiyor. Üniversiteye ya da ilgili programa (çift anadal, yan dal gibi) ne zaman kaydoldun?",
}
KARARLAR = ("yok", *NETLESTIRME_SORULARI)
KARAR_PARCA_SAYISI = 3  # karar yalnızca en alakalı parçalara bakar; alt sıralardaki ilgisiz istisna listeleri yanıltıyordu
# Öğrenci bilgiyi zaten verdiyse model ne derse desin tekrar sorulmaz.
SOYLENDI = {
    "fakulte": re.compile(r"(?i)fakülte|yüksekokul|\bmyo\b|konservatuvar|iibf|İİBF"),
    "kayit_tarihi": re.compile(r"\b(?:19|20)\d{2}\b"),
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


def karar_istemi() -> str:
    return """Sana bir öğrenci sorusu ve soruyla ilgili yönetmelik maddeleri verilecek. Görevin cevap yazmak değil, yalnızca şunu belirlemek: sorunun doğru cevabı, öğrencinin henüz söylemediği bir bilgiye bağlı mı?

- fakulte: Soruyu cevaplayan kural fakülteye, yüksekokula ya da programa göre farklı sonuç veriyor (kural bazı birimleri ayrıca sayıyor ya da birimlere göre farklı değerler veriyor) ve öğrenci fakültesini, yüksekokulunu ya da programını söylemedi.
- kayit_tarihi: Soruyu cevaplayan kural, öğrencinin üniversiteye ya da bir programa (çift anadal, yan dal gibi) kaydolduğu tarihe göre farklı sonuç veriyor (bir hüküm yalnızca belirli bir tarihten önce ya da sonra kaydolanlara uygulanıyor) ve öğrenci kayıt tarihini söylemedi.
- yok: Cevap öğrencinin durumuna göre değişmiyor, gereken bilgiyi öğrenci zaten verdi ya da soru kaynaklarla ilgili değil.

Yalnızca soruyu cevaplayan kurala bak; kaynaklarda geçen ama soruyla ilgisi olmayan maddeleri dikkate alma. Çoğu soru için doğru karar yok'tur: kural bütün öğrencilere aynı uygulanıyorsa ya da kuraldaki istisna listesi sorulan durumla ilgili değilse yok de. Emin değilsen yok de.

Önce gerekce alanına bir iki cümleyle soruyu hangi kuralın cevapladığını ve bu kuralın sonucunun öğrencinin fakültesine ya da kayıt tarihine göre değişip değişmediğini yaz; sonra karar alanını doldur."""


def karar_mesajlari(diyalog: list, parcalar: list) -> list:
    soru = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
    kaynak = kaynak_metni(parcalar[:KARAR_PARCA_SAYISI])
    return [{"role": "system", "content": karar_istemi()}, {"role": "user", "content": f"{kaynak}\n\nSORU:\n{soru}"}]


def netlestirme_gerekli(karar: str, diyalog: list) -> bool:
    if karar not in NETLESTIRME_SORULARI:
        return False
    ogrenci = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
    return not SOYLENDI[karar].search(ogrenci)


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
    def __init__(self, parcalar: list, getir, uret, gun: dt.date | None = None, karar=None):
        """getir(sorgu) -> parça indeksleri (en alakalı önce); uret(mesajlar) -> (metin, üretilen token sayısı);
        karar(mesajlar) -> (KARARLAR'dan biri, gerekçe) (verilmezse netleştirme adımı atlanır)."""
        self.parcalar = parcalar
        self.getir = getir
        self.uret = uret
        self.karar = karar
        self.gun = gun or dt.date.today()

    def cevapla(self, diyalog: list) -> tuple:
        """(cevap, kullanılan parçalar, ölçüm). Arama sorgusu öğrencinin bütün mesajlarından oluşur."""
        sorgu = " ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")
        t0 = time.perf_counter()
        secilen = [self.parcalar[i] for i in self.getir(sorgu)[:PARCA_SAYISI]]
        t1 = time.perf_counter()
        olcum = {"arama_sn": round(t1 - t0, 3)}
        # Netleştirme yalnızca ilk turda: asistan bir kez sorduysa öğrencinin yanıtıyla cevap verilir.
        if self.karar and not any(m["rol"] == "asistan" for m in diyalog):
            k, gerekce = self.karar(karar_mesajlari(diyalog, secilen))
            simdi = time.perf_counter()
            olcum |= {"karar_sn": round(simdi - t1, 3), "karar": k, "karar_gerekce": gerekce}
            t1 = simdi
            if netlestirme_gerekli(k, diyalog):
                return NETLESTIRME_SORULARI[k], secilen, olcum | {"netlestirme": k}
        cevap, token = self.uret(mesajlar(diyalog, secilen, self.gun))
        t2 = time.perf_counter()
        return cevap, secilen, olcum | {"uretim_sn": round(t2 - t1, 3), "token": token}


def atif_yapilan_maddeler(cevap: str) -> set:
    """Cevapta geçen madde numaraları ("Madde 18", "m.18", "Geçici Madde 4")."""
    sonuc = {f"Geçici {n}" for n in re.findall(r"(?i)geçici\s+madde\s+(\d+)", cevap)}
    temiz = re.sub(r"(?i)geçici\s+madde\s+\d+", " ", cevap)
    sonuc |= set(re.findall(r"(?i)\b(?:madde|m\.)\s*(\d+)", temiz))
    return sonuc


def gercek_asistan(model: str = "qwen3-8b", cihaz: str = "cuda", tohum: int = 0) -> Asistan:
    """Colab'da (GPU) gerçek modellerle asistanı kurar. vLLM önce yüklenir; fp16 arama modelleri kalan belleğe sığar."""
    import torch
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    from .arama import YENIDEN_SIRALAYICILAR, YOGUN_MODELLER, Yogun, YenidenSiralayici

    ad, sablon_ek = DIL_MODELLERI[model]
    # Bellek (L4, 22 GB): ilk denemede vLLM %85'i aldı, fp32 arama modelleri kalan 3 GB'ı doldurdu ve ilk soruda OOM.
    # KV önbelleği sabit 1 GiB (8B'de ~7.000, 30B'de ~10.000 token; istem en fazla ~5.000 token: 8 parça × 1.500 karakter + 600 cevap) ve ön doldurma 2.048'lik
    # parçalarla yapılır (etkinleştirme belleği ~1 GB'tan ~0,25 GB'a); arama modelleri fp16 (~3 GB yerine ~1,5 GB).
    llm = LLM(model=ad, max_model_len=6144, kv_cache_memory_bytes=1 << 30, max_num_batched_tokens=2048, seed=tohum)
    tok = llm.get_tokenizer()
    # İki model kartının önerisi; açgözlü çözümleme uzun metinde tekrar döngüsüne yol açıyor. Sabit tohum: tekrarlanabilirlik.
    ornekleme = SamplingParams(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, max_tokens=600, seed=tohum)
    # Karar bir sınıflandırma: açgözlü; çıktı {"gerekce", "karar"} JSON'u, karar yalnızca KARARLAR'dan biri olabilir.
    sema = {"type": "object", "required": ["gerekce", "karar"],
            "properties": {"gerekce": {"type": "string", "maxLength": 400}, "karar": {"enum": list(KARARLAR)}}}
    karar_ornekleme = SamplingParams(temperature=0.0, max_tokens=200, structured_outputs=StructuredOutputsParams(json=sema))

    parcalar = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    metinler = [p["arama_metni"] for p in parcalar]
    yogun = Yogun(metinler, YOGUN_MODELLER[YOGUN_MODEL], cihaz=cihaz, yarim=True)
    ys = YenidenSiralayici(YENIDEN_SIRALAYICILAR[YENIDEN_SIRALAYICI], cihaz=cihaz, yarim=True)
    torch.cuda.empty_cache()  # fp32 yüklemeden kalan ayrılmış belleği bırak

    def getir(sorgu: str) -> list:
        adaylar = yogun.ara_toplu([sorgu], ADAY_SAYISI)[0]
        return ys.sirala(sorgu, adaylar, metinler)

    def uret(msj: list) -> tuple:
        istem = tok.apply_chat_template(msj, tokenize=False, add_generation_prompt=True, **sablon_ek)
        cikti = llm.generate([istem], ornekleme, use_tqdm=False)[0].outputs[0]
        return cikti.text.strip(), len(cikti.token_ids)

    def karar(msj: list) -> str:
        istem = tok.apply_chat_template(msj, tokenize=False, add_generation_prompt=True, **sablon_ek)
        metin = llm.generate([istem], karar_ornekleme, use_tqdm=False)[0].outputs[0].text
        try:
            j = json.loads(metin)
            return j["karar"], j["gerekce"]
        except (json.JSONDecodeError, KeyError):  # 200 tokende kesilirse
            return "yok", metin

    return Asistan(parcalar, getir, uret, karar=karar)
