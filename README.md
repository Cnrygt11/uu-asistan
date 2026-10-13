# UÜ Asistan

Bursa Uludağ Üniversitesi önlisans ve lisans öğrencilerinin eğitim-öğretim mevzuatıyla ilgili sorularını, resmî metinlere dayanarak ve madde numarası vererek cevaplayan bir RAG asistanı.

## Durum
- [x] **Adım 0: Kapsam ve test seti.** Kapsam: [KAPSAM.md](KAPSAM.md). Test seti: [eval/](eval/) (64 soru, tamamı onaylı, `eval-v1`).
- [x] **Adım 1: Belgeleri temizleme ve madde bazlı bölme.** 6 belge, 167 madde, 224 parça.
- [ ] **Adım 2: Arama (sürüyor).** BM25 tabanı: Recall@5 = 0.686. Embedding/hibrit/reranker deneyi: [Colab'da aç](https://colab.research.google.com/github/Cnrygt11/uu-asistan/blob/main/notebooks/adim2_arama.ipynb)
- [ ] **Adım 3:** Cevap üretimi ve kaynak gösterme
- [ ] **Adım 4:** Değerlendirme
- [ ] **Adım 5:** Arayüz

## Kurulum ve çalıştırma
```
pip install -r requirements.txt
python -m uuasistan.hazirla   # PDF -> temiz metin -> data/parcalar.jsonl
python -m pytest              # parçalama, arama ve test seti testleri
python -m uuasistan.deney     # arama deneyi (GPU yoksa yalnızca BM25)
```

## Yapı
```
uuasistan/
  metin.py           PDF'ten metin çıkarma (PyMuPDF) ve temizleme
  parcalama.py       madde / fıkra / bent bazlı parçalama
  hazirla.py         hattı uçtan uca çalıştırır
  arama.py           BM25, embedding, RRF, reranker
  degerlendirme.py   arama metrikleri (recall@k, MRR)
  deney.py           arama deneyi
notebooks/
  adim2_arama.ipynb  Colab'da GPU ile arama deneyi
data/
  belgeler.json      belge kataloğu (kimlik, kapsam, yürürlük, kaynak URL, güncellik)
  madde_durumu.json  geçici maddelerin uygulanabilirliği (süresi dolmuş / süreli)
  raw/kaysis/        KAYSIS'ten indirilen resmî PDF'ler
  text/kaysis/       temizlenmiş metin (üretilir)
  parcalar.jsonl     indekslenecek parçalar (üretilir)
eval/
  test_seti.json     soru-cevap test seti
  sonuclar/          deney raporları
  README.md          şema ve kurallar
scripts/
  test_seti_dogrula.py   test setinin şemasını ve alıntılarını doğrular
tests/
  test_parcalama.py
```

`data/text/` ve `data/parcalar.jsonl` üretilen dosyalardır ama değişiklikler incelenebilsin diye depoda tutulur. Testler, `parcalar.jsonl` dosyasının kodla senkron olduğunu kontrol eder.

## Kaynaklar
Yalnızca [KAYSIS](https://kms.kaysis.gov.tr) (Kamu Kurumları Mevzuat Sistemi) üzerindeki resmî ve değişiklikleri işlenmiş metinler kullanılır.
