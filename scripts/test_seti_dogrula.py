"""Test setinin şemasını ve her kaynağın belge metninde gerçekten bulunduğunu doğrular.

Kontroller:
  - zorunlu alanlar ve izin verilen değerler
  - davranış etiketlerinin tutarlılığı (ör. kapsam_disi -> bilgi_yok_der)
  - beklenen_cevap'a puanlama talimatı sızmamış olması
  - belge kimliği data/belgeler.json'da var mı
  - madde numarası belge metninde geçiyor mu
  - alıntı, o maddenin metninde birebir geçiyor mu (boşluklar yok sayılarak;
    PDF'ten çıkan "öğr encilerin" gibi kırılmalar sorun olmasın diye)

Kullanım: python scripts/test_seti_dogrula.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DATA = KOK / "data"
TEST_SETI = KOK / "eval" / "test_seti.json"

KATEGORILER = {
    "olgusal", "sayisal", "kosullu", "coklu_kaynak",
    "guncel_degisiklik", "celiski", "kapsam_disi", "ingilizce",
}
NETLESTIRME_KONULARI = {"fakulte", "kayit_yili"}
DAVRANISLAR = {
    "netlestirme_sorar", "netlestirme_sormaz", "bilgi_yok_der",
    "uydurmaz", "guncellik_uyarisi", "yonlendirir",
}
ZORLUKLAR = {"kolay", "orta", "zor"}
KAYNAK_TIPLERI = {"sentetik", "gercek"}
ZORUNLU = ["id", "soru", "beklenen_cevap", "kaynaklar", "kategori", "zorluk", "kaynak_tipi", "dogrulandi"]
# Kategoriye göre zorunlu davranış etiketi
KATEGORI_DAVRANIS = {"kapsam_disi": "bilgi_yok_der", "celiski": "guncellik_uyarisi"}
# "Sistem ... uydurmamalı" gibi puanlama talimatları beklenen_cevap'a değil beklenen_davranis'a yazılır
TALIMAT_SIZINTISI = re.compile(r"(?i)\b(sistem|model)\b[^.]*\w(malı|meli)(dır|dir)?\b")


def bosluksuz(metin: str) -> str:
    return re.sub(r"\s+", "", metin).casefold()


def madde_deseni(madde: str) -> str:
    if madde.lower().startswith("geçici"):
        return rf"GEÇİCİ\s*MADDE\s*{madde.split()[-1]}\b"
    return rf"(?i)(?<!GEÇİCİ\s)\bmadde\s*[-–]?\s*{madde}\s*[-–(]"


def madde_var_mi(metin: str, madde: str) -> bool:
    return re.search(madde_deseni(madde), metin) is not None


def madde_metni(metin: str, madde: str) -> str:
    """Maddenin başından bir sonraki maddenin başına kadar olan kısım."""
    m = re.search(madde_deseni(madde), metin)
    if not m:
        return ""
    sonraki = re.search(r"(?i)\bmadde\s*[-–]?\s*\d+\s*[-–(]", metin[m.end():])
    return metin[m.start(): m.end() + sonraki.start()] if sonraki else metin[m.start():]


def main() -> int:
    belgeler = {b["id"]: b for b in json.loads((DATA / "belgeler.json").read_text("utf-8"))}
    metinler = {bid: (DATA / b["metin"]).read_text("utf-8") for bid, b in belgeler.items()}
    sorular = json.loads(TEST_SETI.read_text("utf-8"))

    hatalar = []
    idler = Counter(s["id"] for s in sorular)
    for sid, n in idler.items():
        if n > 1:
            hatalar.append(f"{sid}: id {n} kez tekrarlanıyor")

    for s in sorular:
        sid = s.get("id", "?")
        eksik = [a for a in ZORUNLU if a not in s]
        if eksik:
            hatalar.append(f"{sid}: eksik alan(lar) {eksik}")
            continue
        if s["kategori"] not in KATEGORILER:
            hatalar.append(f"{sid}: bilinmeyen kategori {s['kategori']!r}")
        if s["zorluk"] not in ZORLUKLAR:
            hatalar.append(f"{sid}: bilinmeyen zorluk {s['zorluk']!r}")
        if s["kaynak_tipi"] not in KAYNAK_TIPLERI:
            hatalar.append(f"{sid}: bilinmeyen kaynak_tipi {s['kaynak_tipi']!r}")
        if TALIMAT_SIZINTISI.search(s["beklenen_cevap"]):
            hatalar.append(f"{sid}: beklenen_cevap puanlama talimatı içeriyor; bunu beklenen_davranis'a taşıyın")

        davranis = s.get("beklenen_davranis", [])
        if set(davranis) - DAVRANISLAR or len(davranis) != len(set(davranis)):
            hatalar.append(f"{sid}: geçersiz/tekrarlı beklenen_davranis {davranis}")
        if {"netlestirme_sorar", "netlestirme_sormaz"} <= set(davranis):
            hatalar.append(f"{sid}: netlestirme_sorar ve netlestirme_sormaz birlikte olamaz")
        gerekli = KATEGORI_DAVRANIS.get(s["kategori"])
        if gerekli and gerekli not in davranis:
            hatalar.append(f"{sid}: {s['kategori']} sorusunda {gerekli!r} davranışı zorunlu")

        n = s.get("netlestirme")
        if n is not None:
            if not isinstance(n, dict) or n.get("konu") not in NETLESTIRME_KONULARI \
                    or not n.get("ornek_soru") or not n.get("ogrenci_yaniti"):
                hatalar.append(f"{sid}: netlestirme {{konu, ornek_soru, ogrenci_yaniti}} olmalı")
        if (n is not None) != ("netlestirme_sorar" in davranis):
            hatalar.append(f"{sid}: netlestirme alanı ile 'netlestirme_sorar' davranışı birlikte olmalı")

        if s["kategori"] != "kapsam_disi" and not s.get("kaynaklar"):
            hatalar.append(f"{sid}: kaynak yok (kapsam_disi değilse en az bir kaynak gerekli)")
        for k in s.get("kaynaklar", []):
            bid = k["belge"]
            if bid not in belgeler:
                hatalar.append(f"{sid}: bilinmeyen belge {bid!r}")
                continue
            metin = metinler[bid]
            madde = str(k["madde"])
            if not madde_var_mi(metin, madde):
                hatalar.append(f"{sid}: {bid} içinde madde {madde} bulunamadı")
            elif bosluksuz(k["alinti"]) not in bosluksuz(madde_metni(metin, madde)):
                yer = "başka bir maddede" if bosluksuz(k["alinti"]) in bosluksuz(metin) else "belgede hiç"
                hatalar.append(f"{sid}: {bid} m.{madde} alıntısı bu maddede yok ({yer} geçiyor): {k['alinti']!r}")

    # Geçici maddelerin durumu: listedeki maddeler gerçekten var mı, test seti süresi dolmuşa dayanıyor mu
    durum = json.loads((DATA / "madde_durumu.json").read_text("utf-8"))
    dolmus, sureli = set(), set()
    for m in durum["maddeler"]:
        if m["durum"] == "sureli":
            sureli.add((m["belge"], m["madde"]))
        if m["belge"] not in belgeler or not madde_var_mi(metinler[m["belge"]], m["madde"]):
            hatalar.append(f"madde_durumu: {m['belge']} {m['madde']} belgede bulunamadı")
        if m["durum"] not in {"suresi_dolmus", "sureli"}:
            hatalar.append(f"madde_durumu: {m['belge']} {m['madde']} bilinmeyen durum {m['durum']!r}")
        if m["durum"] == "suresi_dolmus":
            dolmus.add((m["belge"], m["madde"]))
    for s in sorular:
        for k in s.get("kaynaklar", []):
            if (k["belge"], str(k["madde"])) in dolmus:
                hatalar.append(f"{s['id']}: süresi dolmuş maddeye dayanıyor ({k['belge']} {k['madde']})")
        # Kayıt yılı yalnızca cevabı süreli bir geçici madde değiştiriyorsa sorulur
        if (s.get("netlestirme") or {}).get("konu") == "kayit_yili" and \
                not any((k["belge"], str(k["madde"])) in sureli for k in s.get("kaynaklar", [])):
            hatalar.append(f"{s['id']}: kayıt yılı soruluyor ama süreli bir geçici maddeye dayanmıyor")

    sayim = Counter(s["kategori"] for s in sorular)
    print(f"{len(sorular)} soru | " + ", ".join(f"{k}={v}" for k, v in sorted(sayim.items())))
    davranis_sayim = Counter(d for s in sorular for d in s.get("beklenen_davranis", []))
    print("davranış etiketleri | " + ", ".join(f"{k}={v}" for k, v in sorted(davranis_sayim.items())))
    print(f"doğrulanmış (insan kontrolü): {sum(s.get('dogrulandi', False) for s in sorular)}/{len(sorular)}")
    if hatalar:
        print(f"\n{len(hatalar)} HATA:")
        for h in hatalar:
            print("  -", h)
        return 1
    print("Şema geçerli; tüm kaynaklar ve alıntılar belge metinlerinde bulundu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
