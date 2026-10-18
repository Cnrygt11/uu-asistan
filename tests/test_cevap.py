import datetime as dt
import re

from uuasistan.cevap import (
    NETLESTIRME_SORULARI,
    PARCA_SAYISI,
    SOYLENDI,
    Asistan,
    atif_yapilan_maddeler,
    egitim_yili,
    kaynak_metni,
    kosul_kurallari,
    mesajlar,
    netlestirme_konusu,
    sistem_istemi,
)
from uuasistan.degerlendirme import yukle
from uuasistan.uretim import calistir, hiz, ozet

GUN = dt.date(2026, 10, 17)


def ogr(*metinler):
    """Öğrenci ve asistan sırayla konuşur: ogr("soru", "asistan", "yanıt")."""
    return [{"rol": "ogrenci" if i % 2 == 0 else "asistan", "metin": m} for i, m in enumerate(metinler)]


def parca_bul(parcalar, belge, madde, fikra=None):
    return next(i for i, p in enumerate(parcalar) if p["belge"] == belge and p["madde"] == madde and (fikra is None or fikra in p["fikralar"]))


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
    """İstem ve sabit sorular genel kurallar içerir; belirli bir yönetmelik hükmü (tarih, eşik) aramadan gelmeli."""
    for s in (sistem_istemi(GUN), *NETLESTIRME_SORULARI.values()):
        for sizinti in ("20 Mart 2025", "2.72", "2.50", "%70", "Geçici", "2023"):
            assert sizinti not in s
        assert not re.search(r"Madde \d", s)  # örnek atıf bile gerçek bir maddeyi göstermesin


def test_kosullar_dosyasi_dizinle_tutarli():
    parcalar, _ = yukle()
    kimlikler = {p["id"] for p in parcalar}
    for (belge, madde, fikra), k in kosul_kurallari().items():
        assert k["konu"] in NETLESTIRME_SORULARI and k["konu"] in SOYLENDI
        eslesen = [p for p in parcalar if p["belge"] == belge and p["madde"] == madde and (fikra is None or fikra in p["fikralar"])]
        assert eslesen, (belge, madde, fikra)
        if fikra is not None:  # etiketli fıkra kendi parçasında: aynı maddenin koşulsuz fıkralarında soru sorulmaz
            assert all(p["fikralar"] == [fikra] for p in eslesen), (belge, madde, fikra)
        assert set(k.get("bagli", [])) <= kimlikler


def test_etiketli_kural_ilk_siradaysa_cevap_uretmeden_sorar_ve_tekrar_sormaz():
    parcalar, _ = yukle()
    i = parca_bul(parcalar, "EOY", "37", 1)
    uretilen = []
    a = Asistan(parcalar, getir=lambda q: [i], uret=lambda m: uretilen.append(m) or ("cevap", 5), gun=GUN)
    cevap, _, olcum = a.cevapla(ogr("Mezun olmak için kaç AKTS lazım?"))
    assert cevap == NETLESTIRME_SORULARI["fakulte"] and not uretilen
    assert olcum["netlestirme"] == "fakulte" and "token" not in olcum
    # "Hukuk'tayım" kalıba uymasa da az önce sorulan soru tekrarlanmaz, cevap üretilir
    assert a.cevapla(ogr("Mezun olmak için kaç AKTS lazım?", cevap, "Hukuk'tayım."))[0] == "cevap"
    # fakültesini baştan söyleyen öğrenciye sorulmaz
    assert a.cevapla(ogr("Diş hekimliği fakültesindeyim, mezun olmak için kaç AKTS lazım?"))[0] == "cevap"


