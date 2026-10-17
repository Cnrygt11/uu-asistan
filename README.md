# UÜ Asistan

Bursa Uludağ Üniversitesi önlisans ve lisans öğrencilerinin eğitim-öğretim mevzuatıyla ilgili sorularını, resmî metinlere dayanarak ve madde numarası vererek cevaplayan bir RAG asistanı.

## Durum
- [x] **Adım 0: Kapsam ve test seti.** Kapsam: [KAPSAM.md](KAPSAM.md). Test seti: [eval/](eval/) (84 soru, tamamı onaylı).
- [x] **Adım 1: Belgeleri temizleme ve madde bazlı bölme.** 6 belge, 186 madde, 240 parça.
- [x] **Adım 2: Arama.** turkish-e5-large → modernbert-tr-reranker: Recall@5 = 0.905, Recall@10 = 0.941, MRR = 0.851 (80 soru; BM25: 0.656). Karar ve gerekçe: [KAPSAM.md](KAPSAM.md#arama-adım-2). Deney: [Colab'da aç](https://colab.research.google.com/github/Cnrygt11/uu-asistan/blob/main/notebooks/adim2_arama.ipynb)
- [ ] **Adım 3: Cevap üretimi (sürüyor).** İlk sürüm (Qwen3-8B, transformers): 84 sorunun %57'si doğru; darboğaz dil modeli ([değerlendirme](eval/sonuclar/adim3_qwen3-8b_degerlendirme.json)). Şimdi: vLLM ile Qwen3-8B ve Qwen3-30B-A3B karşılaştırması, hedef ilk kelime < 2 sn, cevap < 10 sn: [Colab'da aç](https://colab.research.google.com/github/Cnrygt11/uu-asistan/blob/main/notebooks/adim3_cevap.ipynb)
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
  cevap.py           arama + dil modeli ile kaynaklı cevap (sistem istemi burada)
  uretim.py          test setini asistana sorup cevapları kaydeder
notebooks/
  adim2_arama.ipynb  Colab'da GPU ile arama deneyi
  adim3_cevap.ipynb  Colab'da GPU ile cevap üretimi
data/
  belgeler.json      belge kataloğu (kimlik, kapsam, yürürlük, kaynak URL, güncellik)
  madde_durumu.json  geçici maddelerin uygulanabilirliği (süresi dolmuş / süreli)
  ogrenci_sozlugu.json  öğrenci dili -> mevzuat terimi sözlüğü (taslak)
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
  test_arama.py
  test_cevap.py
```

`data/text/` ve `data/parcalar.jsonl` üretilen dosyalardır ama değişiklikler incelenebilsin diye depoda tutulur. Testler, `parcalar.jsonl` dosyasının kodla senkron olduğunu kontrol eder.

## Kaynaklar
Yalnızca [KAYSIS](https://kms.kaysis.gov.tr) (Kamu Kurumları Mevzuat Sistemi) üzerindeki resmî ve değişiklikleri işlenmiş metinler kullanılır.
