"""Mevzuat metnini madde bazlı parçalara böler.

Her madde bir parçadır. UZUNLUK_SINIRI'nı aşan maddeler fıkra sınırlarından,
tek başına sınırı aşan fıkralar bent sınırlarından bölünür; bentlere bölünen
fıkranın giriş cümlesi her alt parçanın başına eklenir.
"""
import re
from dataclasses import dataclass, field

UZUNLUK_SINIRI = 1500  # karakter; yaklaşık 350-400 token

MADDE_BASI = re.compile(
    r"^(?P<gecici>(?:GEÇİCİ|Geçici)\s+)?(?:MADDE|Madde)\s*[-–]?\s*(?P<no>\d+)\s*(?=[-–(]|$)"
)
BOLUM = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)\s+BÖLÜM$"
)
EKLER = re.compile(r"^EKLER\s*:?$")
FIKRA = re.compile(r"^\((\d+)\)")
# a) b) ... ğ) ı) ; i) ii) iv) ; 2) gibi numaralı bentler ; madde işareti.
# Sayı en fazla iki hane: satır sonunda bölünen "(Değişik ibare:RG-18/8/2024-\n32636)" bent sanılmasın.
BENT = re.compile(r"^(?:[a-zçğıöşü]{1,4}\)|\d{1,2}\)|•)\s?")
# Tireyle biten satırın devamı ("eğitim-" + "öğretim", "2019-" + "2020")
TIRE_DEVAMI = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]-$")
DEGISIKLIK = re.compile(r"\((Değişik|Mülga|Ek)(?: ibare)?\s*:\s*RG-\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d+)\)")
CUMLE_SONU = (".", ":", ";", ",")


@dataclass
class Madde:
    no: int
    gecici: bool
    baslik: str
    bolum: str
    satirlar: list = field(default_factory=list)

    @property
    def etiket(self) -> str:
        return f"Geçici {self.no}" if self.gecici else str(self.no)


def _baslik_ayir(govde: list) -> str:
    """Madde satırının hemen üstündeki başlık satırlarını önceki gövdeden ayırıp döndürür."""
    while govde and not govde[-1]:
        govde.pop()
    baslik = []
    while govde and govde[-1] and len(baslik) < 3:
        aday = govde[-1]
        if len(aday) > 100 or FIKRA.match(aday) or BENT.match(aday):
            break
        if aday.endswith(CUMLE_SONU):
            # Noktalamayla biten kısa, tek başına duran satır yine başlıktır ("Diğer hususlar;")
            # Sayfa sonundan kalan cümle parçalarını ("yapılmaz.") başlık sanmamak için dar tutulur
            oncesi_bos = len(govde) < 2 or not govde[-2]
            if baslik or len(aday) > 40 or not oncesi_bos or aday.endswith(".") or not aday[0].isupper():
                break
            aday = aday.rstrip("".join(CUMLE_SONU))
            govde.pop()
            baslik.insert(0, aday)
            break
        baslik.insert(0, govde.pop())
    return " ".join(baslik)


def maddelere_ayir(metin: str) -> list:
    maddeler, giris, bolum = [], [], ""
    satirlar = metin.splitlines()
    i = 0
    while i < len(satirlar):
        s = satirlar[i]
        hedef = maddeler[-1].satirlar if maddeler else giris
        if EKLER.match(s):
            break
        if BOLUM.match(s):
            j = i + 1
            while j < len(satirlar) and not satirlar[j]:
                j += 1
            bolum = f"{s} – {satirlar[j]}" if j < len(satirlar) else s
            i = j + 1
            continue
        m = MADDE_BASI.match(s)
        if m:
            baslik = _baslik_ayir(hedef)
            yeni = Madde(int(m["no"]), bool(m["gecici"]), baslik, bolum)
            ilk = s[m.end():].lstrip(" -–")
            if ilk:
                yeni.satirlar.append(ilk)
            maddeler.append(yeni)
        else:
            hedef.append(s)
        i += 1
    return maddeler


def paragraflar(satirlar: list) -> list:
    """PDF satır kırılmalarını birleştirir; fıkra ve bent başlarında yeni paragraf açar."""
    sonuc = []
    for s in satirlar:
        if not s:
            continue
        if sonuc and TIRE_DEVAMI.search(sonuc[-1]) and (s[:1].islower() or s[:1].isdigit()):
            sonuc[-1] += s  # tireyle bölünmüş kelime/tarih: araya boşluk girmez, yeni paragraf açılmaz
        elif not sonuc or FIKRA.match(s) or BENT.match(s):
            sonuc.append(s)
        else:
            sonuc[-1] += " " + s
    return sonuc


def _fikralar(paras: list) -> list:
    """[(fikra_no | None, [paragraflar])]"""
    gruplar = []
    for p in paras:
        m = FIKRA.match(p)
        if m or not gruplar:
            gruplar.append((int(m[1]) if m else None, [p]))
        else:
            gruplar[-1][1].append(p)
    return gruplar


def _paketle(birimler: list, sinir: int) -> list:
    """Birimleri sırayla, toplam uzunluk sınırı aşmayacak şekilde gruplar."""
    paketler, mevcut, uzunluk = [], [], 0
    for b in birimler:
        u = len(b[1]) + 1
        if mevcut and uzunluk + u > sinir:
            paketler.append(mevcut)
            mevcut, uzunluk = [], 0
        mevcut.append(b)
        uzunluk += u
    if mevcut:
        paketler.append(mevcut)
    return paketler


def madde_parcalari(madde: Madde, sinir: int = UZUNLUK_SINIRI) -> list:
    """[(fikra_numaralari, metin)]"""
    paras = paragraflar(madde.satirlar)
    tam = "\n".join(paras)
    if len(tam) <= sinir:
        return [([f for f, _ in _fikralar(paras) if f is not None], tam)]

    birimler = []  # (fikra_no, metin)
    for no, ps in _fikralar(paras):
        metin = "\n".join(ps)
        if len(metin) <= sinir or len(ps) == 1:
            birimler.append((no, metin))
            continue
        # Fıkra tek başına uzun: bentlerden böl, giriş cümlesini her alt parçaya ekle
        giris, bentler = (ps[0], ps[1:]) if not BENT.match(ps[0]) else ("", ps)
        alt = _paketle([(no, b) for b in bentler], sinir - len(giris))
        for k, grup in enumerate(alt):
            onek = giris if k == 0 else f"{giris} (devam)" if giris else ""
            birimler.append((no, "\n".join(([onek] if onek else []) + [b for _, b in grup])))

    return [
        (sorted({f for f, _ in grup if f is not None}), "\n".join(m for _, m in grup))
        for grup in _paketle(birimler, sinir)
    ]


def degisiklikler(metin: str) -> list:
    return sorted({f"{tur}:RG-{tarih}-{sayi}" for tur, tarih, sayi in DEGISIKLIK.findall(metin)})