def test_ayni_maddenin_kosulsuz_fikrasinda_sorulmaz():
    """Devam oranı (EOY 18/1) herkese aynı; yalnızca tekrar alınan derslerdeki istisna (18/3) fakülteye bağlı."""
    parcalar, _ = yukle()
    kurallar = kosul_kurallari()
    oran, istisna = parca_bul(parcalar, "EOY", "18", 1), parca_bul(parcalar, "EOY", "18", 3)
    assert netlestirme_konusu(ogr("Devamsızlık sınırı ne kadar?"), parcalar[oran], kurallar) is None
    assert netlestirme_konusu(ogr("Kaldığım dersi tekrar alıyorum, devam zorunlu mu?"), parcalar[istisna], kurallar) == "fakulte"


def test_ogrenci_bilgiyi_verdiyse_sorulmaz():
    kurallar = {("X", "1", None): {"konu": "fakulte"}, ("X", "2", None): {"konu": "cap_yandal_kayit_tarihi"}}
    fak, cap, diger = ({"belge": "X", "madde": m, "fikralar": []} for m in ("1", "2", "3"))
    assert netlestirme_konusu(ogr("Kaldığım dersi tekrar alıyorum, devam zorunlu mu?"), fak, kurallar) == "fakulte"
    assert netlestirme_konusu(ogr("Tıp fakültesindeyim, devam zorunlu mu?"), fak, kurallar) is None
    assert netlestirme_konusu(ogr("İİBF'deyim."), fak, kurallar) is None
    assert netlestirme_konusu(ogr("2024'te çift anadala başladım."), cap, kurallar) is None
    assert netlestirme_konusu(ogr("Çift anadaldayım, ortalamam düştü."), cap, kurallar) == "cap_yandal_kayit_tarihi"
    assert netlestirme_konusu(ogr("soru"), diger, kurallar) is None


def test_bagli_hukumler_baglama_eklenir():
    """Kayıt yılına bağlı kuralda geçici madde, ÇAP kuralında geçici madde ve yürürlük tarihi aramadan bağımsız eklenir."""
    parcalar, _ = yukle()
    uretilen = []
    for (belge, madde, fikra), soru, beklenen in (
        (("EOY", "35", 2), "İkinci öğretimdeyim, 2023'te kaydoldum. %10 için ortalamam kaç olmalı?", {"EOY-g4"}),
        (("GEC", "20", None), "2024'te çift anadala başladım, ortalamam düştü. Atılır mıyım?", {"GEC-g1", "GEC-m32"}),
    ):
        i = parca_bul(parcalar, belge, madde, fikra)
        a = Asistan(parcalar, getir=lambda q, i=i: [i], uret=lambda m: uretilen.append(m) or ("cevap", 5), gun=GUN)
        _, secilen, _ = a.cevapla(ogr(soru))
        assert {p["id"] for p in secilen[1:]} == beklenen
        assert all(f"Madde {parcalar[next(j for j, p in enumerate(parcalar) if p['id'] == b)]['madde']}" in uretilen[-1][-1]["content"] for b in beklenen)


def test_okuma_notu_yalnizca_etiketli_parcaya_eklenir():
    parcalar, _ = yukle()
    kurallar = kosul_kurallari()
    istisna, oran = parcalar[parca_bul(parcalar, "EOY", "18", 3)], parcalar[parca_bul(parcalar, "EOY", "18", 1)]
    assert "Okuma notu" in kaynak_metni([istisna], kurallar) and "Okuma notu" not in kaynak_metni([oran], kurallar)
    assert "Okuma notu" not in kaynak_metni([istisna])


def test_kaynak_metni_etiketleri_tasir():
    p = {"belge": "Y", "belge_adi": "Y", "madde": "Geçici 4", "baslik": "B", "metin": "M", "kayit_yili_en_gec": "2019-2020", "guncellik": "supheli"}
    k = kaynak_metni([p])
    assert "[1] Y, Madde Geçici 4 (B)" in k and "2019-2020 ve öncesinde" in k and "güncellik: supheli" in k


def test_kaynaklar_yalnizca_son_ogrenci_mesajina_eklenir():
    d = ogr("s1", "c1", "s2")
    p = {"belge": "Y", "belge_adi": "Y", "madde": "1", "baslik": "", "metin": "M"}
    m = mesajlar(d, [p], GUN)
    assert [x["role"] for x in m] == ["system", "user", "assistant", "user"]
    assert m[1]["content"] == "s1" and "KAYNAKLAR" in m[3]["content"] and m[3]["content"].endswith("SORU:\ns2")


