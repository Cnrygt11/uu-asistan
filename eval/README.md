# Test seti

`test_seti.json`, sistemin her değişiklikten sonra ölçüleceği soru-cevap setidir.

## Temel ilke: üç şeyi ayrı tut
| Ne | Nerede | Kim okur |
|---|---|---|
| Öğrenciye gidecek doğru içerik | `beklenen_cevap` | Değerlendirici; asistanın cevabıyla karşılaştırır |
| Asistanın nasıl davranması gerektiği | `beklenen_davranis` | Değerlendirici; her etiketi evet/hayır kontrol eder |
| Çok adımlı diyalog | `netlestirme` | Değerlendirme betiği; diyaloğu simüle eder |

`beklenen_cevap`'a "Sistem şunu yapmalı" gibi talimat yazılmaz. Validator bunu yakalar.

## Alanlar
| Alan | Zorunlu | Açıklama |
|---|---|---|
| `id` | ✓ | `S001` biçiminde, tekil |
| `soru` | ✓ | Öğrencinin ilk mesajı, günlük dille |
| `netlestirme` | | Diyaloğun ikinci adımı (aşağıya bkz.) |
| `beklenen_cevap` | ✓ | Öğrenciye gidecek cevabın özü. Birebir eşleşme beklenmez. `netlestirme` varsa öğrencinin yanıtından **sonraki** cevaptır. |
| `beklenen_davranis` | | Davranış etiketleri listesi (aşağıya bkz.) |
| `kaynaklar` | ✓ | `belge` (bkz. `data/belgeler.json`), `madde`, `alinti`: o maddeden birebir kısa alıntı |
| `kategori` | ✓ | aşağıya bkz. |
| `zorluk` | ✓ | `kolay` / `orta` / `zor` |
| `not` | | Tuzaklar, eş sorular; yalnızca insanlar için |
| `kaynak_tipi` | ✓ | `sentetik` (mevzuattan üretildi) / `gercek` (öğrenciden geldi) |
| `dogrulandi` | ✓ | Bir insan cevabı mevzuata karşı kontrol ettiyse `true`. **`beklenen_cevap` değişirse `false` yapılır.** |

## Kategoriler
- **olgusal / sayisal**: tek maddeden doğrudan cevap
- **kosullu**: cevap öğrencinin durumuna (fakülte, kayıt yılı, dönem türü) göre değişir
- **coklu_kaynak**: birden fazla madde veya belge birleştirilmeli
- **guncel_degisiklik**: eski metne göre cevap verilirse yanlış olur (2023/2024 değişiklikleri)
- **celiski**: kaynağın güncelliği şüpheli (`guncellik_uyarisi` zorunlu)
- **kapsam_disi**: belgelerde cevap yok (`bilgi_yok_der` zorunlu)
- **ingilizce**: İngilizce soru, Türkçe mevzuata dayalı İngilizce cevap

## Davranış etiketleri
| Etiket | Asistan… |
|---|---|
| `netlestirme_sorar` | Cevap vermeden önce eksik bilgiyi (ör. fakülte) sorar; tek bir kesin cevap vermez |
| `netlestirme_sormaz` | Bilgi soruda zaten var; tekrar sormaz, doğrudan cevaplar |
| `bilgi_yok_der` | Belgelerde olmadığını açıkça söyler |
| `uydurmaz` | Belgede olmayan sayı/tarih/tutar vermez |
| `guncellik_uyarisi` | Kaynağın eski olabileceğini belirtir |
| `yonlendirir` | Doğru birime/kaynağa yönlendirir |

Tüm sorular için ortak kurallar etiketlenmez; değerlendirme rubriğinde genel kural olarak tanımlanır:
- Cevapta dayanılan belge ve madde numarası gösterilir.
- Öğrenciye "sen" diye hitap edilir (bkz. `KAPSAM.md`, Üslup).

`beklenen_cevap` bir **içerik** referansıdır; hitabı ("siz"/"sen") puanlamayı etkilemez. Bu yüzden yalnızca hitap düzeltmek için cevaplar değiştirilmez (onaylar sıfırlanmasın diye).

## Netleştirme (çok adımlı diyalog)
```json
"netlestirme": {
  "konu": "fakulte",
  "ornek_soru": "Gereken AKTS fakülteye göre değişiyor. Hangi fakültede okuyorsun?",
  "ogrenci_yaniti": "İİBF'deyim."
}
```
Değerlendirme iki adımda yapılır:
1. Asistan `soru`'ya cevap verir → fakülteyi sordu mu? (`netlestirme_sorar`)
2. `ogrenci_yaniti` gönderilir → cevap `beklenen_cevap` ile karşılaştırılır.

Her netleştirme sorusunun, fakültenin baştan belirtildiği eşleri vardır. Böylece hem farklı fakülte cevapları hem de "her seferinde fakülte sorma" hatası ölçülür:

| Netleştirmeli soru (öğrenci yanıtı) | Fakülteli eşleri (`netlestirme_sormaz`) |
|---|---|
| S002: tekrar derste devam (Mühendislik → zorunlu değil) | S003 (Tıp → zorunlu), S004 (Eğitim → 2023'ten beri zorunlu değil) |
| S026: mezuniyet AKTS (İİBF → 240) | S065 (Diş Hekimliği → 300) |
| S047: bitiremezsem diploma (Mühendislik → önlisans) | S066 (Tıp → önlisans + lisans) |

## Doğrulama
```
python scripts/test_seti_dogrula.py
```
Şemayı, etiket tutarlılığını, talimat sızıntısını ve her alıntının belirtilen maddede birebir geçtiğini kontrol eder. Her değişiklikten sonra çalıştırın.

## Sıradaki işler
1. **İnsan kontrolü.** 63 sorunun 1'i onaylı. Her birini okuyup `dogrulandi: true` yapın. S056–S058'deki (GEC) güncellik sorusunu Öğrenci İşleri'ne sorun.
2. **Gerçek öğrenci soruları.** Sentetik sorular öğrencilerin gerçekte nasıl sorduğunu yansıtmaz. Hedef en az 50 gerçek soru. Kaynaklar: anket (Google Form: "Okul kurallarıyla ilgili en son neyi merak ettin?"), öğrenci WhatsApp/Discord grupları, Öğrenci İşleri'ne en sık gelen sorular. Kişisel bilgileri silin; `kaynak_tipi: "gercek"` ile ekleyin.
