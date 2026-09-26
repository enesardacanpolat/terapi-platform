# iyi — Terapi platformu

Mevcut FastAPI + PostgreSQL projesi üzerine kurulmuş, mobil ekranlara uyumlu ilk web sürümü. Türkçe arayüz; sıcak yeşil, mercan ve sarı renkler. Ön yüz ayrı bir derleme gerektirmez.

## Hazır akışlar

- Duygu seçimi → birden fazla beklenti seçimi → çalışma alanı eşleşen, doğrulanmış uzmanlar. Eşleştirme açık kurallara dayanır; tanı veya klinik değerlendirme yapmaz.
- Uzman profili: eğitim, çalışma alanları, tanıtım, ücret, süre ve tamamlanan seanslardan gelen anonim değerlendirmeler.
- Danışan ve uzman hesapları; kişiye özel randevu ekranı.
- Haftalık çalışma saatleri; 90 gün boyunca Türkiye saatine göre müsait seanslar.
- Randevu talebi → uzman onayı → seans bittikten sonra uzman tarafından tamamlandı işareti → tek değerlendirme.
- Gelecek randevuyu iki taraf da iptal edebilir; saat tekrar açılır.
- Hem danışan hem uzman için çakışmalar PostgreSQL exclusion constraint ile engellenir. Aynı anda gelen isteklerde de korunur.
- Duygu ve beklentiler yalnızca randevudaki paylaşım kutusu seçilirse uzmana iletilir. Ham belge numarası herkese açık profilde gösterilmez.
- Profilde unvan, eğitim veya belge numarası değiştiğinde doğrulama kaldırılır. Çalışma saatlerini silmek mevcut randevuyu iptal etmez.

## Başlatma

Proje klasöründe:

```sh
source .venv/bin/activate
# Yeni kurulumda: python -m pip install -r requirements.txt
# .env.example dosyasından .env oluşturup bağlantı ve SECRET_KEY değerlerini ayarla.
docker compose up -d db
alembic upgrade head
DEBUG=false uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Arayüz: http://127.0.0.1:8000 · API dokümanı: http://127.0.0.1:8000/docs

`.env` dosyasındaki mevcut bağlantı korunmuştur. Yeni kurulumdaki veritabanı bağlantısı Docker Compose ayarlarıyla eşleşmelidir. Gerçek ortamda güçlü bir SECRET_KEY kullanın; DEBUG ve DEMO_MODE kapalı olmalı.

## Örnek verilerle deneme

Normal sunucuyu durdurup çalıştırın:

```sh
DEBUG=false .venv/bin/python scripts/demo.py
```

Demo, aynı PostgreSQL veritabanında rastgele isimli ayrı bir şema oluşturur. Gerçek uygulama kayıtlarını değiştirmez. Üst bant örnek profil kullanıldığını belirtir; demo kapatılınca örnek şema silinir. Örnek eğitimler gerçek bir yeterlilik beyanı değildir. Demo sunucusu yalnızca bu bilgisayara açıktır.

| Hesap | E-posta | Şifre |
| --- | --- | --- |
| Danışan | danisan@iyi.example | IyiDemo2026! |
| Deniz Yılmaz (uzman) | uzman1@iyi.example | IyiDemo2026! |
| Ece Demir (uzman) | uzman2@iyi.example | IyiDemo2026! |
| Can Aydın (uzman) | uzman3@iyi.example | IyiDemo2026! |

Duygu ve beklenti seçin, uzmanın profilinden yarın için saat seçin, danışan hesabıyla randevu alın. Çıkış yapıp ilgili uzman hesabıyla girerek randevuyu onaylayın. Aynı gün içinde geçmiş saatler listelenmez. Yeni açılan tarayıcı sekmesinde oturum tekrar gerekebilir.

## Uzman doğrulama

Yeni uzman hesabından profil oluşturulabilir; doğrulanana kadar arama ve randevu alımına kapalıdır. Bu sürümde yönetici web paneli yoktur. İşletmeci eğitim ve mesleki belgeleri dışarıda inceledikten sonra yerel yönetim komutunu kullanır:

```sh
DEBUG=false .venv/bin/python scripts/verify_therapist.py PROFIL_UUID --credentials-reviewed
# Onayı kaldırmak için:
DEBUG=false .venv/bin/python scripts/verify_therapist.py PROFIL_UUID --revoke
```

Profil kimliği, uzman hesabının `/api/therapists/me` yanıtındaki `id` alanıdır. Kullanıcıların kendilerini onaylayabileceği bir API yoktur. Önceki yorum tablosundaki yazarı bilinmeyen kayıtlar korunur fakat herkese açık yorumlarda ve puan ortalamasında kullanılmaz.

## Test

```sh
DEBUG=false .venv/bin/python -m unittest discover -s tests -v
node --check app/static/app.js
```

Testler rastgele isimli ayrı bir PostgreSQL şemasında tüm migration'ları sıfırdan uygular, geçici API sunucusu açar ve sonunda kendi şemasını kaldırır. Veritabanı kullanıcısının şema oluşturma izni gerekir. Mevcut uygulama verileri değişmez. Eşzamanlı çift rezervasyon, iki uzmana aynı anda randevu, doğrudan veritabanı çakışması, rol ve erişim kontrolleri, iptal, geçmiş saat, izin aralığı, doğrulama ve yorum kuralları sınanır.

## Sonraki ürün aşamaları

Bu sürüm yerel olarak çalışan bir randevu MVP'sidir. Gerçek ödeme, görüntülü görüşme, e-posta/SMS gönderimi, şifre sıfırlama, e-posta doğrulama, yönetici/moderasyon paneli ve iOS/Android uygulaması henüz yoktur. “Randevu talebin uzmana iletildi” ifadesi kaydın uzman panelinde görünmesini anlatır; dış bildirim gönderilmez. Paneldeki Yenile düğmesi güncel kayıtları getirir.

Gerçek kullanıcılarla yayına çıkmadan önce kişisel veri süreçleri, bilgilendirme ve izin metinleri, uzman doğrulama iş akışı, saklama/silme kuralları, erişim kayıtları, hız sınırlaması, HTTPS, yedekleme ve geri yükleme planı tamamlanmalıdır. Yorumlar kimlik göstermeden yayınlansa da kullanıcı metne kişisel bilgi ekleyebilir; moderasyon akışı henüz uygulanmadı. Bunlar tamamlanmadan sürüm üretime hazır kabul edilmemelidir.

Mobil uygulama aynı `/api` servislerini kullanabilir. Sonraki aşamada tercih edilen mobil teknoloji ve görüşme/ödeme hizmeti üzerinden devam edilebilir.
