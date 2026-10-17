"""Adım 3 üretim deneyi: test setindeki her soruyu asistana sorar, cevapları kaydeder.

Netleştirmeli sorularda iki tur çalışır: önce soru, sonra test setindeki öğrenci yanıtı.
Otomatik ölçümler kabadır (getirme, madde atfı, netleştirme sorusu); içerik doğruluğu
cevaplar okunarak değerlendirilir.

Kullanım (Colab, GPU):
  python -m uuasistan.uretim --cikti eval/sonuclar/adim3_qwen3-8b.jsonl
  python -m uuasistan.uretim --sinir 3        # hızlı deneme
"""
import argparse
import json
import time

from . import KOK
from .cevap import DIL_MODELI, PARCA_SAYISI, atif_yapilan_maddeler, gercek_asistan
from .degerlendirme import hedefler


def calistir(asistan, sorular: list) -> list:
    hedef = hedefler(sorular, asistan.parcalar)
    konum = {id(p): i for i, p in enumerate(asistan.parcalar)}
    kayitlar = []
    for s in sorular:
        t = time.time()
        diyalog = [{"rol": "ogrenci", "metin": s["soru"]}]
        cevap1, parcalar = asistan.cevapla(diyalog)
        kayit = {"id": s["id"], "kategori": s["kategori"], "soru": s["soru"], "tur1": cevap1}
        n = s.get("netlestirme")
        if n:
            diyalog += [{"rol": "asistan", "metin": cevap1}, {"rol": "ogrenci", "metin": n["ogrenci_yaniti"]}]
            kayit["ogrenci_yaniti"] = n["ogrenci_yaniti"]
            kayit["tur2"], parcalar = asistan.cevapla(diyalog)
        son = kayit.get("tur2", cevap1)
        kayit["parcalar"] = [p["id"] for p in parcalar]
        if s["id"] in hedef:
            verilen = {konum[id(p)] for p in parcalar}
            kayit["getirildi"] = [bool(kume & verilen) for kume in hedef[s["id"]]]
            altin = {str(k["madde"]) for k in s["kaynaklar"]}
            kayit["dogru_madde_atfi"] = bool(atif_yapilan_maddeler(son) & altin)
        davranis = s.get("beklenen_davranis", [])
        if "netlestirme_sorar" in davranis or "netlestirme_sormaz" in davranis:
            kayit["ilk_turda_soru_sordu"] = "?" in cevap1
        kayit["sure_sn"] = round(time.time() - t, 1)
        kayitlar.append(kayit)
        print(f"{s['id']} ({kayit['sure_sn']} sn) {son[:100]!r}")
    return kayitlar


def ozet(kayitlar: list, sorular: list) -> dict:
    davranis = {s["id"]: s.get("beklenen_davranis", []) for s in sorular}
    g = [k for k in kayitlar if "getirildi" in k]
    sorar = [k for k in kayitlar if "netlestirme_sorar" in davranis[k["id"]]]
    sormaz = [k for k in kayitlar if "netlestirme_sormaz" in davranis[k["id"]]]
    return {
        f"getirme@{PARCA_SAYISI}": round(sum(sum(k["getirildi"]) / len(k["getirildi"]) for k in g) / len(g), 3),
        "dogru_madde_atfi": round(sum(k["dogru_madde_atfi"] for k in g) / len(g), 3),
        "netlestirme_sordu": f"{sum(k['ilk_turda_soru_sordu'] for k in sorar)}/{len(sorar)}",
        "gereksiz_netlestirme": f"{sum(k['ilk_turda_soru_sordu'] for k in sormaz)}/{len(sormaz)}",
        "ortalama_sure_sn": round(sum(k["sure_sn"] for k in kayitlar) / len(kayitlar), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default=None, help="cevapların yazılacağı JSONL dosyası")
    ap.add_argument("--sinir", type=int, default=None, help="yalnızca ilk N soru (hızlı deneme)")
    args = ap.parse_args()

    sorular = json.loads((KOK / "eval" / "test_seti.json").read_text("utf-8"))[: args.sinir]
    asistan = gercek_asistan()
    kayitlar = calistir(asistan, sorular)
    o = ozet(kayitlar, sorular) | {"model": DIL_MODELI, "tarih": asistan.gun.isoformat(), "soru_sayisi": len(kayitlar)}
    print("\nÖzet:", json.dumps(o, ensure_ascii=False))
    if args.cikti:
        with open(KOK / args.cikti, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ozet": o}, ensure_ascii=False) + "\n")
            for k in kayitlar:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print("Kayıt:", KOK / args.cikti)


if __name__ == "__main__":
    main()
