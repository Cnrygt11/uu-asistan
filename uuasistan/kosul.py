"""Öğrencinin durumuna bağlı kurallar: netleştirme, bağlı hükümler ve koşul notları.

Etiketler data/kosullar.json'da, birim adları data/birimler.json'da. Dil modelinin zorlandığı iki işlem,
bir listede öğrencinin birimini aramak ve kayıt tarihini bir eşikle karşılaştırmak, burada kodla yapılır;
model sonucu kaynağın yanında "koşul notu" olarak görür ve yalnızca açıklar. Öğrencinin ifadesi kesin
çözümlenemiyorsa (ör. Geçici 4 için "2020'de") not eklenmez.
"""
import datetime as dt
import json
import re
from functools import lru_cache

from . import DATA
from .arama import HARF, kucuk

# Kararı dil modeline bıraktığımız denemeler başarısızdı: istemle 0/6; ayrı karar adımında 1/6 doğru, 12/78 gereksiz soru.
NETLESTIRME_SORULARI = {
    "fakulte": "Bu konudaki kural fakülteye ya da yüksekokula göre değişiyor. Hangi fakültede ya da yüksekokulda okuyorsun?",
    "kayit_yili": "Bu konudaki kural üniversiteye kayıt yılına göre değişiyor. Üniversiteye hangi yıl kaydoldun?",
    "cap_yandal_kayit_tarihi": "Bu konudaki kural çift anadal ya da yan dal programına kayıt tarihine göre değişiyor. Programa hangi dönem kaydoldun?",
}
NETLESTIRME_SORULARI_EN = {
    "fakulte": "This rule depends on your faculty or school. Which faculty or school are you in?",
    "kayit_yili": "This rule depends on the year you enrolled at the university. Which year did you enroll?",
    "cap_yandal_kayit_tarihi": "This rule depends on when you enrolled in the double major or minor programme. Which semester did you enroll?",
}
_SORULAR = set(NETLESTIRME_SORULARI.values()) | set(NETLESTIRME_SORULARI_EN.values())

_SOL, _SAG = rf"(?<![{HARF}])", rf"(?![{HARF}])"
BIRIM_SOZCUGU = re.compile(rf"fakülte|yüksekokul|{_SOL}myo{_SAG}|konservatuv?ar")
CAP = re.compile(rf"çift anadal|{_SOL}çap|yan ?dal")
# Bir tarihin kayıt tarihi olduğunu gösteren sözcükler ("Bu yıl harç ne kadar?" bir kayıt tarihi değildir).
KAYIT_IPUCU = re.compile(r"kayıt ol|kaydol|kayıt yaptır|kayıtlı|girdim|girişli|giriş yaptım|başladım|başlamıştım|kazandım|beri")
INGILIZCE = re.compile(r"(?i)\b(?:what|how|can|is|are|do|does|my|the|which|when|i)\b")
TURKCE_HARF = re.compile("[çğıöşüÇĞİÖŞÜ]")


@lru_cache(maxsize=1)
def _kosullar() -> dict:
    return json.loads((DATA / "kosullar.json").read_text("utf-8"))


def kosul_kurallari() -> dict:
    """{(belge, madde, fıkra | None): kural}; fıkra None ise maddenin tamamı etiketlidir."""
    return {(k["belge"], k["madde"], k.get("fikra")): k for k in _kosullar()["kurallar"]}


def gecis_hukumleri() -> list:
    return _kosullar()["gecis_hukumleri"]


@lru_cache(maxsize=1)
def birimler() -> list:
    return json.loads((DATA / "birimler.json").read_text("utf-8"))["birimler"]


def eski_parcalar() -> list:
    """Aramaya girmeyen, yalnızca koşulu sağlayan öğrenciye verilen parçalar (ör. mülga 2014 ÇAP yönergesi)."""
    return [json.loads(s) for s in (DATA / "eski_parcalar.jsonl").read_text("utf-8").splitlines()]


def parca_kurali(parca: dict, kurallar: dict) -> dict | None:
    for f in (None, *parca.get("fikralar", [])):
        if (k := kurallar.get((parca["belge"], parca["madde"], f))) is not None:
            return k
    return None


# --- Öğrencinin söyledikleri ---

def _ogrenci(diyalog: list) -> list:
    return [m["metin"] for m in diyalog if m["rol"] == "ogrenci"]


def _son_asistan(diyalog: list) -> str | None:
    return next((m["metin"] for m in reversed(diyalog) if m["rol"] == "asistan"), None)


def ingilizce_mi(metin: str) -> bool:
    return bool(INGILIZCE.search(metin)) and not TURKCE_HARF.search(metin)


