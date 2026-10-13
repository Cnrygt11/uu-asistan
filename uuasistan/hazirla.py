"""Belge hazırlama hattı: PDF -> temiz metin -> madde bazlı parçalar.

Çıktılar:
  data/text/kaysis/<id>.txt   tüm belgelerin temiz metni (test seti doğrulaması bunu kullanır)
  data/parcalar.jsonl         indekslenecek parçalar (yalnızca v1 kapsamı, süresi dolmuşlar hariç)

Kullanım: python -m uuasistan.hazirla
"""
import json
from pathlib import Path

from . import DATA
from .metin import pdf_metni, temizle
from .parcalama import degisiklikler, madde_parcalari, maddelere_ayir

INDEKS_KAPSAMI = {"v1", "v1-ikincil"}
CIKTI = DATA / "parcalar.jsonl"


def katalog() -> list:
    return json.loads((DATA / "belgeler.json").read_text("utf-8"))


def madde_durumlari() -> dict:
    durum = json.loads((DATA / "madde_durumu.json").read_text("utf-8"))
    return {(m["belge"], m["madde"]): m for m in durum["maddeler"]}


def belge_maddeleri(belge: dict) -> list:
    return maddelere_ayir((DATA / belge["metin"]).read_text("utf-8"))


def parcalar_uret(belge: dict, durumlar: dict) -> tuple:
    """(parcalar, dislananlar)"""
    parcalar, dislananlar = [], []
    for madde in belge_maddeleri(belge):
        d = durumlar.get((belge["id"], madde.etiket))
        if d and d["durum"] == "suresi_dolmus":
            dislananlar.append(f"{belge['id']} {madde.etiket} (süresi dolmuş)")
            continue
        bolumler = madde_parcalari(madde)
        kok_id = f"{belge['id']}-{'g' if madde.gecici else 'm'}{madde.no}"
        for k, (fikralar, metin) in enumerate(bolumler, 1):
            baslik_satiri = f"{belge['ad']} — Madde {madde.etiket}" + (f": {madde.baslik}" if madde.baslik else "")
            parca = {
                "id": kok_id if len(bolumler) == 1 else f"{kok_id}-p{k}",
                "belge": belge["id"],
                "belge_adi": belge["ad"],
                "madde": madde.etiket,
                "baslik": madde.baslik,
                "bolum": madde.bolum,
                "fikralar": fikralar,
                "parca": [k, len(bolumler)],
                "metin": metin,
                "arama_metni": f"{baslik_satiri}\n{metin}",
                "degisiklikler": degisiklikler(metin),
                "kaynak_url": belge["kaynak_url"],
            }
            if belge.get("guncellik"):
                parca["guncellik"] = belge["guncellik"]
            if d and d["durum"] == "sureli":
                parca["kayit_yili_en_gec"] = d["kayit_yili_en_gec"]
            parcalar.append(parca)
    return parcalar, dislananlar


def main() -> None:
    durumlar = madde_durumlari()
    tum, dislanan = [], []
    print(f"{'belge':8} {'madde':>5} {'parça':>5}  kapsam")
    for belge in katalog():
        ham = DATA / belge["ham"]
        hedef = DATA / belge["metin"]
        hedef.write_text(temizle(pdf_metni(ham)), "utf-8")
        if belge.get("kapsam") not in INDEKS_KAPSAMI:
            dislanan.append(f"{belge['id']} (kapsam {belge.get('kapsam')})")
            print(f"{belge['id']:8} {'-':>5} {'-':>5}  {belge.get('kapsam')} (indekslenmez)")
            continue
        parcalar, d = parcalar_uret(belge, durumlar)
        tum.extend(parcalar)
        dislanan.extend(d)
        print(f"{belge['id']:8} {len(belge_maddeleri(belge)):5} {len(parcalar):5}  {belge.get('kapsam')}")

    with CIKTI.open("w", encoding="utf-8", newline="\n") as f:
        for p in tum:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    uzunluklar = sorted(len(p["metin"]) for p in tum)
    print(f"\n{len(tum)} parça -> {CIKTI.relative_to(DATA.parent)}")
    print(f"parça uzunluğu (karakter): min {uzunluklar[0]}, medyan {uzunluklar[len(uzunluklar) // 2]}, max {uzunluklar[-1]}")
    print("dışlananlar:", ", ".join(dislanan))


if __name__ == "__main__":
    main()
