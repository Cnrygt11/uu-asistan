"""Adım 2 arama deneyi: BM25, yoğun modeller, hibrit (RRF) ve yeniden sıralama karşılaştırması.

Kullanım:
  python -m uuasistan.deney                     # mümkün olan her şey (sentence-transformers yoksa yalnızca BM25)
  python -m uuasistan.deney --yogun bge-m3 me5-large
  python -m uuasistan.deney --cikti eval/sonuclar/adim2.json
"""
import argparse
import datetime as dt
import gc
import json
import subprocess
import time
import traceback
from pathlib import Path

from . import KOK
from .arama import BM25, YENIDEN_SIRALAYICILAR, YOGUN_MODELLER, Yogun, YenidenSiralayici, rrf
from .degerlendirme import hedefler, kacirilanlar, metrikler, sorgu_metni, yukle

DERINLIK = 50
YENIDEN_SIRALAMA_ADAY = 30


def _st_var() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _gpu_bosalt() -> None:
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _git_surumu() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=KOK, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yogun", nargs="*", default=None, help=f"yoğun modeller (varsayılan: hepsi): {', '.join(YOGUN_MODELLER)}")
    ap.add_argument("--yeniden", nargs="*", default=None, help=f"yeniden sıralayıcılar (varsayılan: hepsi): {', '.join(YENIDEN_SIRALAYICILAR)}")
    ap.add_argument("--cihaz", default=None, help="cuda / cpu (varsayılan: otomatik)")
    ap.add_argument("--cikti", default=None, help="sonuçların yazılacağı JSON dosyası")
    args = ap.parse_args()

    parcalar, sorular = yukle()
    metinler = [p["arama_metni"] for p in parcalar]
    hedef = hedefler(sorular, parcalar)
    sorgular = {s["id"]: sorgu_metni(s) for s in sorular if s["id"] in hedef}
    idler = list(sorgular)
    print(f"{len(parcalar)} parça, {len(hedef)} soru (kapsam dışılar hariç)\n")

    sonuclar, siralamalar, hatalar = {}, {}, {}

    def kaydet(ad: str, sir: dict, sure: float) -> None:
        siralamalar[ad] = sir
        m = metrikler(sir, hedef)
        sonuclar[ad] = m | {"sure_sn": round(sure, 1), "kacirilan@5": kacirilanlar(sir, hedef)}
        print(f"  {ad:45} recall@5={m['recall@5']:.3f}  mrr={m['mrr']:.3f}  ({sure:.1f} sn)")

    print("BM25")
    for kok in (None, "onek5", "snowball"):
        t = time.time()
        bm = BM25(metinler, kok)
        kaydet(f"bm25[{kok or 'kok-yok'}]", {sid: bm.ara(q, DERINLIK) for sid, q in sorgular.items()}, time.time() - t)
    en_iyi_bm25 = max((a for a in sonuclar if a.startswith("bm25")), key=lambda a: sonuclar[a]["recall@5"])

    yogunlar = []
    if not _st_var():
        print("\nsentence-transformers kurulu değil: yoğun modeller ve yeniden sıralama atlandı.")
    else:
        print("\nYoğun (embedding)")
        for anahtar in args.yogun if args.yogun is not None else YOGUN_MODELLER:
            ad = f"yogun[{anahtar}]"
            try:
                t = time.time()
                y = Yogun(metinler, YOGUN_MODELLER[anahtar], cihaz=args.cihaz)
                sir = dict(zip(idler, y.ara_toplu([sorgular[i] for i in idler], DERINLIK)))
                kaydet(ad, sir, time.time() - t)
                yogunlar.append(ad)
            except Exception as e:  # bir modelin hatası (indirme, bellek) deneyi durdurmasın
                hatalar[ad] = f"{type(e).__name__}: {e}"
                print(f"  {ad:45} HATA: {hatalar[ad][:120]}")
                traceback.print_exc(limit=1)
            finally:
                y = None
                _gpu_bosalt()

    if yogunlar:
        print(f"\nHibrit (RRF: {en_iyi_bm25} + yoğun)")
        for yad in yogunlar:
            sir = {sid: rrf([siralamalar[en_iyi_bm25][sid], siralamalar[yad][sid]], derinlik=DERINLIK) for sid in idler}
            kaydet(f"hibrit[{en_iyi_bm25}+{yad}]", sir, 0.0)

        taban = max((a for a in sonuclar if a.startswith(("hibrit", "yogun"))), key=lambda a: sonuclar[a]["recall@5"])
        print(f"\nYeniden sıralama (ilk {YENIDEN_SIRALAMA_ADAY} aday: {taban})")
        for anahtar in args.yeniden if args.yeniden is not None else YENIDEN_SIRALAYICILAR:
            ad = f"yeniden[{anahtar}]({taban})"
            try:
                t = time.time()
                ys = YenidenSiralayici(YENIDEN_SIRALAYICILAR[anahtar], cihaz=args.cihaz)
                sir = {sid: ys.sirala(sorgular[sid], siralamalar[taban][sid][:YENIDEN_SIRALAMA_ADAY], metinler) for sid in idler}
                kaydet(ad, sir, time.time() - t)
            except Exception as e:
                hatalar[ad] = f"{type(e).__name__}: {e}"
                print(f"  {ad:45} HATA: {hatalar[ad][:120]}")
            finally:
                ys = None
                _gpu_bosalt()

    print("\n## Sonuçlar (recall@5'e göre)\n")
    print("| yöntem | recall@1 | recall@3 | recall@5 | recall@10 | tam@5 | MRR | süre (sn) |")
    print("|---|---|---|---|---|---|---|---|")
    for ad, m in sorted(sonuclar.items(), key=lambda x: (-x[1]["recall@5"], -x[1]["mrr"])):
        print(f"| {ad} | {m['recall@1']:.3f} | {m['recall@3']:.3f} | {m['recall@5']:.3f} | {m['recall@10']:.3f} "
              f"| {m['tam@5']:.3f} | {m['mrr']:.3f} | {m['sure_sn']} |")
    en_iyi = max(sonuclar, key=lambda a: sonuclar[a]["recall@5"])
    print(f"\nEn iyi: {en_iyi}  |  ilk 5'te kaçırılan sorular: {sonuclar[en_iyi]['kacirilan@5']}")
    if hatalar:
        print("Hatalar:", json.dumps(hatalar, ensure_ascii=False, indent=2))

    if args.cikti:
        yol = KOK / args.cikti
        yol.parent.mkdir(parents=True, exist_ok=True)
        rapor = {
            "tarih": dt.datetime.now().isoformat(timespec="seconds"),
            "kod_surumu": _git_surumu(),
            "test_seti": "eval-v1",
            "parca_sayisi": len(parcalar),
            "soru_sayisi": len(hedef),
            "sonuclar": sonuclar,
            "hatalar": hatalar,
        }
        with open(yol, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rapor, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\nRapor: {yol}")


if __name__ == "__main__":
    main()
