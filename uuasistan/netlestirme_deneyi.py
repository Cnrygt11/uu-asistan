"""Arama ve netleştirme kararının hızlı ölçümü; dil modeli yüklenmez (Colab, GPU, ~3 dk).

1. Arama: doğru parçanın ilk k sonuçta bulunma oranı. Parçalama değiştiği için (koşula bağlı fıkralar
   ayrı parça) Adım 2'nin ölçümü aynı sorgularla yeniden yapılır.
2. Netleştirme: her sorunun ilk turunda karar. "netlestirme_sorar" etiketli sorularda sorulmalı,
   "netlestirme_sormaz" etiketlilerde (öğrenci bilgiyi vermiş) sorulmamalı; diğerlerinde de beklenmez.

Kullanım: python -m uuasistan.netlestirme_deneyi
"""
from .cevap import arama_kur, kosul_kurallari, netlestirme_konusu
from .degerlendirme import hedefler, metrikler, sorgu_metni, yukle

# Adım 2, eski parçalama (eval/sonuclar/adim2_v2_colab.json, turkish-e5-large + modernbert-tr-reranker)
ADIM2 = {"recall@1": 0.694, "recall@3": 0.815, "recall@5": 0.905, "recall@10": 0.941, "mrr": 0.851}


def main() -> None:
    _, sorular = yukle()
    parcalar, getir = arama_kur()
    hedef = hedefler(sorular, parcalar)
    kurallar = kosul_kurallari()

    siralamalar, sordu = {}, {}
    for s in sorular:
        siralamalar[s["id"]] = getir(sorgu_metni(s))
        ilk = [parcalar[i] for i in getir(s["soru"])[:3]]
        sordu[s["id"]] = netlestirme_konusu([{"rol": "ogrenci", "metin": s["soru"]}], ilk[0], kurallar)
        davranis = s.get("beklenen_davranis", [])
        beklenen = "sor" if "netlestirme_sorar" in davranis else "sorma" if "netlestirme_sormaz" in davranis else "-"
        print(f"{s['id']} {'SORDU' if sordu[s['id']] else '-':5} beklenen={beklenen:5} {sordu[s['id']] or '':24} ilk3={[p['id'] for p in ilk]}")

    m = metrikler({k: v for k, v in siralamalar.items() if k in hedef}, hedef)
    print("\nArama (yeni parçalama):", {k: round(v, 3) for k, v in m.items() if k in ADIM2})
    print("Arama (Adım 2, eski):  ", ADIM2)
    for etiket, ad in (("netlestirme_sorar", "Sorması gerekenlerde sordu"), ("netlestirme_sormaz", "Bilgiyi verenlerde sordu")):
        grup = [s["id"] for s in sorular if etiket in s.get("beklenen_davranis", [])]
        evet = [i for i in grup if sordu[i]]
        print(f"{ad}: {len(evet)}/{len(grup)}  sordu={evet}  sormadı={[i for i in grup if not sordu[i]]}")
    diger = [s["id"] for s in sorular if not {"netlestirme_sorar", "netlestirme_sormaz"} & set(s.get("beklenen_davranis", []))]
    print(f"Diğer sorularda sordu: {sum(bool(sordu[i]) for i in diger)}/{len(diger)}  {[i for i in diger if sordu[i]]}")


if __name__ == "__main__":
    main()
