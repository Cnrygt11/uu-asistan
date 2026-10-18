"""Adım 3 üretim deneyi: test setindeki her soruyu asistana sorar, cevapları ve süreleri kaydeder.

Netleştirmeli sorularda iki tur çalışır: önce soru, sonra test setindeki öğrenci yanıtı.
Otomatik ölçümler kabadır (getirme, madde atfı, netleştirme sorusu); içerik doğruluğu
cevaplar okunarak değerlendirilir.

Kullanım (Colab, GPU, vLLM):
  python -m uuasistan.uretim --model qwen3-30b-a3b --cikti eval/sonuclar/adim3_qwen3-30b-a3b.jsonl
  python -m uuasistan.uretim --model qwen3-8b --sinir 3     # hızlı deneme
"""
import argparse
import json
import statistics

from . import KOK
from .cevap import DIL_MODELLERI, PARCA_SAYISI, atif_yapilan_maddeler, gercek_asistan
from .degerlendirme import hedefler


def calistir(asistan, sorular: list) -> list:
    hedef = hedefler(sorular, asistan.parcalar)
    konum = {id(p): i for i, p in enumerate(asistan.parcalar)}
    kayitlar = []
    for s in sorular:
        diyalog = [{"rol": "ogrenci", "metin": s["soru"]}]
        cevap1, parcalar, olcum = asistan.cevapla(diyalog)
        kayit = {"id": s["id"], "kategori": s["kategori"], "soru": s["soru"], "tur1": cevap1, "olcum": [olcum]}
        n = s.get("netlestirme")
        if n:
            diyalog += [{"rol": "asistan", "metin": cevap1}, {"rol": "ogrenci", "metin": n["ogrenci_yaniti"]}]
            kayit["ogrenci_yaniti"] = n["ogrenci_yaniti"]
            kayit["tur2"], parcalar, olcum = asistan.cevapla(diyalog)
            kayit["olcum"].append(olcum)
        son = kayit.get("tur2", cevap1)
        kayit["parcalar"] = [p["id"] for p in parcalar]
        if s["id"] in hedef:
            verilen = {konum[id(p)] for p in parcalar if id(p) in konum}  # eski yönerge parçaları dizinde değil
            kayit["getirildi"] = [bool(kume & verilen) for kume in hedef[s["id"]]]
            altin = {str(k["madde"]) for k in s["kaynaklar"]}
            kayit["dogru_madde_atfi"] = bool(atif_yapilan_maddeler(son) & altin)
        davranis = s.get("beklenen_davranis", [])
        if "netlestirme_sorar" in davranis or "netlestirme_sormaz" in davranis:
            kayit["ilk_turda_soru_sordu"] = "?" in cevap1
        kayitlar.append(kayit)
        print(f"{s['id']} ({sum(o['arama_sn'] + o.get('uretim_sn', 0) for o in kayit['olcum']):.1f} sn) {son[:100]!r}")
    return kayitlar


def hiz(olcumler: list) -> dict:
    """uretim_sn = a + b * token doğrusal uyumu: a ~ ilk token süresi (istem işleme), 1/b ~ token/sn.
    Akış (streaming) açıkken öğrencinin ilk kelimeyi görme süresi ~ arama + a.
    Netleştirme sorusu sorulan ölçümlerde cevap üretilmez; uyum yalnızca üretilen cevaplardan yapılır."""
    uretilen = [o for o in olcumler if "token" in o]
    x = [o["token"] for o in uretilen]
    y = [o["uretim_sn"] for o in uretilen]
    arama = statistics.median(o["arama_sn"] for o in olcumler)
    sonuc = {
        "arama_sn_medyan": round(arama, 2),
        "token_medyan": statistics.median(x),
        "toplam_sn_medyan": round(statistics.median(o["arama_sn"] + o.get("uretim_sn", 0) for o in olcumler), 1),
    }
    if len(set(x)) > 1:
        b, a = statistics.linear_regression(x, y)
        sonuc |= {"tahmini_ilk_kelime_sn": round(arama + a, 2), "token_per_sn": round(1 / b, 1) if b > 0 else None}
    return sonuc


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
        "hiz": hiz([o for k in kayitlar for o in k["olcum"]]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(DIL_MODELLERI), default="qwen3-8b")
    ap.add_argument("--cikti", default=None, help="cevapların yazılacağı JSONL dosyası")
    ap.add_argument("--sinir", type=int, default=None, help="yalnızca ilk N soru (hızlı deneme)")
    ap.add_argument("--tohum", type=int, default=0, help="örnekleme tohumu (koşudan koşuya değişkenliği ölçmek için)")
    args = ap.parse_args()

    sorular = json.loads((KOK / "eval" / "test_seti.json").read_text("utf-8"))[: args.sinir]
    asistan = gercek_asistan(args.model, tohum=args.tohum)
    kayitlar = calistir(asistan, sorular)
    o = ozet(kayitlar, sorular) | {"model": DIL_MODELLERI[args.model][0], "tarih": asistan.gun.isoformat(), "soru_sayisi": len(kayitlar), "tohum": args.tohum}
    print("\nÖzet:", json.dumps(o, ensure_ascii=False))
    if args.cikti:
        with open(KOK / args.cikti, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"ozet": o}, ensure_ascii=False) + "\n")
            for k in kayitlar:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print("Kayıt:", KOK / args.cikti)


if __name__ == "__main__":
    main()
