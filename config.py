"""Trend Radar ayarları. Değiştirmek istediğin her şey burada."""

# Hangi ülkenin trendleri takip edilsin (ABD = "US", Türkiye = "TR", İngiltere = "GB")
COUNTRY = "US"

# Reddit'te takip edilecek topluluklar (başında r/ olmadan)
SUBREDDITS = [
    "OutOfTheLoop",      # "bu akım da ne?" soruları: yeni akımların erken sinyali
    "GenZ",
    "TikTokCringe",      # TikTok'ta patlayan videoların Reddit'e taşındığı yer
    "popculturechat",
    "femalefashionadvice",
    "malefashionadvice",
    "BuyItForLife",
    "shutupandtakemymoney",
]

# Talep Borsası'nda en fazla kaç ürün takip edilsin
MAX_PRODUCTS = 25

# Yapay zekanın her gün yazacağı akım kartı sayısı
MAX_TRENDS = 8

# Gemini modeli. Google yeni model çıkarırsa buradan değiştirebilirsin.
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
