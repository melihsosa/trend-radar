# Trend Radar

İnternetteki yükselen akımları ve ürün talebini düzenli olarak tarayan, sonucu Chrome eklentisinde gösteren ücretsiz sistem.

- **Talep Borsası:** Ürünlerin Google aramalarındaki son 7 günlük talep değişimi (gerçek ölçüm).
- **İnternette Gündem:** TikTok, YouTube, Reddit ve Google'dan toplanan verilerle yapay zekanın (Gemini) seçtiği akımlar ve ürün fikirleri.

Sistem GitHub'ın sunucularında kendi kendine çalışır:

- **İnternette Gündem:** 3 saatte bir (Türkiye saatiyle 00, 03, 06, 09, 12, 15, 18, 21)
- **Talep Borsası:** günde 1 kez, 07:30'da (verisi günlük değiştiği için daha sık çalışmasının faydası yok)

GitHub yoğun saatlerde çalışmayı 10-30 dakika geciktirebilir. Eklentinin başlığında son güncellemenin saati ve dakikası yazar. Bilgisayarının açık olmasına gerek yoktur ve Claude kullanım hakkından yemez.

---

## Kurulum (yaklaşık 15 dakika)

### 1. GitHub hesabı aç
github.com adresinden ücretsiz hesap aç. Hesabın varsa bu adımı atla.

### 2. Depoyu (repo) oluştur ve dosyaları yükle
1. GitHub'da sağ üstteki **+** → **New repository**.
2. Ad: `trend-radar`. Görünürlük: **Public** (herkese açık).
   Eklentinin raporu okuyabilmesi için bu gerekli. Depoda sadece herkese açık trend verisi durur; anahtarların gizli kalır (4. adım).
3. **Create repository** → açılan sayfada **uploading an existing file** bağlantısına tıkla.
4. Bu klasördeki **her şeyi** (collector, data, extension klasörleri, README.md ve **.github** klasörü) sürükleyip bırak → **Commit changes**.

> **.github klasörü görünmüyorsa:** Başı noktayla başlayan klasörler gizlidir. Mac'te Finder'da `Cmd + Shift + .`, Windows'ta Görünüm → Gizli öğeler ile görünür yap.
> Ya da GitHub'da **Add file → Create new file** de, dosya adına `.github/workflows/daily.yml` yaz ve bu klasördeki aynı dosyanın içeriğini yapıştır.

### 3. Gemini API anahtarı al
1. **aistudio.google.com** adresine Google hesabınla gir.
2. **Get API key** → **Create API key**.
3. Çıkan anahtarı kopyala. Kimseyle paylaşma.

### 4. Anahtarı GitHub'a gizli olarak ekle
1. Depo sayfanda **Settings** → sol menüde **Secrets and variables** → **Actions**.
2. **New repository secret**.
3. Name: `GEMINI_API_KEY`, Secret: kopyaladığın anahtar → **Add secret**.

### 5. İlk taramayı başlat
1. Depo sayfanda üstteki **Actions** sekmesi. Sorarsa **I understand my workflows, go ahead and enable them**.
2. Soldan **Trend Radar tarama** → sağda **Run workflow** → "Ne güncellensin?" kısmında **all** seçili kalsın → **Run workflow**.
3. 5-10 dakika bekle. Yeşil tik çıkınca `data/latest.json` dosyası oluşmuş olur.

### 6. Chrome eklentisini kur
1. Bu klasörü bilgisayarında bir yere çıkar (zip ise).
2. Chrome'da adres çubuğuna `chrome://extensions` yaz.
3. Sağ üstten **Geliştirici modu**nu aç.
4. **Paketlenmemiş öğe yükle** → `extension` klasörünü seç.
5. Yapboz simgesinden Trend Radar'ı **sabitle**.
6. Eklentiyi aç → dişli simgesi → GitHub kullanıcı adını ve `trend-radar` yaz → **Kaydet ve test et**.

Bitti. Artık gündem 3 saatte bir, talep borsası her sabah kendiliğinden güncellenir.

---

## İsteğe bağlı: daha fazla kaynak

Sistem bunlar olmadan da çalışır. Eklersen analiz güçlenir.

**YouTube (önerilir, ücretsiz)**
1. console.cloud.google.com → yeni proje oluştur.
2. **APIs & Services → Library** → "YouTube Data API v3" → **Enable**.
3. **Credentials → Create credentials → API key**.
4. GitHub'a `YOUTUBE_API_KEY` adıyla gizli anahtar olarak ekle (4. adımdaki gibi).

**Reddit**
Anahtar olmadan da herkese açık akıştan okumayı dener, ama Reddit GitHub sunucularından gelen istekleri sık sık engeller. Reddit geliştirici erişimin varsa `REDDIT_CLIENT_ID` ve `REDDIT_CLIENT_SECRET` olarak ekle. Reddit yeni geliştiricilerden başvuru isteyebiliyor.

---

## Ayarlar

- **Ülke, Reddit toplulukları, kart sayısı:** `collector/config.py`
- **Her zaman izlemek istediğin ürünler:** `collector/watchlist.txt`
- **Gemini modeli:** Varsayılan `gemini-2.5-flash`. Google modeli değiştirirse **Settings → Secrets and variables → Actions → Variables** bölümüne `GEMINI_MODEL` adıyla yeni model adını ekle.
- **Çalışma sıklığı:** `.github/workflows/daily.yml` içindeki iki `cron` satırı (UTC saatiyle). `0 */3 * * *` = 3 saatte bir. 2 saatten daha sık yapma; Google, Reddit ve TikTok sık istekleri engelleyebilir, Gemini'nin ücretsiz günlük kotası da dolabilir.

Dosyaları GitHub'da doğrudan kalem simgesiyle düzenleyebilirsin.

---

## Bir şey ters giderse

Eklentinin altındaki noktalar hangi kaynağın çalıştığını gösterir. Dolu yeşil nokta çalışıyor, içi boş kırmızı halka o gün çalışmadı demek. Üzerine gelince sebebini yazar.

| Sorun | Çözüm |
|---|---|
| Eklenti "örnek veri" gösteriyor | Dişli simgesinden kullanıcı adını ve depo adını kontrol et. İlk tarama bitmiş olmalı. |
| Actions kırmızı çarpı verdi | Actions → çalışmaya tıkla → "Trendleri topla" adımındaki hata mesajını oku. |
| TikTok noktası kırmızı | TikTok sayfasını değiştirmiş olabilir. `collector/sources.py` içindeki `tiktok_hashtags` güncellenmeli. |
| "Talep ölçümü" çalışmadı | Google Trends çok fazla istek gelince geçici olarak engelliyor. Genelde ertesi gün düzelir; önceki değerler "eski veri" etiketiyle gösterilir. |
| Tarama birden durdu | GitHub, uzun süre hareketsiz kalan depolarda zamanlanmış çalışmayı kapatabiliyor. Actions sekmesinden yeniden **Enable** et. |

## Bilmen gerekenler

- **Talep Borsası yüzdeleri** Google'ın 0-100 arası ilgi puanından hesaplanır: son 7 günün ortalaması, önceki 7 günle karşılaştırılır. Satış rakamı değil, arama ilgisidir.
- **Yapay zeka hata yapabilir.** Stok almadan önce akımı kendin de kontrol et.
- **Gemini'nin ücretsiz sürümünde** Google gönderilen veriyi modellerini geliştirmek için kullanabilir. Buraya sadece herkese açık trend verisi gönderilir.
- **TikTok Creative Center'ın resmi API'si yoktur.** Sayfa değişirse o bölüm bozulabilir; diğer kaynaklar çalışmaya devam eder.
