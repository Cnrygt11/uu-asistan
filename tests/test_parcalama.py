import json
import re
import sys

import pytest

from uuasistan import DATA, KOK
from uuasistan.hazirla import INDEKS_KAPSAMI, belge_maddeleri, katalog, madde_durumlari, parcalar_uret
from uuasistan.metin import temizle
from uuasistan.parcalama import UZUNLUK_SINIRI, Madde, madde_parcalari, maddelere_ayir

sys.path.insert(0, str(KOK / "scripts"))
import test_seti_dogrula  # noqa: E402

BELGELER = katalog()
DURUMLAR = madde_durumlari()


def bosluksuz(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


@pytest.fixture(scope="module")
def parcalar():
    tum = []
    for b in BELGELER:
        if b.get("kapsam") in INDEKS_KAPSAMI:
            tum.extend(parcalar_uret(b, DURUMLAR)[0])
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


def test_guncellik_uyarisi_tasinir(parcalar):
    assert all(p.get("guncellik") == "supheli" for p in parcalar if p["belge"] == "GEC")


@pytest.mark.parametrize("belge,madde,baslik", [
    ("EOY", "5", "Öğrenci kontenjanları"),
    ("EOY", "Geçici 4", "Başarı değerlendirmesi"),
    ("GEC", "9", "Değerlendirme"),
    ("YAB", "20", "Diğer hususlar"),
    ("UYG", "14", "Zorunlu ya da isteğe bağlı staj"),
])
def test_madde_basliklari(parcalar, belge, madde, baslik):
    assert {p["baslik"] for p in parcalar if p["belge"] == belge and p["madde"] == madde} == {baslik}


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


def test_satir_kirilmalari_birlestirilir():
    m = maddelere_ayir("Başlık\nMADDE 1 – (1) Bu bir eğitim-\nöğretim kuralıdır ve\nuzun bir cümledir.\n(2) İkinci fıkra.\n")[0]
    assert madde_parcalari(m) == [([1, 2], "(1) Bu bir eğitim-öğretim kuralıdır ve uzun bir cümledir.\n(2) İkinci fıkra.")]


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
