"""Talep Borsası: ürünlerin Google aramalarındaki haftalık talep değişimi.

Her ürün için Google Trends'ten son ~30 günlük günlük ilgi eğrisini alır ve
son 7 günün ortalamasını önceki 7 günle karşılaştırır. Yüzdeler gerçek
ölçümdür (tahmin değil); Google'ın 0-100 ölçeğindeki ilgi değerine dayanır.
"""

import random
import time


def weekly_change(series):
    """Son 7 gün ortalaması / önceki 7 gün ortalaması -> yüzde değişim."""
    vals = [float(v) for v in series if v is not None]
    if len(vals) < 14:
        return None
    last = sum(vals[-7:]) / 7
    prev = sum(vals[-14:-7]) / 7
    if prev == 0:
        return 100.0 if last > 0 else 0.0
    return round((last - prev) / prev * 100, 1)


def fetch_google_trends(keywords, geo="US"):
    """pytrends ile anahtar kelimelerin 30 günlük eğrilerini alır. {kelime: [değerler]}"""
    from pytrends.request import TrendReq

    client = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
    result = {}
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        for attempt in range(4):
            try:
                client.build_payload(batch, timeframe="today 1-m", geo=geo)
                df = client.interest_over_time()
                for kw in batch:
                    if kw in df.columns:
                        result[kw] = [int(x) for x in df[kw].tolist()]
                break
            except Exception as e:  # çoğunlukla 429 (çok fazla istek)
                wait = 20 * (attempt + 1) + random.uniform(0, 5)
                print(f"  Google Trends bekletiyor ({e.__class__.__name__}), {wait:.0f} sn")
                time.sleep(wait)
        time.sleep(random.uniform(6, 10))
    return result


def build_products(keywords, history, today, geo="US", fetch=fetch_google_trends):
    """Talep Borsası satırlarını hazırlar ve geçmişi günceller.

    keywords: [{"keyword": "felt plant cover", "label": "Keçe saksı örtüsü", "origin": "..."}]
    history:  data/history.json içeriği (yerinde güncellenir)
    """
    kw_list = [k["keyword"] for k in keywords]
    fetched = fetch(kw_list, geo=geo) if kw_list else {}

    rows = []
    for k in keywords:
        kw = k["keyword"]
        series = fetched.get(kw)
        stale = False
        if series:
            history[kw] = {"series": series, "updated": today, "label": k.get("label", kw)}
        elif kw in history:
            series = history[kw]["series"]
            stale = True
        if not series:
            continue
        change = weekly_change(series)
        if change is None:
            continue
        rows.append({
            "name": k.get("label") or kw,
            "keyword": kw,
            "origin": k.get("origin", ""),
            "change": change,
            "spark": series[-14:],
            "stale": stale,
        })
    rows.sort(key=lambda r: r["change"], reverse=True)
    return rows, len(fetched)
