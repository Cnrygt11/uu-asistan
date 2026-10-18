"""Belge hazırlama hattı: PDF -> temiz metin -> madde bazlı parçalar.

Çıktılar:
  data/text/kaysis/<id>.txt   tüm belgelerin temiz metni (test seti doğrulaması bunu kullanır)
  data/parcalar.jsonl         indekslenecek parçalar (yalnızca v1 kapsamı, süresi dolmuşlar hariç)
  data/eski_parcalar.jsonl    aramaya girmeyen, yalnızca koşulu sağlayan öğrenciye verilen parçalar (bagli_kullanim)

Kullanım: python -m uuasistan.hazirla
"""
import json
from pathlib import Path

from . import DATA
from .metin import pdf_metni, temizle
from .parcalama import degisiklikler, madde_parcalari, maddelere_ayir

INDEKS_KAPSAMI = {"v1", "v1-ikincil"}
CIKTI = DATA / "parcalar.jsonl"
ESKI_CIKTI = DATA / "eski_parcalar.jsonl"


def katalog() -> list:
    return json.loads((DATA / "belgeler.json").read_text("utf-8"))


def madde_durumlari() -> dict:
    durum = json.loads((DATA / "madde_durumu.json").read_text("utf-8"))
    return {(m["belge"], m["madde"]): m for m in durum["maddeler"]}


def ayri_fikralar() -> dict:
    """{(belge, madde): {fıkra no}}: koşula bağlı fıkralar ayrı parça olur (data/kosullar.json)."""
    sonuc = {}
    for k in json.loads((DATA / "kosullar.json").read_text("utf-8"))["kurallar"]:
        if "fikra" in k:
            sonuc.setdefault((k["belge"], k["madde"]), set()).add(k["fikra"])
    return sonuc


def belge_maddeleri(belge: dict) -> list:
    return maddelere_ayir((DATA / belge["metin"]).read_text("utf-8"))


def parcalar_uret(belge: dict, durumlar: dict, ayri: dict | None = None) -> tuple:
    """(parcalar, dislananlar)"""
    ayri = ayri or {}
    parcalar, dislananlar = [], []
    for madde in belge_maddeleri(belge):
        d = durumlar.get((belge["id"], madde.etiket))
        if d and d["durum"] == "suresi_dolmus":
            dislananlar.append(f"{belge['id']} {madde.etiket} (süresi dolmuş)")
            continue
        bolumler = madde_parcalari(madde, ayri=frozenset(ayri.get((belge["id"], madde.etiket), ())))
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
            if belge.get("bagli_kullanim"):
                parca["uygulama_kosulu"] = belge["bagli_kullanim"]
            if d and d["durum"] == "sureli":
                parca["kayit_yili_en_gec"] = d["kayit_yili_en_gec"]
            parcalar.append(parca)
    return parcalar, dislananlar


def main() -> None:
    durumlar, ayri = madde_durumlari(), ayri_fikralar()
    tum, dislanan, eski = [], [], []
    print(f"{'belge':8} {'madde':>5} {'parça':>5}  kapsam")
    for belge in katalog():
        ham = DATA / belge["ham"]
        hedef = DATA / belge["metin"]
        hedef.write_text(temizle(pdf_metni(ham)), "utf-8", newline="\n")
        if belge.get("kapsam") not in INDEKS_KAPSAMI:
            if belge.get("bagli_kullanim"):
                eski.extend(parcalar_uret(belge, durumlar)[0])
            dislanan.append(f"{belge['id']} (kapsam {belge.get('kapsam')})")
            print(f"{belge['id']:8} {'-':>5} {'-':>5}  {belge.get('kapsam')} (indekslenmez)")
            continue
        parcalar, d = parcalar_uret(belge, durumlar, ayri)
        tum.extend(parcalar)
        dislanan.extend(d)
        print(f"{belge['id']:8} {len(belge_maddeleri(belge)):5} {len(parcalar):5}  {belge.get('kapsam')}")

    for dosya, liste in ((CIKTI, tum), (ESKI_CIKTI, eski)):
        with dosya.open("w", encoding="utf-8", newline="\n") as f:
            for p in liste:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    uzunluklar = sorted(len(p["metin"]) for p in tum)
    print(f"\n{len(tum)} parça -> {CIKTI.relative_to(DATA.parent)}")
    print(f"parça uzunluğu (karakter): min {uzunluklar[0]}, medyan {uzunluklar[len(uzunluklar) // 2]}, max {uzunluklar[-1]}")
    print(f"{len(eski)} bağlı kullanım parçası -> {ESKI_CIKTI.relative_to(DATA.parent)}")
    print("dışlananlar:", ", ".join(dislanan))


if __name__ == "__main__":
    main()
