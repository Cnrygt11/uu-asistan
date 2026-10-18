import datetime as dt
import json

from uuasistan import DATA
from uuasistan.arama import sozluk_genislet
from uuasistan.degerlendirme import yukle
from uuasistan.hazirla import katalog, madde_durumlari, parcalar_uret
from uuasistan.kosul import (
    NETLESTIRME_SORULARI,
    NETLESTIRME_SORULARI_EN,
    bagli_ekle,
    birim_soylendi,
    birimler,
    birimleri_bul,
    eski_parcalar,
    gecis_hukumleri,
    kayit_tarihleri,
    kosul_kurallari,
    kosul_notlari,
    netlestirme_konusu,
    netlestirme_sorusu,
    once_mi,
    tarih_ifadeleri,
)

GUN = dt.date(2026, 10, 17)
PARCALAR, SORULAR = yukle()
KURALLAR = kosul_kurallari()
ESKI = eski_parcalar()


def ogr(*metinler):
    """Öğrenci ve asistan sırayla konuşur: ogr("soru", "asistan", "yanıt")."""
    return [{"rol": "ogrenci" if i % 2 == 0 else "asistan", "metin": m} for i, m in enumerate(metinler)]


def parca(belge, madde, fikra=None):
    return next(p for p in PARCALAR if p["belge"] == belge and p["madde"] == madde and (fikra is None or fikra in p["fikralar"]))


def notlar_ve_ekler(diyalog, *ilk):
    secilen = bagli_ekle(list(ilk), PARCALAR, KURALLAR)
    return kosul_notlari(diyalog, secilen, KURALLAR, ESKI, GUN)


# --- Veri dosyaları ---

def test_kosullar_dosyasi_dizinle_tutarli():
    kimlikler = {p["id"] for p in PARCALAR}
    eski_maddeler = {(e["belge"], e["madde"]) for e in ESKI}
    adlar = {b["ad"] for b in birimler()}
    for (belge, madde, fikra), k in KURALLAR.items():
        assert k["konu"] in NETLESTIRME_SORULARI and k["konu"] in NETLESTIRME_SORULARI_EN
        eslesen = [p for p in PARCALAR if p["belge"] == belge and p["madde"] == madde and (fikra is None or fikra in p["fikralar"])]
        assert eslesen, (belge, madde, fikra)
        if fikra is not None:  # etiketli fıkra kendi parçasında: aynı maddenin koşulsuz fıkralarında soru sorulmaz
            assert all(p["fikralar"] == [fikra] for p in eslesen), (belge, madde, fikra)
        assert set(k.get("bagli", [])) <= kimlikler
        assert set(k.get("liste", [])) <= adlar  # liste adları birim listesindeki adlarla aynı yazılmalı
    for g in gecis_hukumleri():
        assert g["parca"] in kimlikler and dt.date.fromisoformat(g["esik"])
        for k in KURALLAR.values():
            if k["konu"] == g["konu"]:
                assert {(g["eski_belge"], m) for m in k.get("eski", [])} <= eski_maddeler


def test_eski_parcalar_dosyasi_guncel():
    """data/eski_parcalar.jsonl kod ile senkron olmalı; değilse: python -m uuasistan.hazirla"""
    beklenen = [p for b in katalog() if b.get("bagli_kullanim") for p in parcalar_uret(b, madde_durumlari())[0]]
    assert ESKI == beklenen and ESKI and all(p["uygulama_kosulu"] for p in ESKI)
    assert not {p["id"] for p in ESKI} & {p["id"] for p in PARCALAR}  # aramaya girmez


# --- Öğrencinin söyledikleri ---

def test_birim_tanima():
    bul = lambda t: [b["ad"] for b in birimleri_bul(t)]
    assert bul("Tıp fakültesindeyim") == bul("Tıp'tayım") == bul("Tıp öğrencisiyim") == ["Tıp Fakültesi"]
    assert bul("İİBF'deyim.") == ["İktisadi ve İdari Bilimler Fakültesi"]
    assert bul("Mühendislik Fakültesindeyim.") == ["Mühendislik Fakültesi"]
    assert bul("Eğitim Fakültesi öğrencisiyim.") == ["Eğitim Fakültesi"]
    for baska_anlam in ("tıpkı onun gibi", "uzaktan eğitimde", "hukuki bir sorun"):
        assert bul(baska_anlam) == [] and not birim_soylendi(baska_anlam)
    assert bul("fakültemde") == [] and birim_soylendi("fakültemde")  # birim belli değil ama söylenmiş


