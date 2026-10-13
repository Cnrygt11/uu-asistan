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
| UYG | Uygulamalı Eğitimler (Staj) Yönergesi | 2022 | ✅ |
| OZEL | Özel Öğrenci Yönergesi | 2022 | ✅ |
| GEC | Yatay Geçiş / ÇAP / Yandal Yönergesi | 2014 | ⚠️ güncelliği şüpheli |
| YAB | Yabancı Uyruklu Öğrenci Kabul Yönergesi | 2022 | ✅ ikincil |
| LU_YON, LU_UE, TIP_INT, DIS | Lisansüstü, Tıp, Diş | — | v2 |

## Veri sorunları
| # | Sorun | Durum |
|---|---|---|
| 1 | **Eski sürüm tuzağı.** EOY'nin 2014 ve 2020 orijinal kopyaları internette dolaşıyor; 2023 ve 2024 değişiklikleri önemli kuralları değiştirdi. | ✅ Yalnızca KAYSIS konsolide metni kullanılıyor; parçalar `degisiklikler` alanında RG değişiklik bilgisini taşıyor. |
| 2 | **GEC 2014 tarihli.** YGS/LYS'ye atıf yapıyor, ÇAP GANO eşiği (2.72) güncel YÖK yönetmeliğiyle çelişiyor olabilir. | 🟡 Parçalar `guncellik: "supheli"` etiketi taşıyor; cevaba uyarı ekleme Adım 3'te. |
| 3 | **YAZ, mülga yönetmeliğe atıf yapıyor.** Madde 7 ve 13 "Önlisans ve Lisans Öğretim Yönetmeliği"ni (2014) anıyor; fiilen EOY kastediliyor. | 🔲 Adım 3 (sistem istemi). |
| 4 | **Süreli (geçici) maddeler.** Durumları [data/madde_durumu.json](data/madde_durumu.json) dosyasında. | ✅ Süresi dolanlar (Geçici 1, 2) indekse alınmıyor; süreli olanlar (Geçici 3, 4) `kayit_yili_en_gec` etiketi taşıyor. **Her eğitim-öğretim yılı başında gözden geçirilmeli** (Geçici 3'ün süresi 2026-2027 sonunda doluyor). |
| 5 | **PDF kodlama hatası.** 61283'te `Ġ/ġ/Ģ` bozulması. | ✅ `uuasistan/metin.py` içinde kural; testle korunuyor. |
| 6 | **PDF kelime kırılmaları.** pypdf "giri ş", "öğr encilerin" gibi kırıklar üretiyordu. | ✅ Metin çıkarma PyMuPDF'e taşındı; kırıklar kayboldu. |
| 7 | **Sayfa gürültüsü.** "Senato Karar Eki" başlıkları, sayfa numaraları, üç satıra bölünen madde başları (`MADDE`/`1`/`–`). | ✅ `uuasistan/metin.py`; madde numaralarının ardışıklığı testle korunuyor. |

## Dönem başı bakım
Mevzuat değiştiğinde asistan sessizce yanlış bilgi vermeye başlar. Her eğitim-öğretim dönemi başında:
1. `python scripts/guncellik_kontrol.py`: EOY ve YAZ'ın değişiklik geçmişini mevzuat.gov.tr ile karşılaştırır (son kontrol: Ekim 2026, ikisi de güncel).
2. KAYSIS'te Senato yönergelerinin (UYG, OZEL, GEC, YAB) yeni sürümü var mı, elle bakılır.
3. [data/madde_durumu.json](data/madde_durumu.json) gözden geçirilir; süresi dolan geçici maddeler `suresi_dolmus` yapılır.
4. Değişiklik varsa: PDF güncellenir → `python -m uuasistan.hazirla` → `python -m pytest` → etkilenen test soruları yeniden onaylanır.

## Parçalama (Adım 1)
- Her madde bir parça; 1500 karakteri aşan maddeler fıkra sınırlarından, tek başına uzun fıkralar bent sınırlarından bölünür (fıkranın giriş cümlesi her alt parçada tekrarlanır). Paragraf ortasından asla bölünmez.
- Her parça: belge, madde, başlık, bölüm, fıkra numaraları, değişiklik bilgisi, kaynak URL ve varsa güncellik/kayıt yılı etiketi taşır.
- Başarı kriteri (testle korunuyor): test setindeki her kaynak alıntısı, doğru maddenin tek bir parçasında eksiksiz bulunur. Karşılaştırma: sabit 500/1000 karakterlik pencereler alıntıların %9/%5'ini bölüyor.

## Başarı ölçütü
[eval/test_seti.json](eval/test_seti.json) üzerinde:
- Doğru kaynağı getirme (Recall@5) ≥ %90
- Cevap doğruluğu ≥ %85
- `kapsam_disi` sorularda uydurma oranı = %0
- `guncel_degisiklik` sorularında eski kurala dayanan cevap = 0
