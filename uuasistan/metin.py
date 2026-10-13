"""PDF'ten metin çıkarma ve temizleme.

PyMuPDF kullanılır: pypdf bu PDF'lerde Türkçe karakterlerin etrafında kelimeleri
bölüyordu ("giri ş", "öğr encilerin"); PyMuPDF bu kırıkları üretmiyor.
"""
import re
from pathlib import Path

import pymupdf

# Bazı PDF'lerin (ör. 61283) yazı tipi eşlemesi bozuk; bu karakterler Türkçe metinde başka türlü geçmez.
KARAKTER_DUZELTME = str.maketrans({"Ġ": "İ", "ġ": "Ş", "Ģ": "ş", "": "•", "\xa0": " "})

# Sayfa geçişlerinde metne karışan Senato eki başlıkları
SAYFA_BASLIGI = re.compile(r"(?i)^senato\s+(karar|evrak)\s+eki(dir)?$")


def pdf_metni(yol: Path) -> str:
    """PDF'i sayfa sayfa okur; sayfa başı numaralarını ve Senato eki başlıklarını atar."""
    sayfalar = []
    with pymupdf.open(yol) as belge:
        for sayfa in belge:
            satirlar = [s.rstrip() for s in sayfa.get_text().splitlines()]
            dolu = [i for i, s in enumerate(satirlar) if s.strip()]
            # Sayfa numarası yalnızca sayfanın ilk dolu satırında görülüyor (167577, 167135)
            if dolu and re.fullmatch(r"\d{1,3}", satirlar[dolu[0]].strip()):
                satirlar[dolu[0]] = ""
            satirlar = [s for s in satirlar if not SAYFA_BASLIGI.match(s.strip())]
            sayfalar.append("\n".join(satirlar))
    return "\n".join(sayfalar)


def temizle(metin: str) -> str:
    metin = metin.translate(KARAKTER_DUZELTME)
    # PyMuPDF bazen madde başını üç satıra böler: "MADDE\n1\n– (1)"
    metin = re.sub(r"(?i)\b(madde)[ \t]*\n[ \t]*(\d+)[ \t]*\n[ \t]*([-–])", r"\1 \2 \3", metin)
    satirlar = [re.sub(r"[ \t]+", " ", s).strip() for s in metin.splitlines()]
    metin = "\n".join(satirlar)
    return re.sub(r"\n{3,}", "\n\n", metin).strip() + "\n"