def test_asistan_sorguyu_ogrenci_mesajlarindan_kurar_ve_parca_sayisini_sinirlar():
    parcalar = [{"id": f"p{i}", "belge": "Y", "belge_adi": "Y", "madde": str(i), "baslik": "", "metin": "M"} for i in range(20)]
    sorgular = []
    a = Asistan(parcalar, getir=lambda q: sorgular.append(q) or list(range(20)), uret=lambda m: ("cevap", 7), gun=GUN)
    cevap, secilen, olcum = a.cevapla(ogr("a", "x", "b"))
    assert sorgular == ["a b"] and cevap == "cevap" and len(secilen) == PARCA_SAYISI
    assert olcum["token"] == 7 and olcum["arama_sn"] >= 0 and olcum["uretim_sn"] >= 0


def test_atif_yapilan_maddeler():
    c = "Devam %70 (Eğitim Öğretim Yönetmeliği, Madde 18). Bkz. m.29 ve Geçici Madde 4."
    assert atif_yapilan_maddeler(c) == {"18", "29", "Geçici 4"}


def test_uretim_netlestirmede_iki_tur_calistirir():
    """S026'da ilk sıradaki parça mezuniyet AKTS kuralı (fakülteye bağlı): ilk turda sorulur, ikinci turda cevap verilir."""
    parcalar, sorular = yukle()
    sec = [s for s in sorular if s["id"] in ("S001", "S026", "S059")]
    aks = parca_bul(parcalar, "EOY", "37", 1)
    devam = parca_bul(parcalar, "EOY", "18", 1)
    sirali = lambda bas: [bas] + [i for i in range(len(parcalar)) if i != bas]
    a = Asistan(parcalar, getir=lambda q: sirali(aks if "AKTS" in q else devam),
                uret=lambda m: ("Kuramsal derslere %70 devam (Madde 18).", 12), gun=GUN)
    k = {x["id"]: x for x in calistir(a, sec)}
    assert "tur2" not in k["S001"] and k["S001"]["dogru_madde_atfi"] is True and k["S001"]["tur1"].startswith("Kuramsal")
    assert k["S026"]["tur1"] == NETLESTIRME_SORULARI["fakulte"] and k["S026"]["ilk_turda_soru_sordu"] is True
    assert k["S026"]["ogrenci_yaniti"] == "İİBF'deyim." and k["S026"]["tur2"].startswith("Kuramsal")
    assert "getirildi" not in k["S059"]  # kapsam dışı
    o = ozet(list(k.values()), sec)
    assert o["netlestirme_sordu"] == "1/1"
    assert len(k["S026"]["olcum"]) == 2 and "netlestirme" in k["S026"]["olcum"][0] and len(k["S001"]["olcum"]) == 1


def test_hiz_dogrusal_uyumdan_ilk_kelime_ve_token_hizi():
    """uretim_sn = 0.5 + token/50 ise: ilk kelime = arama (0.2) + 0.5, hız = 50 token/sn."""
    olc = [{"arama_sn": 0.2, "uretim_sn": 0.5 + n / 50, "token": n} for n in (100, 200, 300)]
    h = hiz(olc)
    assert h["tahmini_ilk_kelime_sn"] == 0.7 and h["token_per_sn"] == 50.0 and h["token_medyan"] == 200


def test_hiz_netlestirme_olcumlerini_uyumdan_cikarir():
    olc = [{"arama_sn": 0.2, "uretim_sn": 0.5 + n / 50, "token": n} for n in (100, 200, 300)]
    olc.append({"arama_sn": 0.2, "netlestirme": "fakulte"})
    h = hiz(olc)
    assert h["tahmini_ilk_kelime_sn"] == 0.7 and h["token_per_sn"] == 50.0
