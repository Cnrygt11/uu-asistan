# UÜ Asistan — Kapsam (v1)

## Ne yapacak?
Bursa Uludağ Üniversitesi **önlisans ve lisans** öğrencilerinin eğitim-öğretim mevzuatıyla ilgili sorularını, resmî metinlere dayanarak ve **madde numarası vererek** cevaplayacak.

## Üslup
- Öğrenciye **"sen"** diye hitap eder; samimi ama net.
- Her cevapta dayandığı belge ve madde numarasını gösterir.
- Cevap öğrencinin durumuna göre değişiyorsa ve bu bilgi yoksa önce sorar:
  - **Fakülte:** kural fakülteye göre farklıysa.
  - **Kayıt yılı:** yalnızca cevabı süreli bir geçici madde ([data/madde_durumu.json](data/madde_durumu.json), `sureli`) değiştiriyorsa. Diğer sorularda kayıt yılı sorulmaz.
- Bugünün tarihini ve güncel eğitim-öğretim yılını bilir (sistem istemine her istekte eklenir). Azami süre, geçici maddeler ve kayıt yılına bağlı kurallarda bunu hesaba katar.
- Öğrenci hakkında yalnızca öğrencinin kendi söylediklerini bilir. Bu bilgiye dayanırken kaynağını belli eder ("2019'da kayıt olduğunu söylediğin için…"); öğrenci kayıtlarına erişimi varmış gibi konuşmaz.

## Ne yapmayacak? (v1)
- Lisansüstü (YL/doktora) soruları → v2
- Fakülteye özel yönergeler (Tıp intörnlük, Diş Hekimliği) → v2
- Akademik takvim tarihleri, ücret tutarları, duyurular, yemekhane vb. → kapsam dışı; sistem "belgelerimde yok" demeli ve doğru yere yönlendirmeli
- Kişisel öğrenci verisi (OBS, not, transkript) → yok (KVKK)

## Belgeler
Tam liste ve kaynak bağlantıları: [data/belgeler.json](data/belgeler.json). **Yalnızca KAYSIS** (kms.kaysis.gov.tr) metinleri kullanılır: değişiklikleri işlenmiş resmî metinler. Başka kaynaktan (fakülte siteleri, çeviriler, haber siteleri) belge eklenmez.

| Kimlik | Belge | Yürürlük | Durum |
|---|---|---|---|
| EOY | Önlisans ve Lisans Eğitim Öğretim Yönetmeliği | 2020; 2023 ve 2024 değişiklikleri işlenmiş | ✅ ana kaynak |
| YAZ | Yaz Öğretimi Yönetmeliği | 2020 | ✅ (mülga yönetmeliğe atıf yapıyor, bkz. aşağı) |
| YDY | Yabancı Diller YO Yabancı Dil Eğitim-Öğretim ve Sınav Yönetmeliği (hazırlık) | 2020 | ✅ (değişiklik bulunamadı) |
| UYG | Uygulamalı Eğitimler (Staj) Yönergesi | 2022 | ✅ |
| OZEL | Özel Öğrenci Yönergesi | 2022 | ✅ |
| GEC | Yatay Geçiş / ÇAP / Yan Dal / Kredi Transferi Yönergesi | 2025 | ✅ |
| GEC_2014 | Eski Yatay Geçiş / ÇAP / Yandal Yönergesi | 2014 | mülga; yalnızca 20.03.2025 öncesi ÇAP/yan dal kayıtlılarına uygulanır (GEC Geçici 1); indekslenmez |
| YAB | Yabancı Uyruklu Öğrenci Kabul Yönergesi | 2022 | v2 (aday öğrencilere yönelik; hedef kitle dışı) |
| LU_YON, LU_UE, TIP_INT, DIS | Lisansüstü, Tıp, Diş | — | v2 |