def test_tarih_ifadeleri_kayit_donemi_araligi():
    ara = lambda t: [(str(b), str(s)) for _, b, s in tarih_ifadeleri(t, GUN)]
    assert ara("2019 güzünde hazırlıkla başladım.") == [("2019-08-01", "2019-10-31")]
    assert ara("2020 baharında kaydoldum") == [("2020-01-15", "2020-03-15")]
    assert ara("2019-2020'de kayıt oldum") == [("2019-08-01", "2020-03-31")]
    assert ara("2024'te çift anadala başladım") == ara("Üniversiteye 2024.") == [("2024-01-01", "2024-12-31")]
    assert ara("bu dönem başladım") == [("2026-08-01", "2026-10-31")]
    assert ara("geçen yıl başladım") == [("2025-01-01", "2026-08-31")]
    assert ara("%10'a girersem") == ara("5. yarıyılda") == ara("GANO'm 2.45") == []


def test_kayit_tarihi_konuya_gore_ayrilir():
    s087 = ogr("2024'te çift anadala başladım. Yeni ÇAP yönergesindeki ortalama şartları bana da uygulanıyor mu?")
    assert [t[0] for t in kayit_tarihleri(s087, "cap_yandal_kayit_tarihi", GUN)] == ["2024"]
    assert kayit_tarihleri(s087, "kayit_yili", GUN) == []  # ÇAP tarihi üniversite kaydı değildir
    # bizim sorumuza verilen yanıtta ipucu sözcüğü gerekmez
    yanit = ogr("Çift anadaldayım, ortalamam düştü.", NETLESTIRME_SORULARI["cap_yandal_kayit_tarihi"], "2025 güzü.")
    assert [t[0] for t in kayit_tarihleri(yanit, "cap_yandal_kayit_tarihi", GUN)] == ["2025 güzü"]
    # kayıttan söz etmeyen tarih kayıt tarihi değildir
    assert kayit_tarihleri(ogr("Bu yıl ikinci öğretim harcı ne kadar?"), "kayit_yili", GUN) == []
    assert kayit_tarihleri(ogr("2026-2027 güz dönemi final sınavları hangi tarihlerde?"), "kayit_yili", GUN) == []


def test_once_mi_belirsizi_ayirir():
    esik = dt.date(2020, 9, 1)  # 2019-2020 ve öncesi
    assert once_mi(dt.date(2019, 8, 1), dt.date(2019, 10, 31), esik) is True
    assert once_mi(dt.date(2023, 1, 1), dt.date(2023, 12, 31), esik) is False
    assert once_mi(dt.date(2020, 1, 1), dt.date(2020, 12, 31), esik) is None  # "2020'de": hangi eğitim yılı belli değil


# --- Karar ---

def test_netlestirme_kayit_tarihi_soylendiyse_sorulmaz():
    cap = parca("GEC", "20")
    assert netlestirme_konusu(ogr("Çift anadaldayım, ortalamam düştü. Atılır mıyım?"), cap, KURALLAR, GUN) == "cap_yandal_kayit_tarihi"
    assert netlestirme_konusu(ogr("2024'te çift anadala başladım. Ortalamam düştü."), cap, KURALLAR, GUN) is None
    # üniversite kayıt yılı ÇAP kayıt tarihinin yerini tutmaz
    assert netlestirme_konusu(ogr("2019'da kaydoldum. Çift anadaldayım, ortalamam düştü."), cap, KURALLAR, GUN) == "cap_yandal_kayit_tarihi"


def test_ingilizce_soruya_ingilizce_sabit_soru():
    assert netlestirme_sorusu("fakulte", ogr("How many ECTS do I need to graduate?")) == NETLESTIRME_SORULARI_EN["fakulte"]
    assert netlestirme_sorusu("fakulte", ogr("Mezun olmak için kaç AKTS lazım?")) == NETLESTIRME_SORULARI["fakulte"]
    soru = ogr("How many ECTS do I need to graduate?", NETLESTIRME_SORULARI_EN["fakulte"], "Law.")
    assert netlestirme_konusu(soru, parca("EOY", "37", 1), KURALLAR, GUN) is None  # az önce sorduk


# --- Koşul notları ---

