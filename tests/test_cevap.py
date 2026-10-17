import datetime as dt
import re

from uuasistan.cevap import PARCA_SAYISI, Asistan, atif_yapilan_maddeler, egitim_yili, kaynak_metni, mesajlar, sistem_istemi
from uuasistan.degerlendirme import yukle
from uuasistan.uretim import calistir, ozet

GUN = dt.date(2026, 10, 17)


def test_egitim_yili_eylulde_baslar():
    assert egitim_yili(dt.date(2026, 10, 17)) == "2026-2027"
    assert egitim_yili(dt.date(2027, 3, 1)) == "2026-2027"
    assert egitim_yili(dt.date(2026, 8, 31)) == "2025-2026"


def test_sistem_istemi_tarih_ve_kurallari_icerir():
    s = sistem_istemi(GUN)
    assert "17 Ekim 2026" in s and "2026-2027" in s
    for kural in ("uydurma", "Madde N", '"sen"', "kayıt tarihine göre", "enstitü"):
        assert kural in s


def test_sistem_istemi_test_setinin_cevabini_sizdirmaz():
    """İstem genel kurallar içerir; belirli bir yönetmelik hükmü (tarih, eşik) aramadan gelmeli."""
    s = sistem_istemi(GUN)
    for sizinti in ("20 Mart 2025", "2.72", "2.50", "%70", "Geçici"):
        assert sizinti not in s
    assert not re.search(r"Madde \d", s)  # örnek atıf bile gerçek bir maddeyi göstermesin


def test_kaynak_metni_etiketleri_tasir():
    p = {"belge_adi": "Y", "madde": "Geçici 4", "baslik": "B", "metin": "M", "kayit_yili_en_gec": "2019-2020", "guncellik": "supheli"}
    k = kaynak_metni([p])
    assert "[1] Y, Madde Geçici 4 (B)" in k and "2019-2020 ve öncesinde" in k and "güncellik: supheli" in k


def test_kaynaklar_yalnizca_son_ogrenci_mesajina_eklenir():
    d = [{"rol": "ogrenci", "metin": "s1"}, {"rol": "asistan", "metin": "c1"}, {"rol": "ogrenci", "metin": "s2"}]
    p = {"belge_adi": "Y", "madde": "1", "baslik": "", "metin": "M"}
    m = mesajlar(d, [p], GUN)
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user"]
    assert m[1]["content"] == "s1" and "KAYNAKLAR" in m[3]["content"] and m[3]["content"].endswith("SORU:\ns2")


def test_asistan_sorguyu_ogrenci_mesajlarindan_kurar_ve_parca_sayisini_sinirlar():
    parcalar = [{"id": f"p{i}", "belge_adi": "Y", "madde": str(i), "baslik": "", "metin": "M"} for i in range(20)]
    sorgular = []
    a = Asistan(parcalar, getir=lambda q: sorgular.append(q) or list(range(20)), uret=lambda m: "cevap", gun=GUN)
    cevap, secilen = a.cevapla([{"rol": "ogrenci", "metin": "a"}, {"rol": "asistan", "metin": "x"}, {"rol": "ogrenci", "metin": "b"}])
    assert sorgular == ["a b"] and cevap == "cevap" and len(secilen) == PARCA_SAYISI


def test_atif_yapilan_maddeler():
    c = "Devam %70 (Eğitim Öğretim Yönetmeliği, Madde 18). Bkz. m.29 ve Geçici Madde 4."
    assert atif_yapilan_maddeler(c) == {"18", "29", "Geçici 4"}


def test_uretim_netlestirmede_iki_tur_calistirir():
    parcalar, sorular = yukle()
    sec = [s for s in sorular if s["id"] in ("S001", "S026", "S059")]
    cagrilar = []

    def uret(m):
        cagrilar.append(m)
        return "Hangi fakültedesin?" if len(cagrilar) == 2 else "Kuramsal derslere %70 devam (Madde 18)."

    a = Asistan(parcalar, getir=lambda q: list(range(len(parcalar))), uret=uret, gun=GUN)
    k = {x["id"]: x for x in calistir(a, sec)}
    assert "tur2" not in k["S001"] and k["S001"]["dogru_madde_atfi"] is True
    assert k["S026"]["ilk_turda_soru_sordu"] is True and k["S026"]["ogrenci_yaniti"] == "İİBF'deyim." and "tur2" in k["S026"]
    assert "getirildi" not in k["S059"]  # kapsam dışı
    o = ozet(list(k.values()), sec)
    assert o["netlestirme_sordu"] == "1/1"
