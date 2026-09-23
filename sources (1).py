"""Veri kaynakları. Her fonksiyon bağımsızdır: biri çökerse diğerleri çalışmaya devam eder."""

import base64
import re
import time
import xml.etree.ElementTree as ET

import requests

UA = "TrendRadar/1.0 (personal trend research; github actions)"
TIMEOUT = 30


# ---------------------------------------------------------------- TikTok
def tiktok_hashtags(country="US", period=7, limit=50):
    """TikTok Creative Center'daki 'Popüler hashtag'ler' listesini okur.

    Resmi API olmadığı için sayfayı gerçek bir tarayıcıyla (Playwright) açar ve
    sayfanın kendi yüklediği veriyi yakalar. TikTok sayfayı değiştirirse bu
    bölüm bozulabilir; o durumda diğer kaynaklar çalışmaya devam eder.
    """
    from playwright.sync_api import sync_playwright

    url = (
        "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"
        f"?countryCode={country}&period={period}"
    )
    captured = []

    def on_response(resp):
        if "popular_trend/hashtag/list" in resp.url:
            try:
                captured.append(resp.json())
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page.on("response", on_response)
        # Sayfa arka planda sürekli istek attığı için "tamamen yüklendi" anını beklemiyoruz;
        # iskelet gelince verinin yakalanmasını en fazla 45 saniye bekliyoruz.
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            print(f"   TikTok sayfası yavaş açıldı: {e.__class__.__name__}")
        for _ in range(45):
            if captured:
                break
            page.wait_for_timeout(1000)
            if _ == 15:
                page.mouse.wheel(0, 1500)  # bazı listeler kaydırınca yükleniyor
        page.wait_for_timeout(2000)
        try:
            dom_text = page.inner_text("body")
        except Exception:
            dom_text = ""
        browser.close()

    items = []
    for payload in captured:
        data = payload.get("data") or {}
        for it in data.get("list") or []:
            name = it.get("hashtag_name") or it.get("hashtagName")
            if not name:
                continue
            trend = it.get("trend") or []
            items.append({
                "hashtag": name,
                "rank": it.get("rank"),
                "rank_change": it.get("rank_diff"),
                "is_new": (it.get("rank_diff_type") == 4) or bool(it.get("is_new")),
                "posts": it.get("publish_cnt"),
                "views": it.get("video_views"),
                "industry": (it.get("industry_info") or {}).get("value"),
                "trend": [t.get("value") for t in trend if isinstance(t, dict)],
            })

    if not items:
        # Yedek plan: sayfadaki yazılardan hashtag adlarını çıkar.
        seen = set()
        for tag in re.findall(r"#\s?([A-Za-z0-9_]{3,40})", dom_text):
            if tag.lower() not in seen:
                seen.add(tag.lower())
                items.append({"hashtag": tag, "rank": len(items) + 1})
    if not items:
        raise RuntimeError("TikTok Creative Center'dan veri alınamadı")
    return items[:limit]


# ---------------------------------------------------------------- YouTube
def youtube_trending(api_key, region="US", limit=50):
    """YouTube'un resmi API'si ile o ülkenin 'Trendler' listesini alır."""
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": limit,
        },
        headers={"x-goog-api-key": api_key},  # anahtar adreste değil başlıkta: hata mesajına sızmaz
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for v in r.json().get("items", []):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        out.append({
            "title": sn.get("title"),
            "channel": sn.get("channelTitle"),
            "tags": (sn.get("tags") or [])[:10],
            "views": int(st.get("viewCount", 0) or 0),
            "published": sn.get("publishedAt"),
        })
    return out


# ---------------------------------------------------------------- Reddit
def _reddit_token(client_id, client_secret):
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        headers={"Authorization": f"Basic {auth}", "User-Agent": UA},
        data={"grant_type": "client_credentials"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def reddit_top(subreddits, client_id=None, client_secret=None, per_sub=15):
    """Her topluluğun son bir haftadaki en popüler gönderilerini alır.

    Reddit anahtarı varsa resmi API'yi, yoksa herkese açık RSS akışını dener.
    """
    out, errors = [], []
    token = None
    if client_id and client_secret:
        token = _reddit_token(client_id, client_secret)

    for sub in subreddits:
        try:
            if token:
                r = requests.get(
                    f"https://oauth.reddit.com/r/{sub}/top",
                    params={"t": "week", "limit": per_sub},
                    headers={"Authorization": f"Bearer {token}", "User-Agent": UA},
                    timeout=TIMEOUT,
                )
                r.raise_for_status()
                for c in r.json()["data"]["children"]:
                    d = c["data"]
                    out.append({
                        "sub": sub, "title": d.get("title"),
                        "score": d.get("score"), "comments": d.get("num_comments"),
                    })
            else:
                for attempt in range(3):
                    r = requests.get(
                        f"https://www.reddit.com/r/{sub}/top/.rss",
                        params={"t": "week", "limit": per_sub},
                        headers={"User-Agent": UA},
                        timeout=TIMEOUT,
                    )
                    if r.status_code != 429:
                        break
                    time.sleep(10 * (attempt + 1))  # Reddit "yavaşla" dedi
                r.raise_for_status()
                root = ET.fromstring(r.content)
                ns = {"a": "http://www.w3.org/2005/Atom"}
                for e in root.findall("a:entry", ns)[:per_sub]:
                    out.append({"sub": sub, "title": e.findtext("a:title", "", ns)})
            time.sleep(4)
        except Exception as e:  # tek bir topluluk hatası diğerlerini durdurmasın
            errors.append(f"r/{sub}: {e}")
    if not out:
        raise RuntimeError("; ".join(errors) or "Reddit'ten veri alınamadı")
    return out


# ---------------------------------------------------------------- Google
def google_trending_searches(geo="US"):
    """Google'da son 24 saatte hızla yükselen aramalar (resmi RSS akışı)."""
    urls = [
        f"https://trends.google.com/trending/rss?geo={geo}",
        f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
    ]
    last_err = None
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            r.raise_for_status()
            return parse_google_rss(r.content)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Google Trends RSS alınamadı: {last_err}")


def parse_google_rss(content):
    # Google, ad alanını (namespace) zaman zaman değiştiriyor; etiket adının sonuna bakıyoruz.
    def local(tag):
        return tag.rsplit("}", 1)[-1]

    root = ET.fromstring(content)
    out = []
    for item in root.iter("item"):
        entry = {"query": None, "traffic": "", "news": []}
        for child in item:
            name = local(child.tag)
            if name == "title":
                entry["query"] = (child.text or "").strip()
            elif name == "approx_traffic":
                entry["traffic"] = (child.text or "").strip()
            elif name == "news_item":
                for sub in child:
                    if local(sub.tag) == "news_item_title" and sub.text and len(entry["news"]) < 2:
                        entry["news"].append(sub.text.strip())
        if entry["query"]:
            out.append(entry)
    if not out:
        raise RuntimeError("RSS boş geldi")
    return out