def test_liste_uyeligi_notu():
    istisna = parca("EOY", "18", 3)
    for metin, beklenen in (("Mühendislik Fakültesindeyim.", "sayılmıyor"), ("Tıp fakültesindeyim.", "sayılıyor"),
                            ("Eğitim Fakültesi öğrencisiyim.", "sayılmıyor")):
        notlar, _ = notlar_ve_ekler(ogr("Kaldığım dersi tekrar alıyorum, devam zorunlu mu?", "?", metin), istisna)
        assert notlar[istisna["id"]] == [f"Öğrencinin söylediği birim ({birimleri_bul(metin)[0]['ad']}) bu listede {beklenen}."]
    # MYO bünyesindeki sağlık programları da listede: program bilinmeden karar verilmez
    myo = [{"ad": "Teknik Bilimler Meslek Yüksekokulu", "tur": "myo", "adlar": ["teknik bilimler"]}]
    assert birimleri_bul("Teknik Bilimler MYO'dayım", myo) and not birimleri_bul("Teknik Bilimler MYO'dayım")
    notlar, _ = notlar_ve_ekler(ogr("Tekrar aldığım derse devam zorunlu mu? Fakültemi söylemeyeceğim."), istisna)
    assert not notlar  # birim belli değilse not yok


def test_gecici_4_kayit_yili_notu():
    yuzde10 = parca("EOY", "35", 2)
    g4 = next(p for p in PARCALAR if p["id"] == "EOY-g4")
    for metin, beklenen in (("İkinci öğretimdeyim. 2023'te kayıt oldum. %10 için ortalamam kaç olmalı?", "uygulanmaz"),
                            ("2019 güzünde hazırlıkla başladım. %10 için ortalamam kaç olmalı?", "uygulanır")):
        notlar, ekler = notlar_ve_ekler(ogr(metin), yuzde10)
        assert list(notlar) == [g4["id"]] and beklenen in notlar[g4["id"]][0] and not ekler
    notlar, _ = notlar_ve_ekler(ogr("2020'de kaydoldum. %10 için ortalamam kaç olmalı?"), yuzde10)
    assert not notlar  # 2019-2020 mi 2020-2021 mi belli değil


def test_gecici_1_eski_yonergeyi_yalnizca_once_kaydolana_ekler():
    silme = parca("GEC", "20")
    notlar, ekler = notlar_ve_ekler(ogr("2024'te çift anadala başladım. Ortalamam düşerse kaydım silinir mi?"), silme)
    assert "önce" in notlar["GEC-g1"][0] and "20.03.2025" in notlar["GEC-g1"][0]
    assert [e["id"] for e in ekler] == ["GEC_2014-m18"] and "2,50’nin altına" in ekler[0]["metin"]
    notlar, ekler = notlar_ve_ekler(ogr("Çift anadaldayım.", NETLESTIRME_SORULARI["cap_yandal_kayit_tarihi"], "2025 güzünde başladım."), silme)
    assert "sonra" in notlar["GEC-g1"][0] and not ekler
    notlar, ekler = notlar_ve_ekler(ogr("2025'te çift anadala başladım. Kaydım silinir mi?"), silme)
    assert not notlar and not ekler  # 20 Mart 2025'ten önce mi sonra mı belli değil


# --- Sözlükle sorgu genişletme ---

def test_sozluk_genisletme():
    assert sozluk_genislet("Kayıt dondurduğum dönemde sınava girebilir miyim?").endswith("(izinli ayrılma)")
    assert "bütünleme sınavı" in sozluk_genislet("Büte kimler girebiliyor?")
    assert "bütünleme" not in sozluk_genislet("Bütün derslerimi geçtim.")  # kısa terim yalnızca eklerle
    assert "FF / FD notu" in sozluk_genislet("Seçmeli dersten kaldım.")  # fiil çekimi
    assert sozluk_genislet("Çift anadal (ÇAP) yapmak için") == "Çift anadal (ÇAP) yapmak için"  # karşılığı zaten var
    assert sozluk_genislet("Çanakkale") == "Çanakkale"


def test_test_seti_netlestirme_konulari_tanimli():
    assert {s["netlestirme"]["konu"] for s in SORULAR if s.get("netlestirme")} <= set(NETLESTIRME_SORULARI)
    assert json.loads((DATA / "birimler.json").read_text("utf-8"))["birimler"] == birimler()
