# UÜ Asistan — Kapsam (v1)

## Ne yapacak?
Bursa Uludağ Üniversitesi **önlisans ve lisans** öğrencilerinin eğitim-öğretim mevzuatıyla ilgili sorularını, resmî metinlere dayanarak ve **madde numarası vererek** cevaplayacak.

## Üslup
- Öğrenciye **"sen"** diye hitap eder; samimi ama net.
- Her cevapta dayandığı belge ve madde numarasını gösterir.
- Cevap öğrencinin durumuna (ör. fakülte) göre değişiyorsa ve bu bilgi yoksa önce sorar.
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

## Bilinen veri sorunları (Adım 1'de çözülecek)
1. **Eski sürüm tuzağı.** İnternette EOY'nin 2014 ve 2020 orijinal kopyaları dolaşıyor. 2023 değişikliği Eğitim Fakültesi'ni devam istisnasından çıkardı, 2024 değişikliği kayıt dondurma kurallarını değiştirdi. Derlemde yalnızca KAYSIS'teki konsolide metin kullanılmalı.
2. **GEC 2014 tarihli.** YGS/LYS'ye atıf yapıyor, ÇAP GANO eşiği (2.72) YÖK'ün güncel yönetmeliğiyle çelişiyor olabilir. Bu belgeden üretilen cevaplara otomatik güncellik uyarısı eklenmeli.
3. **YAZ, mülga yönetmeliğe atıf yapıyor.** Madde 7 ve 13 "Önlisans ve Lisans Öğretim Yönetmeliği"ni (2014) anıyor; bu atıf EOY olarak çözülmeli.
4. **PDF kodlama hatası.** 61283'te `Ġ→İ`, `ġ→Ş`, `Ģ→ş` bozulması vardı; elle düzeltildi, temizleme hattına kural olarak eklenmeli.
5. **PDF kelime kırılmaları.** "öğr encilerin", "pro gramlanmış" gibi. BM25 ve embedding kalitesini düşürür, temizlenmeli.

## Başarı ölçütü
[eval/test_seti.json](eval/test_seti.json) üzerinde:
- Doğru kaynağı getirme (Recall@5) ≥ %90
- Cevap doğruluğu ≥ %85
- `kapsam_disi` sorularda uydurma oranı = %0
- `guncel_degisiklik` sorularında eski kurala dayanan cevap = 0
