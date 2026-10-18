"""Arama, netleştirme kararı ve koşul notlarının hızlı ölçümü; dil modeli yüklenmez (Colab, GPU, ~3 dk).

1. Arama: doğru parçanın ilk k sonuçta bulunma oranı, sözlükle sorgu genişletme kapalı ve açık.
   Parçalama değiştiği için (koşula bağlı fıkralar ayrı parça) Adım 2'nin ölçümü aynı sorgularla yeniden yapılır.
2. Netleştirme: her sorunun ilk turunda karar. "netlestirme_sorar" etiketli sorularda sorulmalı,
   "netlestirme_sormaz" etiketlilerde (öğrenci bilgiyi vermiş) sorulmamalı; diğerlerinde de beklenmez.
3. Koşul notları: koşula bağlı sorularda (netleştirmelilerde öğrencinin yanıtıyla) modele hangi notların ve
   hangi eski yönerge parçalarının verileceği.

Kullanım: python -m uuasistan.netlestirme_deneyi
"""
import datetime as dt

from .arama import sozluk_genislet
from .cevap import PARCA_SAYISI, SORGU_GENISLETME, arama_kur
from .degerlendirme import hedefler, metrikler, sorgu_metni, yukle
from .kosul import NETLESTIRME_SORULARI, bagli_ekle, eski_parcalar, kosul_kurallari, kosul_notlari, netlestirme_konusu

# Adım 2, eski parçalama (eval/sonuclar/adim2_v2_colab.json, turkish-e5-large + modernbert-tr-reranker)
ADIM2 = {"recall@1": 0.694, "recall@3": 0.815, "recall@5": 0.905, "recall@10": 0.941, "mrr": 0.851}


def main() -> None:
    _, sorular = yukle()
    parcalar, getir = arama_kur()
    hedef = hedefler(sorular, parcalar)
    kurallar, eski, gun = kosul_kurallari(), eski_parcalar(), dt.date.today()
    sorgu = sozluk_genislet if SORGU_GENISLETME else str

    for ad, f in (("kapalı", str), ("açık", sozluk_genislet)):
        m = metrikler({s["id"]: getir(f(sorgu_metni(s))) for s in sorular if s["id"] in hedef}, hedef)
        print(f"Arama, sözlük genişletme {ad}:", {k: round(v, 3) for k, v in m.items() if k in ADIM2})
    print("Arama, Adım 2 (eski parçalama):  ", ADIM2, f"\nAsistanda sözlük genişletme: {'açık' if SORGU_GENISLETME else 'kapalı'}\n")

    sordu = {}
    for s in sorular:
        ilk = [parcalar[i] for i in getir(sorgu(s["soru"]))[:3]]
        sordu[s["id"]] = netlestirme_konusu([{"rol": "ogrenci", "metin": s["soru"]}], ilk[0], kurallar, gun)
        davranis = s.get("beklenen_davranis", [])
        beklenen = "sor" if "netlestirme_sorar" in davranis else "sorma" if "netlestirme_sormaz" in davranis else "-"
        print(f"{s['id']} {'SORDU' if sordu[s['id']] else '-':5} beklenen={beklenen:5} {sordu[s['id']] or '':24} ilk3={[p['id'] for p in ilk]}")
    for etiket, ad in (("netlestirme_sorar", "Sorması gerekenlerde sordu"), ("netlestirme_sormaz", "Bilgiyi verenlerde sordu")):
        grup = [s["id"] for s in sorular if etiket in s.get("beklenen_davranis", [])]
        evet = [i for i in grup if sordu[i]]
        print(f"{ad}: {len(evet)}/{len(grup)}  sordu={evet}  sormadı={[i for i in grup if not sordu[i]]}")
    diger = [s["id"] for s in sorular if not {"netlestirme_sorar", "netlestirme_sormaz"} & set(s.get("beklenen_davranis", []))]
    print(f"Diğer sorularda sordu: {sum(bool(sordu[i]) for i in diger)}/{len(diger)}  {[i for i in diger if sordu[i]]}\n")

    print("Koşul notları (koşula bağlı sorular; netleştirmelilerde öğrencinin yanıtıyla):")
    for s in sorular:
        n = s.get("netlestirme")
        diyalog = [{"rol": "ogrenci", "metin": s["soru"]}]
        if n:
            soru = NETLESTIRME_SORULARI.get(sordu[s["id"]] or n["konu"], n["ornek_soru"])
            diyalog += [{"rol": "asistan", "metin": soru}, {"rol": "ogrenci", "metin": n["ogrenci_yaniti"]}]
        secilen = [parcalar[i] for i in getir(sorgu(" ".join(m["metin"] for m in diyalog if m["rol"] == "ogrenci")))[:PARCA_SAYISI]]
        secilen = bagli_ekle(secilen, parcalar, kurallar)
        notlar, ekler = kosul_notlari(diyalog, secilen, kurallar, eski, gun)
        if notlar or ekler or n or "netlestirme_sormaz" in s.get("beklenen_davranis", []):
            print(f"{s['id']}: notlar={notlar or '-'} eski={[e['id'] for e in ekler] or '-'}")


if __name__ == "__main__":
    main()
