"""Arama değerlendirmesi: test setinden doğru parçaları çıkarır ve metrikleri hesaplar.

Bir sorunun her kaynağı (belge, madde, alıntı) için "doğru parça", aynı belge ve
maddeye ait olup alıntıyı içeren parçadır. Kapsam dışı sorular arama
değerlendirmesine katılmaz.
"""
import json
import re

from . import DATA, KOK


def bosluksuz(metin: str) -> str:
    return re.sub(r"\s+", "", metin).casefold()


def yukle() -> tuple:
    parcalar = [json.loads(s) for s in (DATA / "parcalar.jsonl").read_text("utf-8").splitlines()]
    sorular = json.loads((KOK / "eval" / "test_seti.json").read_text("utf-8"))
    return parcalar, sorular


def sorgu_metni(soru: dict) -> str:
    """Netleştirmeli sorularda öğrencinin yanıtı da sorguya eklenir (diyaloğun ikinci adımı)."""
    n = soru.get("netlestirme")
    return f"{soru['soru']} {n['ogrenci_yaniti']}" if n else soru["soru"]


def hedefler(sorular: list, parcalar: list) -> dict:
    """{soru_id: [kaynak başına doğru parça indeksleri kümesi]}"""
    sonuc = {}
    for s in sorular:
        if s["kategori"] == "kapsam_disi":
            continue
        kumeler = []
        for k in s["kaynaklar"]:
            alinti = bosluksuz(k["alinti"])
            kumeler.append({
                i for i, p in enumerate(parcalar)
                if p["belge"] == k["belge"] and p["madde"] == str(k["madde"]) and alinti in bosluksuz(p["metin"])
            })
        sonuc[s["id"]] = kumeler
    return sonuc


def _sira(siralama: list, kume: set) -> float:
    return next((r for r, i in enumerate(siralama) if i in kume), float("inf"))


def metrikler(siralamalar: dict, hedef: dict, ks=(1, 3, 5, 10)) -> dict:
    """
    recall@k: kaynakların ilk k sonuçta bulunma oranı (soru başına ortalama, sonra genel ortalama)
    tam@k:    tüm kaynakları ilk k'da bulunan soruların oranı
    mrr:      ilk doğru parçanın sırasının tersi
    """
    sonuc = {f"recall@{k}": 0.0 for k in ks} | {f"tam@{k}": 0.0 for k in ks} | {"mrr": 0.0}
    for sid, kumeler in hedef.items():
        siralar = [_sira(siralamalar[sid], kume) for kume in kumeler]
        for k in ks:
            sonuc[f"recall@{k}"] += sum(r < k for r in siralar) / len(siralar)
            sonuc[f"tam@{k}"] += all(r < k for r in siralar)
        sonuc["mrr"] += 1 / (min(siralar) + 1)
    return {ad: deger / len(hedef) for ad, deger in sonuc.items()}


def kacirilanlar(siralamalar: dict, hedef: dict, k: int = 5) -> list:
    """İlk k'da en az bir kaynağı bulunamayan sorular."""
    return [sid for sid, kumeler in hedef.items() if any(_sira(siralamalar[sid], km) >= k for km in kumeler)]
