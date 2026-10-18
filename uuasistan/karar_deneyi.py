"""Netleştirme kararının hızlı ölçümü: her sorunun ilk turunda yalnızca karar adımı çalışır, cevap üretilmez.

Beklenen: "netlestirme_sorar" etiketli sorularda soru sorulur; diğer bütün sorularda sorulmaz.

Kullanım (Colab, GPU, vLLM):
  python -m uuasistan.karar_deneyi --model qwen3-30b-a3b
"""
import argparse
import json

from . import KOK
from .cevap import DIL_MODELLERI, PARCA_SAYISI, gercek_asistan, karar_mesajlari, netlestirme_gerekli


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(DIL_MODELLERI), default="qwen3-30b-a3b")
    args = ap.parse_args()

    sorular = json.loads((KOK / "eval" / "test_seti.json").read_text("utf-8"))
    asistan = gercek_asistan(args.model)
    dogru_sordu, yanlis_sordu, kacirdi = [], [], []
    for s in sorular:
        diyalog = [{"rol": "ogrenci", "metin": s["soru"]}]
        secilen = [asistan.parcalar[i] for i in asistan.getir(s["soru"])[:PARCA_SAYISI]]
        k, gerekce = asistan.karar(karar_mesajlari(diyalog, secilen))
        sordu = netlestirme_gerekli(k, diyalog)
        beklenen = "netlestirme_sorar" in s.get("beklenen_davranis", [])
        (dogru_sordu if sordu and beklenen else yanlis_sordu if sordu else kacirdi if beklenen else []).append(s["id"])
        print(f"{s['id']} {'SORDU ' if sordu else 'sormadı'} karar={k:<12} beklenen={'sor' if beklenen else '-'} | {gerekce[:150]!r}")
    n_sor = sum("netlestirme_sorar" in s.get("beklenen_davranis", []) for s in sorular)
    print(f"\nSorması gerekenlerde sordu: {len(dogru_sordu)}/{n_sor}  kaçırdı: {kacirdi}")
    print(f"Sormaması gerekenlerde sordu: {len(yanlis_sordu)}/{len(sorular) - n_sor}  {yanlis_sordu}")


if __name__ == "__main__":
    main()
