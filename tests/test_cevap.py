import datetime as dt
import re

from uuasistan.cevap import (
    KARARLAR,
    NETLESTIRME_SORULARI,
    PARCA_SAYISI,
    Asistan,
    atif_yapilan_maddeler,
    egitim_yili,
    kaynak_metni,
    karar_istemi,
    mesajlar,
    sistem_istemi,
)
from uuasistan.degerlendirme import yukle
from uuasistan.uretim import calistir, hiz, ozet

GUN = dt.date(2026, 10, 17)


def test_egitim_yili_eylulde_baslar():
    assert egitim_yili(dt.date(2026, 10, 17)) == "2026-2027"
    assert egitim_yili(dt.date(2027, 3, 1)) == "2026-2027"
    assert egitim_yili(dt.date(2026, 8, 31)) == "2025-2026"


def test_sistem_istemi_tarih_ve_kurallari_icerir():
    s = sistem_istemi(GUN)
    assert "17 Ekim 2026" in s and "2026-2027" in s
    for kural in ("uydurma", "tırnak içinde aynen alıntılayarak", "beş cümle", '"sen"', "enstitü", "İngilizce"):
        assert kural in s


def test_istemler_test_setinin_cevabini_sizdirmaz():
    """İstemler genel kurallar içerir; belirli bir yönetmelik hükmü (tarih, eşik) aramadan gelmeli."""
    for s in (sistem_istemi(GUN), karar_istemi()):
        for sizinti in ("20 Mart 2025", "2.72", "2.50", "%70", "Geçici", "2023"):
            assert sizinti not in s
        assert not re.search(r"Madde \d", s)  # örnek atıf bile gerçek bir maddeyi göstermesin


def test_karar_istemi_secenekleri_tanimlar():
    s = karar_istemi()
    assert all(f"- {k}:" in s for k in KARARLAR)


def test_netlestirme_karari_cevap_uretmeden_soru_sorar():
    parcalar = [{"id": "p0", "belge_adi": "Y", "madde": "1", "baslik": "", "metin": "M"}]
    uretilen, kararlar = [], []
    a = Asistan(parcalar, getir=lambda q: [0], uret=lambda m: uretilen.append(m) or ("cevap", 5),
                gun=GUN, karar=lambda m: kararlar.append(m) or "fakulte")
    cevap, _, olcum = a.cevapla([{"rol": "ogrenci", "metin": "soru"}])
    assert cevap == NETLESTIRME_SORULARI["fakulte"] and not uretilen
    assert olcum["netlestirme"] == "fakulte" and "token" not in olcum and olcum["karar_sn"] >= 0
    assert kararlar[0][0]["content"] == karar_istemi() and kararlar[0][1]["content"].endswith("SORU:\nsoru")
    # İkinci tur: asistan zaten sordu, karar atlanır ve cevap üretilir
    cevap, _, olcum = a.cevapla([{"rol": "ogrenci", "metin": "soru"}, {"rol": "asistan", "metin": cevap}, {"rol": "ogrenci", "metin": "İİBF"}])
    assert cevap == "cevap" and len(kararlar) == 1 and olcum["token"] == 5


def test_karar_yok_ise_cevap_uretilir():
    parcalar = [{"id": "p0", "belge_adi": "Y", "madde": "1", "baslik": "", "metin": "M"}]
    a = Asistan(parcalar, getir=lambda q: [0], uret=lambda m: ("cevap", 5), gun=GUN, karar=lambda m: "yok")
    cevap, _, olcum = a.cevapla([{"rol": "ogrenci", "metin": "soru"}])
    assert cevap == "cevap" and "netlestirme" not in olcum and olcum["token"] == 5


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
    a = Asistan(parcalar, getir=lambda q: sorgular.append(q) or list(range(20)), uret=lambda m: ("cevap", 7), gun=GUN)
    cevap, secilen, olcum = a.cevapla([{"rol": "ogrenci", "metin": "a"}, {"rol": "asistan", "metin": "x"}, {"rol": "ogrenci", "metin": "b"}])
    assert sorgular == ["a b"] and cevap == "cevap" and len(secilen) == PARCA_SAYISI
    assert olcum["token"] == 7 and olcum["arama_sn"] >= 0 and olcum["uretim_sn"] >= 0


def test_atif_yapilan_maddeler():
    c = "Devam %70 (Eğitim Öğretim Yönetmeliği, Madde 18). Bkz. m.29 ve Geçici Madde 4."
    assert atif_yapilan_maddeler(c) == {"18", "29", "Geçici 4"}


def test_uretim_netlestirmede_iki_tur_calistirir():
    parcalar, sorular = yukle()
    sec = [s for s in sorular if s["id"] in ("S001", "S026", "S059")]
    cagrilar = []

    def uret(m):
        cagrilar.append(m)
        return ("Hangi fakültedesin?", 5) if len(cagrilar) == 2 else ("Kuramsal derslere %70 devam (Madde 18).", 12)

    a = Asistan(parcalar, getir=lambda q: list(range(len(parcalar))), uret=uret, gun=GUN)
    k = {x["id"]: x for x in calistir(a, sec)}
    assert "tur2" not in k["S001"] and k["S001"]["dogru_madde_atfi"] is True
    assert k["S026"]["ilk_turda_soru_sordu"] is True and k["S026"]["ogrenci_yaniti"] == "İİBF'deyim." and "tur2" in k["S026"]
    assert "getirildi" not in k["S059"]  # kapsam dışı
    o = ozet(list(k.values()), sec)
    assert o["netlestirme_sordu"] == "1/1"
    assert len(k["S026"]["olcum"]) == 2 and len(k["S001"]["olcum"]) == 1


def test_hiz_dogrusal_uyumdan_ilk_kelime_ve_token_hizi():
    """uretim_sn = 0.5 + token/50 ise: ilk kelime = arama (0.2) + 0.5, hız = 50 token/sn."""
    olc = [{"arama_sn": 0.2, "uretim_sn": 0.5 + n / 50, "token": n} for n in (100, 200, 300)]
    h = hiz(olc)
    assert h["tahmini_ilk_kelime_sn"] == 0.7 and h["token_per_sn"] == 50.0 and h["token_medyan"] == 200


def test_hiz_netlestirme_olcumlerini_uyumdan_cikarir_ve_karar_suresini_ekler():
    olc = [{"arama_sn": 0.2, "karar_sn": 0.1, "uretim_sn": 0.5 + n / 50, "token": n} for n in (100, 200, 300)]
    olc.append({"arama_sn": 0.2, "karar_sn": 0.1, "netlestirme": "fakulte"})
    h = hiz(olc)
    assert h["tahmini_ilk_kelime_sn"] == 0.8 and h["token_per_sn"] == 50.0 and h["karar_sn_medyan"] == 0.1