def _birim_deseni(ad: str) -> re.Pattern:
    """Ad, ardından birim sözcüğü, bulunma eki ("tıpta", "iibf'deyim") ya da "öğrencisi/okuyorum" gelirse eşleşir.
    Birim sözcüğüyle biten adlar ("eğitim fakülte") yalnızca o biçimde eşleşir: "uzaktan eğitimde" Eğitim Fakültesi değildir."""
    if BIRIM_SOZCUGU.search(ad):
        return re.compile(rf"{_SOL}{re.escape(ad)}")
    return re.compile(rf"{_SOL}{re.escape(ad)}(?:\s*(?:fakülte|yüksekokul|meslek yüksekokul|myo{_SAG}|konservatuv?ar)"
                      rf"|'?(?:ta|da|te|de)(?:yım|yim|yum|yüm|ki)?{_SAG}|\s+(?:öğrenci|okuyorum|okuyan))")


def birimleri_bul(metin: str, liste: list | None = None) -> list:
    """Metinde adı geçen birimler (aynı birim bir kez)."""
    k = kucuk(metin)
    return [b for b in (liste or birimler()) if any(_birim_deseni(kucuk(a)).search(k) for a in b["adlar"])]


def birim_soylendi(metin: str) -> bool:
    return bool(BIRIM_SOZCUGU.search(kucuk(metin)) or birimleri_bul(metin))


def _aralik_ay(yil: int, mevsim: str | None) -> tuple:
    """Kayıt dönemi: güz kaydı Ağustos-Ekim, bahar kaydı Ocak ortası-Mart ortası (dönem başında yapılır)."""
    if mevsim == "güz":
        return dt.date(yil, 8, 1), dt.date(yil, 10, 31)
    if mevsim == "bahar":
        return dt.date(yil, 1, 15), dt.date(yil, 3, 15)
    return dt.date(yil, 1, 1), dt.date(yil, 12, 31)


def tarih_ifadeleri(metin: str, gun: dt.date) -> list:
    """[(ifade, en erken, en geç)]: öğrencinin söylediği kayıt zamanının olası aralığı."""
    k = kucuk(metin)
    sonuc, kullanilan = [], []

    def ekle(m, bas, son):
        if not any(a <= m.start() < b for a, b in kullanilan):
            kullanilan.append(m.span())
            sonuc.append((m.group(0).strip(), bas, son))

    for m in re.finditer(r"(?<!\d)((?:19|20)\d{2})\s*[-–/]\s*((?:19|20)\d{2})(?!\d)", k):  # akademik yıl
        ekle(m, dt.date(int(m[1]), 8, 1), dt.date(int(m[2]), 3, 31))
    for m in re.finditer(rf"(?<!\d)((?:19|20)\d{{2}})(?!\d)[{HARF}']*(?:\s+(?:yılı|senesi)[{HARF}]*)?\s+(güz|bahar)[{HARF}]*", k):
        ekle(m, *_aralik_ay(int(m[1]), m[2]))
    for m in re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", k):
        ekle(m, *_aralik_ay(int(m[1]), None))
    ay0 = gun.year if gun.month >= 8 else gun.year - 1  # içinde bulunulan eğitim-öğretim yılının başladığı yıl
    guz = gun.month >= 8 or gun.month == 1
    for m in re.finditer(r"\b(bu|geçen) (yıl|sene|dönem|yarıyıl)\b", k):
        if m[2] in ("yıl", "sene"):
            bas, son = ((dt.date(gun.year, 1, 1), gun) if m[1] == "bu"
                        else (min(dt.date(gun.year - 1, 1, 1), dt.date(ay0 - 1, 9, 1)), max(dt.date(gun.year - 1, 12, 31), dt.date(ay0, 8, 31))))
        elif m[1] == "bu":
            bas, son = _aralik_ay(ay0, "güz") if guz else _aralik_ay(gun.year, "bahar")
        else:
            bas, son = _aralik_ay(ay0, "bahar") if guz else _aralik_ay(gun.year - 1, "güz")
        ekle(m, bas, son)
    return sonuc


def kayit_tarihleri(diyalog: list, konu: str, gun: dt.date) -> list:
    """Konuya ait tarih ifadeleri. Asistan az önce bu konuyu sorduysa öğrencinin son mesajı; değilse kayıttan
    söz eden cümleler: ÇAP/yan dal tarihi için bu programların geçtiği, üniversite kaydı için geçmediği cümleler."""
    ogr = _ogrenci(diyalog)
    if _son_asistan(diyalog) in (NETLESTIRME_SORULARI.get(konu), NETLESTIRME_SORULARI_EN.get(konu)):
        cumleler = ogr[-1:]
    else:
        tum = [c for m in ogr for c in re.split(r"[.!?\n]+", m) if KAYIT_IPUCU.search(kucuk(c))]
        cap = [c for c in tum if CAP.search(kucuk(c))]
        cumleler = cap if konu == "cap_yandal_kayit_tarihi" else [c for c in tum if c not in cap]
    return [t for c in cumleler for t in tarih_ifadeleri(c, gun)]


