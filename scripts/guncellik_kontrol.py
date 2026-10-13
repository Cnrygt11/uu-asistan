"""Resmî Gazete'de yayımlanan yönetmeliklerin güncelliğini kontrol eder.

mevzuat.gov.tr'deki konsolide metnin değişiklik notlarını ("Değişik:RG-18/8/2024-32636")
depodaki metinle karşılaştırır. Yeni bir değişiklik varsa çıkış kodu 1 olur: KAYSIS'ten
güncel PDF indirilip `python -m uuasistan.hazirla` çalıştırılmalı ve test seti gözden
geçirilmelidir.

Senato yönergeleri mevzuat.gov.tr'de yayımlanmadığı için yalnızca `mevzuat_gov_tr`
alanı olan belgeler kontrol edilir.

Kullanım: python scripts/guncellik_kontrol.py   (her dönem başında çalıştırın)
"""
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from uuasistan import DATA  # noqa: E402
from uuasistan.metin import pdf_metni, temizle  # noqa: E402

URL = "https://www.mevzuat.gov.tr/File/GeneratePdf?mevzuatNo={mevzuatNo}&mevzuatTur={mevzuatTur}&mevzuatTertip={mevzuatTertip}"
RG = re.compile(r"RG-\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d+)")


def rg_notlari(metin: str) -> set:
    return {f"{tarih}-{sayi}" for tarih, sayi in RG.findall(metin)}


def main() -> int:
    belgeler = json.loads((DATA / "belgeler.json").read_text("utf-8"))
    sorun = False
    for b in belgeler:
        if "mevzuat_gov_tr" not in b:
            continue
        istek = urllib.request.Request(URL.format(**b["mevzuat_gov_tr"]), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(istek, timeout=90) as yanit, tempfile.TemporaryDirectory() as d:
            yol = Path(d) / "belge.pdf"
            yol.write_bytes(yanit.read())
            resmi = rg_notlari(temizle(pdf_metni(yol)))
        yerel = rg_notlari((DATA / b["metin"]).read_text("utf-8"))
        yeni, eksik = resmi - yerel, yerel - resmi
        durum = "GÜNCEL" if not yeni and not eksik else "FARK VAR"
        print(f"{b['id']:5} {durum:9} değişiklikler: {sorted(resmi) or 'yok'}")
        if yeni:
            print(f"      mevzuat.gov.tr'de olup depoda olmayan: {sorted(yeni)}")
        if eksik:
            print(f"      depoda olup mevzuat.gov.tr'de olmayan: {sorted(eksik)}")
        sorun |= bool(yeni or eksik)
    return 1 if sorun else 0


if __name__ == "__main__":
    sys.exit(main())
