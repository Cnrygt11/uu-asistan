import pytest

from uuasistan.arama import BM25, YOGUN_MODELLER, kucuk, rrf, tokenlar
from uuasistan.degerlendirme import hedefler, kacirilanlar, metrikler, sorgu_metni, yukle


@pytest.fixture(scope="module")
def veri():
    return yukle()


def test_turkce_kucuk_harf():
    assert kucuk("IĞDIR İSTANBUL") == "ığdır istanbul"


def test_tokenlar_durak_kelimeleri_atar_ve_kok_bulur():
    assert tokenlar("Öğrencilerin sınavlarına ve derslerine", kok="snowball") == ["öğrenci", "sınav", "ders"]
    assert tokenlar("Öğrencilerin sınavlarına", kok="onek5") == ["öğren", "sınav"]
    assert tokenlar("Devam nedir?", kok=None) == ["devam"]


def test_rrf_elle_hesaplanan_ornekler():
    # 1 ve 2: 1/61 + 1/62 (eşit, küçük indeks önce); 3 ve 4: 1/63
    assert rrf([[1, 2, 3], [2, 1, 4]]) == [1, 2, 3, 4]
    # 1 ve 3: 1/61 + 1/63 = 0.032266 > 2: 2/62 = 0.032258
    assert rrf([[1, 2, 3], [3, 2, 1]]) == [1, 3, 2]
    # iki listede birden geçen, tek listede birinci olanı geçer
    assert rrf([[5, 6], [7, 5]]) == [5, 7, 6]


def test_metrikler_elle_hesaplanan_ornek():
    hedef = {"a": [{0}], "b": [{1}, {9}]}
    sir = {"a": [0, 5, 6], "b": [7, 1, 8, 2, 3, 9]}
    m = metrikler(sir, hedef, ks=(1, 5))
    assert m["recall@1"] == pytest.approx((1 + 0) / 2)
    assert m["recall@5"] == pytest.approx((1 + 0.5) / 2)  # b'nin ikinci kaynağı 6. sırada
    assert m["tam@5"] == pytest.approx(0.5)
    assert m["mrr"] == pytest.approx((1 + 1 / 2) / 2)
    assert kacirilanlar(sir, hedef, k=5) == ["b"]


def test_her_kaynagin_dogru_parcasi_var(veri):
    """Değerlendirme hedefi boş kalan kaynak olmamalı (aksi halde recall yapay olarak düşer)."""
    parcalar, sorular = veri
    h = hedefler(sorular, parcalar)
    assert len(h) == sum(s["kategori"] != "kapsam_disi" for s in sorular)
    assert all(all(k) for k in h.values())


def test_netlestirmede_ogrenci_yaniti_sorguya_eklenir(veri):
    _, sorular = veri
    s = next(s for s in sorular if s["id"] == "S026")
    assert sorgu_metni(s).endswith(s["netlestirme"]["ogrenci_yaniti"])


def test_bm25_belirgin_soruyu_bulur(veri):
    parcalar, _ = veri
    bm = BM25([p["arama_metni"] for p in parcalar], kok="onek5")
    ilk5 = [parcalar[i]["id"] for i in bm.ara("Devamsızlık sınırı yüzde kaç, kuramsal derslere devam zorunluluğu", 5)]
    assert any(i.startswith("EOY-m18") for i in ilk5)


def test_uzak_kod_yalnizca_onayli_modellerde():
    """trust_remote_code Hugging Face'ten kod çalıştırır; yeni bir model eklenirken bilinçli onay gerekir."""
    onayli = {"newmindai/TurkEmbed4Retrieval"}
    assert {m.ad for m in YOGUN_MODELLER.values() if m.uzak_kod} == onayli


def test_kaynak_siralari():
    from uuasistan.degerlendirme import kaynak_siralari
    assert kaynak_siralari({"b": [7, 1, 8]}, {"b": [{1}, {9}]}) == {"b": [1, None]}


def test_yogun_model_adlari_tekil():
    adlar = [m.ad for m in YOGUN_MODELLER.values()]
    assert len(adlar) == len(set(adlar))