def once_mi(bas: dt.date, son: dt.date, esik: dt.date) -> bool | None:
    """Aralık tümüyle eşikten önceyse True, tümüyle sonraysa False, eşiği kapsıyorsa None (belirsiz)."""
    return True if son < esik else False if bas >= esik else None


def _tek(liste: list):
    return liste[0] if len({x[1:] if isinstance(x, tuple) else x["ad"] for x in liste}) == 1 else None


# --- Karar, bağlı hükümler, koşul notları ---

def netlestirme_konusu(diyalog: list, parca: dict, kurallar: dict, gun: dt.date | None = None) -> str | None:
    """Cevaptan önce sorulması gereken konu; gerek yoksa None."""
    kural = parca_kurali(parca, kurallar)
    if kural is None or _son_asistan(diyalog) in _SORULAR:
        return None  # az önce sorduk: öğrencinin yanıtıyla cevap verilir, aynı soru tekrarlanmaz
    konu = kural["konu"]
    if konu == "fakulte":
        soylendi = birim_soylendi(" ".join(_ogrenci(diyalog)))
    else:
        soylendi = bool(kayit_tarihleri(diyalog, konu, gun or dt.date.today()))
    return None if soylendi else konu


def netlestirme_sorusu(konu: str, diyalog: list) -> str:
    return (NETLESTIRME_SORULARI_EN if ingilizce_mi(_ogrenci(diyalog)[0]) else NETLESTIRME_SORULARI)[konu]


def bagli_ekle(secilen: list, parcalar: list, kurallar: dict) -> list:
    """Seçilen kuralları değiştiren hükümleri (geçici maddeler, yürürlük tarihi) sona ekler; arama bunları kaçırabiliyor."""
    kimlik = {p["id"]: p for p in parcalar}
    sonuc = list(secilen)
    for p in secilen:
        for pid in (parca_kurali(p, kurallar) or {}).get("bagli", []):
            if all(q["id"] != pid for q in sonuc):
                sonuc.append(kimlik[pid])
    return sonuc


def kosul_notlari(diyalog: list, secilen: list, kurallar: dict, eski: list, gun: dt.date) -> tuple:
    """({parça id: [not]}, eklenecek eski parçalar). Yalnızca kesin çözümlenen durumlar için not üretir."""
    notlar = {}

    def ekle(p, metin):
        notlar.setdefault(p["id"], []).append(metin)

    birim = _tek(birimleri_bul(" ".join(_ogrenci(diyalog))))
    kayit = _tek(kayit_tarihleri(diyalog, "kayit_yili", gun))
    for p in secilen:
        k = parca_kurali(p, kurallar)
        if k and k.get("liste") and birim:
            if birim["ad"] in k["liste"]:
                ekle(p, f"Öğrencinin söylediği birim ({birim['ad']}) bu listede sayılıyor.")
            elif birim["tur"] != k.get("liste_belirsiz_tur"):  # ör. MYO: bünyesindeki sağlık programları listede
                ekle(p, f"Öğrencinin söylediği birim ({birim['ad']}) bu listede sayılmıyor.")
        if p.get("kayit_yili_en_gec") and kayit:
            once = once_mi(kayit[1], kayit[2], dt.date(int(p["kayit_yili_en_gec"][-4:]), 9, 1))
            if once is not None:
                ekle(p, f"Öğrencinin söylediği kayıt tarihine ({kayit[0]}) göre bu hüküm ona {'uygulanır' if once else 'uygulanmaz'}.")

    ekler = []
    for g in gecis_hukumleri():
        ilgili = [k for p in secilen if (k := parca_kurali(p, kurallar)) and k["konu"] == g["konu"]]
        hedef = next((p for p in secilen if p["id"] == g["parca"]), None)
        t = _tek(kayit_tarihleri(diyalog, g["konu"], gun)) if ilgili and hedef else None
        if t is None:
            continue
        esik = dt.date.fromisoformat(g["esik"])
        once = once_mi(t[1], t[2], esik)
        if once is None:
            continue
        if once:
            maddeler = dict.fromkeys(m for k in ilgili for m in k.get("eski", []))
            yeni = [e for m in maddeler for e in eski if e["belge"] == g["eski_belge"] and e["madde"] == m]
            ekler += yeni
            ekle(hedef, f"Öğrencinin söylediği kayıt tarihi ({t[0]}) bu yönergenin yürürlüğe girdiği {esik:%d.%m.%Y} tarihinden "
                        "önce: bu hüküm ona uygulanır, kayıt anındaki esaslar geçerlidir."
                        + (" Eski yönergenin ilgili maddeleri kaynaklarda ayrıca verildi." if yeni else ""))
        else:
            ekle(hedef, f"Öğrencinin söylediği kayıt tarihi ({t[0]}) bu yönergenin yürürlüğe girdiği {esik:%d.%m.%Y} tarihinden "
                        "sonra: bu hüküm ona uygulanmaz, bu yönerge uygulanır.")
    return notlar, ekler
