"""Trend Radar günlük çalışma: veriyi topla -> yapay zekayla yorumla -> data/latest.json yaz."""

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import analyze
import config
import demand
import sources

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def run_source(status, name, fn, *args, **kwargs):
    print(f"-> {name}")
    try:
        result = fn(*args, **kwargs)
        status[name] = {"ok": True, "count": len(result)}
        print(f"   {len(result)} kayıt")
        return result
    except Exception as e:
        status[name] = {"ok": False, "error": str(e)[:200]}
        print(f"   HATA: {e}")
        traceback.print_exc()
        return []


def read_watchlist():
    items = []
    path = Path(__file__).with_name("watchlist.txt")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kw, _, label = line.partition("|")
        items.append({"keyword": kw.strip().lower(), "label": label.strip() or kw.strip(), "origin": "İzleme listen"})
    return items


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def update_trends(env, status):
    """İnternette Gündem: kaynakları tara, yapay zekayla yorumla. (3 saatte bir)"""
    signals = {}
    signals["tiktok"] = run_source(status, "TikTok", sources.tiktok_hashtags, config.COUNTRY)

    if env.get("YOUTUBE_API_KEY"):
        signals["youtube"] = run_source(status, "YouTube", sources.youtube_trending, env["YOUTUBE_API_KEY"], config.COUNTRY)
    else:
        status["YouTube"] = {"ok": False, "error": "YOUTUBE_API_KEY eklenmemiş"}

    signals["reddit"] = run_source(
        status, "Reddit", sources.reddit_top, config.SUBREDDITS,
        env.get("REDDIT_CLIENT_ID"), env.get("REDDIT_CLIENT_SECRET"),
    )
    signals["google"] = run_source(status, "Google", sources.google_trending_searches, config.COUNTRY)

    if not any(signals.values()):
        return None  # hiçbir kaynak çalışmadı: önceki akımlar korunur

    trends, ai_ok = [], False
    if env.get("GEMINI_API_KEY"):
        print("-> Gemini analizi")
        try:
            trends = analyze.analyze(
                signals, env["GEMINI_API_KEY"],
                env.get("GEMINI_MODEL") or config.GEMINI_MODEL_DEFAULT,
                config.COUNTRY, config.MAX_TRENDS,
            )
            ai_ok = True
            print(f"   {len(trends)} akım")
        except Exception as e:
            print(f"   HATA: {e}")
            status["Yapay zeka"] = {"ok": False, "error": str(e)[:200]}
    else:
        status["Yapay zeka"] = {"ok": False, "error": "GEMINI_API_KEY eklenmemiş"}
    if not trends:
        trends = analyze.fallback_trends(signals, config.MAX_TRENDS)
    if ai_ok:
        status["Yapay zeka"] = {"ok": True, "count": len(trends)}
    return trends


def update_products(trends, status, now):
    """Talep Borsası: izleme listesi + akımlardan gelen ürünlerin haftalık talebi. (günde 1 kez)"""
    today = now.date().isoformat()
    keywords, seen = [], set()
    for k in read_watchlist() + [
        {**pk, "origin": f"Akım: {t['name']}"} for t in trends for pk in t.get("product_keywords", [])
    ]:
        if k["keyword"] not in seen:
            seen.add(k["keyword"])
            keywords.append(k)
    keywords = keywords[: config.MAX_PRODUCTS]

    history = load_json(DATA / "history.json", {})
    print(f"-> Google Trends talep ölçümü ({len(keywords)} ürün)")
    try:
        products, fetched = demand.build_products(keywords, history, today, config.COUNTRY)
        status["Talep ölçümü"] = {"ok": fetched > 0, "count": fetched}
        if fetched == 0:
            status["Talep ölçümü"]["error"] = "Google Trends yanıt vermedi, önceki değerler gösteriliyor"
    except Exception as e:
        traceback.print_exc()
        status["Talep ölçümü"] = {"ok": False, "error": str(e)[:200]}
        return None

    cutoff = (now - timedelta(days=45)).date().isoformat()
    for kw in list(history):
        if history[kw].get("updated", today) < cutoff:
            del history[kw]
    (DATA / "history.json").write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
    return products


def main():
    # Çalışma türü: "trends" (gündem), "demand" (talep borsası) ya da "all" (ikisi)
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").strip() or "all"
    if mode not in ("trends", "demand", "all"):
        sys.exit(f"Bilinmeyen çalışma türü: {mode}")
    print(f"Çalışma türü: {mode}")

    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="minutes")
    env = os.environ
    DATA.mkdir(exist_ok=True)

    out = load_json(DATA / "latest.json", {})
    out.update({"country": config.COUNTRY, "sample": False})
    status = dict(out.get("status") or {})
    changed = False

    if mode in ("trends", "all"):
        new_status = {}
        trends = update_trends(env, new_status)
        status.update(new_status)
        if trends is not None:
            out["trends"] = trends
            out["trends_updated_at"] = stamp
            changed = True
        else:
            print("Hiçbir kaynaktan veri gelmedi; önceki akımlar korunuyor.")

    if mode in ("demand", "all"):
        products = update_products(out.get("trends") or [], status, now)
        if products is not None:
            out["products"] = products
            out["products_updated_at"] = stamp
            changed = True

    out["status"] = status
    if changed:
        out["generated_at"] = stamp
    out.setdefault("trends", [])
    out.setdefault("products", [])
    (DATA / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Bitti:", json.dumps(status, ensure_ascii=False))
    if not changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
