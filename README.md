# UÜ Asistan

Bursa Uludağ Üniversitesi önlisans ve lisans öğrencilerinin eğitim-öğretim mevzuatıyla ilgili sorularını, resmî metinlere dayanarak ve madde numarası vererek cevaplayan bir RAG asistanı.

## Durum
- [x] **Adım 0: Kapsam ve test seti.** Kapsam: [KAPSAM.md](KAPSAM.md). Test seti: [eval/](eval/) (63 soru).
- [ ] **Adım 1:** Belgeleri temizleme ve madde bazlı bölme
- [ ] **Adım 2:** Hibrit arama (BM25 + embedding) ve reranker
- [ ] **Adım 3:** Cevap üretimi ve kaynak gösterme
- [ ] **Adım 4:** Değerlendirme
- [ ] **Adım 5:** Arayüz

## Yapı
```
data/
  belgeler.json      belge kataloğu (kimlik, yürürlük, kaynak URL, güncellik notları)
  raw/kaysis/        KAYSIS'ten indirilen resmî PDF'ler
  text/kaysis/       PDF'lerden çıkarılan ham metin
eval/
  test_seti.json     soru-cevap test seti
  README.md          şema ve kurallar
scripts/
  test_seti_dogrula.py   test setinin şemasını ve alıntılarını doğrular
```

## Kaynaklar
Yalnızca [KAYSIS](https://kms.kaysis.gov.tr) (Kamu Kurumları Mevzuat Sistemi) üzerindeki resmî ve değişiklikleri işlenmiş metinler kullanılır.

## Doğrulama
```
python scripts/test_seti_dogrula.py
```