## Veri sorunları
| # | Sorun | Durum |
|---|---|---|
| 1 | **Eski sürüm tuzağı.** EOY'nin 2014 ve 2020 orijinal kopyaları internette dolaşıyor; 2023 ve 2024 değişiklikleri önemli kuralları değiştirdi. | ✅ Yalnızca KAYSIS konsolide metni kullanılıyor; parçalar `degisiklikler` alanında RG değişiklik bilgisini taşıyor. |
| 2 | **GEC 2014 tarihliydi ve yürürlükten kalkmıştı.** 20.03.2025 tarihli yönerge (KAYSIS 206792) yerini aldı; KAYSIS eskisini (61283) hâlâ yayında tutuyor. **Ders: KAYSIS'te olmak yürürlükte olmak demek değil.** | ✅ 2025 yönergesi indekslendi; 2014 yönergesi `mulga`. Eski kurallar 2025 öncesi ÇAP/yan dal öğrencileri için geçerli (Geçici 1); asistan bu öğrencileri ÇAP'a kayıt tarihini sorarak ayırt eder ve Öğrenci İşleri'ne yönlendirir. |
| 3 | **YAZ, mülga yönetmeliğe atıf yapıyor.** Madde 7 ve 13 "Önlisans ve Lisans Öğretim Yönetmeliği"ni (2014) anıyor; fiilen EOY kastediliyor. | 🔲 Adım 3 (sistem istemi). |
| 4 | **Süreli (geçici) maddeler.** Durumları [data/madde_durumu.json](data/madde_durumu.json) dosyasında. | ✅ Süresi dolanlar (Geçici 1, 2) indekse alınmıyor; süreli olanlar (Geçici 3, 4) `kayit_yili_en_gec` etiketi taşıyor. **Her eğitim-öğretim yılı başında gözden geçirilmeli** (Geçici 3'ün süresi 2026-2027 sonunda doluyor). |
| 5 | **PDF kodlama hatası.** 61283'te `Ġ/ġ/Ģ` bozulması. | ✅ `uuasistan/metin.py` içinde kural; testle korunuyor. |
| 6 | **PDF kelime kırılmaları.** pypdf "giri ş", "öğr encilerin" gibi kırıklar üretiyordu. | ✅ Metin çıkarma PyMuPDF'e taşındı; kırıklar kayboldu. |
| 7 | **Sayfa gürültüsü.** "Senato Karar Eki" başlıkları, sayfa numaraları, üç satıra bölünen madde başları (`MADDE`/`1`/`–`). | ✅ `uuasistan/metin.py`; madde numaralarının ardışıklığı testle korunuyor. |

## Dönem başı bakım
Mevzuat değiştiğinde asistan sessizce yanlış bilgi vermeye başlar. Her eğitim-öğretim dönemi başında:
1. KAYSIS'teki belgelerin yeni sürümü var mı, bakılır (kaynak bağlantıları: [data/belgeler.json](data/belgeler.json); son indirme: Ekim 2026).
2. [data/madde_durumu.json](data/madde_durumu.json) gözden geçirilir; süresi dolan geçici maddeler `suresi_dolmus` yapılır.
3. Değişiklik varsa: PDF güncellenir → `python -m uuasistan.hazirla` → `python -m pytest` → etkilenen test soruları yeniden onaylanır.

## Parçalama (Adım 1)
- Her madde bir parça; 1500 karakteri aşan maddeler fıkra sınırlarından, tek başına uzun fıkralar bent sınırlarından bölünür (fıkranın giriş cümlesi her alt parçada tekrarlanır). Paragraf ortasından asla bölünmez.
- Her parça: belge, madde, başlık, bölüm, fıkra numaraları, değişiklik bilgisi, kaynak URL ve varsa güncellik/kayıt yılı etiketi taşır.
- Başarı kriteri (testle korunuyor): test setindeki her kaynak alıntısı, doğru maddenin tek bir parçasında eksiksiz bulunur. Karşılaştırma: sabit 500/1000 karakterlik pencereler alıntıların %9/%5'ini bölüyor.

## Arama (Adım 2)
**Seçilen yapılandırma (v2):** `ytu-ce-cosmos/turkish-e5-large` ile ilk 30 aday → `ytu-ce-cosmos/modernbert-tr-reranker` ile yeniden sıralama. BM25 kullanılmıyor.

| Ölçüt (80 soru, 197 parça) | BM25 | turkish-e5-large | **+ modernbert-tr** | + bge-reranker-v2-m3 | Eski seçim: BM25 + bge-m3 hibrit |
|---|---|---|---|---|---|
| Recall@1 | 0.354 | 0.460 | **0.694** | 0.656 | 0.467 |
| Recall@5 | 0.656 | 0.874 | **0.905** | 0.872 | 0.849 |
| Recall@10 | 0.782 | 0.931 | 0.941 | **0.942** | 0.896 |
| MRR | 0.544 | 0.681 | **0.851** | 0.824 | 0.664 |

Tam tablo: [eval/sonuclar/adim2_v2_colab.json](eval/sonuclar/adim2_v2_colab.json) (Colab L4). İlk ölçüm (60 soru, BM25 + bge-m3 seçilmişti): [adim2_colab.json](eval/sonuclar/adim2_colab.json).

**Neden değişti:**
- Eski seçim (BM25 + bge-m3 hibrit), seçimden sonra yazılan 20 soruda (S068–S087) belirgin düştü: Recall@5 0.865 → 0.800. İlk skor iyimserdi.
- turkish-e5-large + modernbert-tr yeni sorularda daha sağlam: 0.912 → 0.883. BM25 eklemek turkish-e5-large'ı iyileştirmiyor (hibrit 0.859 < tek başına 0.874), sadelik için çıkarıldı.
- Recall@5 farkları istatistiksel olarak anlamlı değil (eşleştirilmiş bootstrap, %95 güven aralıkları sıfırı içeriyor). Reranker'ın katkısı ilk sıralarda ve anlamlı: Recall@1 +0.233 (GA +0.135…+0.333), MRR +0.170 (GA +0.096…+0.245).

**Uyarılar:**
- Bu seçim 80 sorunun tamamı üzerinde yapıldı; 20 yeni soru artık bu seçim için görülmemiş set değil. Gerçek öğrenci sorularıyla yeniden ölçülmeli.
- Kalan kaçırmaların çoğu öğrenci dili–mevzuat dili farkından ("kayıt dondurma" / "izinli ayrılma"); Adım 3'te ölçülecek.
- Dil modeline verilecek parça sayısı Adım 3'te belirlenecek (Recall@10 = 0.941).
- TurkEmbed4Retrieval deneyden çıkarıldı: özel kodu (`trust_remote_code`) güncel transformers ile uyumsuz ve GPU'da deneyin geri kalanını çökertiyor.
- v2 ölçümü YDY eklenmeden önce yapıldı (197 parça; şimdi 240).

## Başarı ölçütü
[eval/test_seti.json](eval/test_seti.json) üzerinde:
- Doğru kaynağı getirme (Recall@5) ≥ %90
- Cevap doğruluğu ≥ %85
- `kapsam_disi` sorularda uydurma oranı = %0
- `guncel_degisiklik` sorularında eski kurala dayanan cevap = 0
