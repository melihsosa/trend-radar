"""Gemini ile toplanan sinyalleri yorumlayıp akım kartlarını yazar."""

import json
import time

import requests

PROMPT = """Sen bir e-ticaret trend analistisin. Amacın, bir satıcının Etsy ve benzeri
yerlerde satabileceği ürünleri erken fark etmesine yardım etmek.

Aşağıda {country} için bugün toplanan GERÇEK veriler var: TikTok Creative Center'daki
popüler hashtag'ler, YouTube trendleri, Reddit'in haftalık en popüler gönderileri ve
Google'da hızla yükselen aramalar.

Görevin:
1. Gençlerin ürettiği, somut kültürel akımları bul (ör. bir estetik, bir söz kalıbı,
   bir yaşam tarzı hareketi, viral bir ürün). "Moda" veya "ev dekoru" gibi genel
   kategoriler YAZMA. Spor maçı, siyaset, ünlü haberi gibi ürüne dönüşmeyecek konuları atla.
2. Birden fazla kaynakta görünen akımları öne çıkar.
3. En fazla {max_trends} akım seç, en umut vericiden başla.
4. SADECE verilen verilere dayan. Veride olmayan bir şeyi uydurma. Emin değilsen
   o akımı yazma.

Yanıtı Türkçe yaz (akım adları orijinal dilinde kalabilir). Sadece şu JSON'u döndür:
{{
  "trends": [
    {{
      "name": "akımın kısa adı",
      "heat": "Yeni çıktı" | "Yükseliyor" | "Hızla yükseliyor" | "Zirvede",
      "desc": "akım nedir, 1-2 cümle",
      "why": "hangi veride nasıl göründüğü, 1 cümle",
      "sources": ["TikTok", "YouTube", "Reddit", "Google"],
      "idea": "satılabilecek somut ürün fikri",
      "product_keywords": ["Google'da aranacak 1-2 İngilizce ürün araması"],
      "product_labels": ["bu aramaların Türkçe kısa adı, aynı sırayla"]
    }}
  ]
}}

VERİLER:
{signals}
"""


def compact_signals(signals):
    """Gemini'ye gidecek veriyi sadeleştirir (kota ve doğruluk için)."""
    out = {}
    if signals.get("tiktok"):
        out["tiktok_hashtags"] = [
            {k: v for k, v in h.items() if k in ("hashtag", "rank", "rank_change", "is_new", "posts", "industry") and v is not None}
            for h in signals["tiktok"][:40]
        ]
    if signals.get("youtube"):
        out["youtube_trending"] = [
            {"title": v["title"], "tags": v.get("tags", [])[:5], "views": v.get("views")}
            for v in signals["youtube"][:40]
        ]
    if signals.get("reddit"):
        out["reddit_top_week"] = [
            {k: v for k, v in p.items() if k in ("sub", "title", "score") and v is not None}
            for p in signals["reddit"][:80]
        ]
    if signals.get("google"):
        out["google_rising_searches"] = signals["google"][:25]
    return json.dumps(out, ensure_ascii=False)


def analyze(signals, api_key, model, country="US", max_trends=8):
    prompt = PROMPT.format(
        country=country, max_trends=max_trends, signals=compact_signals(signals)
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
    }
    # Anahtar adres satırında değil başlıkta gönderilir; böylece hata mesajlarına sızmaz.
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    # Seçilen model bulunamazsa (Google eski modelleri kaldırıyor) o an mevcut olan
    # en yeni "flash" modelini Google'a sorup onu kullan.
    models = [model]
    try:
        models += [m for m in available_flash_models(api_key) if m != model]
    except Exception as e:
        print(f"   model listesi alınamadı: {e.__class__.__name__}")
    models += [m for m in FALLBACK_MODELS if m not in models]
    last_err = None
    for m in models[:5]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        for attempt in range(4):
            r = requests.post(url, headers=headers, json=body, timeout=120)
            if r.status_code in (429, 500, 503):
                last_err = f"{m}: HTTP {r.status_code} {_err_msg(r)}"
                time.sleep(30 * (attempt + 1))
                continue
            if r.status_code == 404:
                last_err = f"{m}: model bulunamadı"
                break  # sıradaki modeli dene
            if not r.ok:
                raise RuntimeError(f"Gemini {m}: HTTP {r.status_code} {_err_msg(r)}")
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"   model: {m}")
            return parse_trends(text, max_trends)
    raise RuntimeError(f"Gemini yanıt vermedi: {last_err}")


