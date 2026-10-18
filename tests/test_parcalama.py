import json
import re
import sys

import pytest

from uuasistan import DATA, KOK
from uuasistan.hazirla import INDEKS_KAPSAMI, ayri_fikralar, belge_maddeleri, katalog, madde_durumlari, parcalar_uret
from uuasistan.metin import temizle
from uuasistan.parcalama import (
    BENT, BOLUM, EKLER, MADDE_BASI, UZUNLUK_SINIRI, Madde, madde_parcalari, maddelere_ayir, paragraflar,
)

sys.path.insert(0, str(KOK / "scripts"))
import test_seti_dogrula  # noqa: E402

BELGELER = katalog()
DURUMLAR = madde_durumlari()
AYRI = ayri_fikralar()


def bosluksuz(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


@pytest.fixture(scope="module")
def parcalar():
    tum = []
    for b in BELGELER:
        if b.get("kapsam") in INDEKS_KAPSAMI:
            tum.extend(parcalar_uret(b, DURUMLAR, AYRI)[0])
    return tum


# --- Gerçek belgeler üzerinde -------------------------------------------------

@pytest.mark.parametrize("belge", BELGELER, ids=lambda b: b["id"])
def test_madde_numaralari_ardisik(belge):
    """Kaçırılan ya da bölünen madde başı numarada boşluk/tekrar olarak görünür. v2 belgeleri de dahil."""
    maddeler = belge_maddeleri(belge)
    for gecici in (False, True):
        nolar = [m.no for m in maddeler if m.gecici == gecici]
        assert nolar == list(range(1, len(nolar) + 1)), f"{belge['id']} {'geçici ' if gecici else ''}maddeler: {nolar}"
    assert any(not m.gecici for m in maddeler)


@pytest.mark.parametrize("belge", [b for b in BELGELER if b.get("kapsam") in INDEKS_KAPSAMI], ids=lambda b: b["id"])
def test_metin_kaybi_yok(belge):
    """İlk maddeden EKLER'e kadar her satır bir madde gövdesinde, başlığında ya da bölüm başlığında bulunur."""
    satirlar = (DATA / belge["metin"]).read_text("utf-8").splitlines()
    ilk = next(i for i, s in enumerate(satirlar) if MADDE_BASI.match(s))
    son = next((i for i, s in enumerate(satirlar) if EKLER.match(s)), len(satirlar))
    kapsanan = bosluksuz(" ".join(f"{m.baslik} {m.bolum} {' '.join(m.satirlar)}" for m in belge_maddeleri(belge)))
    kayip = [
        s for s in satirlar[ilk:son]
        if s and not MADDE_BASI.match(s) and not BOLUM.match(s) and bosluksuz(s.rstrip(".:;,")) not in kapsanan
    ]
    assert not kayip


def test_bent_isaretleri_makul(parcalar):
    """Paragraf başındaki her bent işareti gerçek bir bent işareti olmalı (sahte bölünme yok)."""
    isaretler = {BENT.match(s)[0].strip() for p in parcalar for s in p["metin"].splitlines() if BENT.match(s)}
    gecerli = re.compile(r"^(?:[a-zçğıöşü]\)|[ivx]{1,4}\)|\d\)|•)$")
    assert {i for i in isaretler if not gecerli.match(i)} == set()


def test_test_seti_alintilari_tek_parcada(parcalar):
    """Adım 1'in başarı kriteri: her kaynak alıntısı, doğru maddenin tek bir parçasında eksiksiz bulunur."""
    sorular = json.loads((KOK / "eval" / "test_seti.json").read_text("utf-8"))
    indeks = {}
    for p in parcalar:
        indeks.setdefault((p["belge"], p["madde"]), []).append(bosluksuz(p["metin"]))
    eksik = []
    for s in sorular:
        for k in s["kaynaklar"]:
            metinler = indeks.get((k["belge"], str(k["madde"])), [])
            if not any(bosluksuz(k["alinti"]) in m for m in metinler):
                eksik.append(f"{s['id']}: {k['belge']} m.{k['madde']} {k['alinti'][:50]!r}")
    assert not eksik, "\n".join(eksik)


def test_test_seti_dogrulamasi_geciyor():
    assert test_seti_dogrula.main() == 0


def test_parcalar_dosyasi_guncel(parcalar):
    """data/parcalar.jsonl kod ile senkron olmalı; değilse: python -m uuasistan.hazirla"""
    dosya = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    assert dosya == parcalar


def test_parca_idleri_tekil(parcalar):
    idler = [p["id"] for p in parcalar]
    assert len(idler) == len(set(idler))


def test_parca_uzunlugu(parcalar):
    uzun = [(p["id"], len(p["metin"])) for p in parcalar if len(p["metin"]) > UZUNLUK_SINIRI]
    assert not uzun


def test_bos_parca_yok(parcalar):
    assert all(len(p["metin"]) > 20 for p in parcalar)


def test_sayfa_gurultusu_ve_bozuk_karakter_yok(parcalar):
    for p in parcalar:
        assert not re.search(r"(?i)senato\s+(karar|evrak)\s+eki", p["metin"]), p["id"]
        assert not set("ĠġĢ") & set(p["metin"]), p["id"]


def test_suresi_dolmus_maddeler_dislanir_sureliler_etiketlenir(parcalar):
    eoy = {p["madde"]: p for p in parcalar if p["belge"] == "EOY"}
    assert "Geçici 1" not in eoy and "Geçici 2" not in eoy
    assert eoy["Geçici 3"]["kayit_yili_en_gec"] == "2015-2016"
    assert eoy["Geçici 4"]["kayit_yili_en_gec"] == "2019-2020"
    assert "kayit_yili_en_gec" not in eoy["35"]


def test_v2_belgeleri_indekslenmez(parcalar):
    assert {p["belge"] for p in parcalar} == {b["id"] for b in BELGELER if b.get("kapsam") in INDEKS_KAPSAMI}


def test_degisiklik_bilgisi(parcalar):
    def degisiklik(belge, madde):
        return {d for p in parcalar if p["belge"] == belge and p["madde"] == madde for d in p["degisiklikler"]}
    assert "Değişik:RG-18/8/2024-32636" in degisiklik("EOY", "19")
    assert "Mülga:RG-7/3/2023-32125" in degisiklik("EOY", "18")


def test_guncellik_uyarisi_tasinir():
    belge = next(b for b in BELGELER if b["id"] == "GEC") | {"guncellik": "supheli"}
    assert all(p["guncellik"] == "supheli" for p in parcalar_uret(belge, DURUMLAR)[0])


@pytest.mark.parametrize("belge,madde,baslik", [
    ("EOY", "5", "Öğrenci kontenjanları"),
    ("EOY", "Geçici 4", "Başarı değerlendirmesi"),
    ("GEC_2014", "9", "Değerlendirme"),  # "Madde – 9" yazımı
    ("YAB", "20", "Diğer hususlar"),
    ("UYG", "14", "Zorunlu ya da isteğe bağlı staj"),
])
def test_madde_basliklari(belge, madde, baslik):
    b = next(b for b in BELGELER if b["id"] == belge)
    assert [m.baslik for m in belge_maddeleri(b) if m.etiket == madde] == [baslik]


def test_baslik_onceki_maddeye_karismaz(parcalar):
    """Madde başlığı bir önceki maddenin sonunda kalmamalı."""
    eoy4 = " ".join(p["metin"] for p in parcalar if p["belge"] == "EOY" and p["madde"] == "4")
    assert eoy4.rstrip().endswith("ifade eder.")
    assert "Öğrenci kontenjanları" not in eoy4


# --- Sentetik örneklerle birim testleri --------------------------------------

def test_uc_satira_bolunmus_madde_basi_birlestirilir():
    assert "MADDE 38 – (1)" in temizle("Başlık\nMADDE\n38\n– (1) Metin.\n")


def test_madde_yazim_cesitleri():
    metin = "Amaç\nMadde 1 – (1) a.\nBaşlık\nMADDE 2- (1) b.\nBaşlık\nMadde – 3 (1) c.\nBaşlık\nMADDE 4 -\na) d.\nGEÇİCİ MADDE 1 – (1) e.\n"
    assert [(m.no, m.gecici) for m in maddelere_ayir(metin)] == [(1, False), (2, False), (3, False), (4, False), (1, True)]


def test_iki_satirlik_bolum_adi_madde_basligina_karismaz():
    """YDY 5. bölüm: bölüm adı iki satır; üçüncü satır madde başlığı."""
    m = maddelere_ayir("BEŞİNCİ BÖLÜM\nUluslararası Sınav Merkezleriyle Ortaklaşa\nYürütülen Sınavlar\nUluslararası sınavlar\nMADDE 32 – (1) a.\n")[0]
    assert (m.bolum, m.baslik) == ("BEŞİNCİ BÖLÜM – Uluslararası Sınav Merkezleriyle Ortaklaşa Yürütülen Sınavlar", "Uluslararası sınavlar")


def test_satir_kirilmalari_birlestirilir():
    m = maddelere_ayir("Başlık\nMADDE 1 – (1) Bu bir eğitim-\nöğretim kuralıdır ve\nuzun bir cümledir.\n(2) İkinci fıkra.\n")[0]
    assert madde_parcalari(m) == [([1, 2], "(1) Bu bir eğitim-öğretim kuralıdır ve uzun bir cümledir.\n(2) İkinci fıkra.")]


def test_satir_sonunda_bolunen_degisiklik_notu_bent_sanilmaz():
    """EOY 12/1: '(Değişik ibare:RG-18/8/2024-' + '32636) birim…' yeni paragraf açmamalı."""
    assert paragraflar(["(1) Ancak (Değişik ibare:RG-18/8/2024-", "32636) birim kurulunun önerisi.", "a) Bent."]) == [
        "(1) Ancak (Değişik ibare:RG-18/8/2024-32636) birim kurulunun önerisi.",
        "a) Bent.",
    ]


def test_satir_sonunda_bolunen_parantez_bent_sanilmaz():
    """GEC 5: '(ikinci, üçüncü … sınıflar' + 'için) ÖSYM…' yeni paragraf açmamalı; Roma rakamlı bentler açmalı."""
    assert paragraflar(["a) Her yıl (ikinci ve üçüncü sınıflar", "için) ÖSYM kontenjanı.", "ii) Bent.", "iv) Bent."]) == [
        "a) Her yıl (ikinci ve üçüncü sınıflar için) ÖSYM kontenjanı.",
        "ii) Bent.",
        "iv) Bent.",
    ]


def test_uzun_madde_fikralardan_bolunur():
    m = Madde(1, False, "B", "", [f"({i}) " + "x" * 600 for i in range(1, 5)])
    bolumler = madde_parcalari(m, sinir=1300)
    assert [f for f, _ in bolumler] == [[1, 2], [3, 4]]


def test_uzun_fikra_bentlerden_bolunur_ve_giris_tekrarlanir():
    m = Madde(1, False, "B", "", ["(1) Şunlardır:"] + [f"{h}) " + "y" * 500 for h in "abcd"])
    bolumler = madde_parcalari(m, sinir=1200)
    assert len(bolumler) == 2
    assert bolumler[0][1].startswith("(1) Şunlardır:\na)")
    assert bolumler[1][1].startswith("(1) Şunlardır: (devam)\nc)")
    assert all(f == [1] for f, _ in bolumler)