FALLBACK_MODELS = ["gemini-flash-latest"]
_SKIP = ("lite", "tts", "live", "image", "audio", "transcribe", "embedding", "exp", "thinking", "translate")


def _version_key(name):
    """'gemini-3.8-flash' -> (3, 8); sürümü olmayanlar sona."""
    import re
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2) or 0))


def available_flash_models(api_key):
    """Anahtarın erişebildiği, metin üretebilen 'flash' modellerini yeniden eskiye sıralar."""
    r = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": api_key}, params={"pageSize": 200}, timeout=30,
    )
    r.raise_for_status()
    names = []
    for m in r.json().get("models", []):
        name = m.get("name", "").replace("models/", "")
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        if "flash" not in name or any(s in name for s in _SKIP):
            continue
        names.append(name)
    # Önce kararlı sürümler, sonra "preview"; her grupta en yeni sürüm önce.
    stable = sorted([n for n in names if "preview" not in n], key=_version_key, reverse=True)
    preview = sorted([n for n in names if "preview" in n], key=_version_key, reverse=True)
    return stable + preview


def _err_msg(resp):
    """Gemini'nin hata açıklamasını kısa biçimde döndürür."""
    try:
        return resp.json()["error"]["message"][:200]
    except Exception:
        return resp.text[:200]


ALLOWED_HEAT = {"Yeni çıktı", "Yükseliyor", "Hızla yükseliyor", "Zirvede"}


def parse_trends(text, max_trends=8):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(text)
    trends = []
    for t in data.get("trends", [])[:max_trends]:
        if not t.get("name"):
            continue
        kws = [k for k in (t.get("product_keywords") or []) if isinstance(k, str) and k.strip()][:2]
        labels = t.get("product_labels") or []
        trends.append({
            "name": str(t["name"])[:60],
            "heat": t.get("heat") if t.get("heat") in ALLOWED_HEAT else "Yükseliyor",
            "desc": str(t.get("desc", ""))[:300],
            "why": str(t.get("why", ""))[:200],
            "sources": [s for s in (t.get("sources") or []) if s in ("TikTok", "YouTube", "Reddit", "Google")],
            "idea": str(t.get("idea", ""))[:120],
            "product_keywords": [
                {"keyword": k.strip().lower()[:60], "label": (labels[i] if i < len(labels) and labels[i] else k)[:50]}
                for i, k in enumerate(kws)
            ],
        })
    return trends


def fallback_trends(signals, max_trends=8):
    """Gemini çalışmazsa: yapay zeka yorumu olmadan ham TikTok hashtag'leri."""
    out = []
    if not signals.get("tiktok"):
        for g in (signals.get("google") or [])[:max_trends]:
            out.append({
                "name": g.get("query") or "?",
                "heat": "Yükseliyor",
                "desc": "Yapay zeka yorumu bugün alınamadı; Google'da hızla yükselen aramalardan.",
                "why": ("Yaklaşık arama: " + g["traffic"]) if g.get("traffic") else "",
                "sources": ["Google"],
                "idea": "",
                "product_keywords": [],
            })
        return out
    for h in (signals.get("tiktok") or [])[:max_trends]:
        out.append({
            "name": "#" + h["hashtag"],
            "heat": "Yeni çıktı" if h.get("is_new") else "Yükseliyor",
            "desc": "Yapay zeka yorumu bugün alınamadı; TikTok'taki popüler hashtag listesinden.",
            "why": f"TikTok sıralaması: {h.get('rank', '?')}",
            "sources": ["TikTok"],
            "idea": "",
            "product_keywords": [],
        })
    return out
