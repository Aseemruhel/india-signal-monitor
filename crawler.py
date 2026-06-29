#!/usr/bin/env python3
"""
India Geopolitical Signal Monitor
Only fetches and stores content relevant to India.
"""

import json
import feedparser
import requests
import re
from datetime import datetime, timezone
from collections import defaultdict
import time

# ── FEED DEFINITIONS ──────────────────────────────────────────────────────────

FEEDS = {
    "india_geopolitics": [
        {"name": "The Hindu - National", "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
        {"name": "The Hindu - International", "url": "https://www.thehindu.com/news/international/feeder/default.rss"},
        {"name": "Indian Express - India", "url": "https://indianexpress.com/section/india/feed/"},
        {"name": "Indian Express - World", "url": "https://indianexpress.com/section/world/feed/"},
        {"name": "LiveMint - Politics", "url": "https://www.livemint.com/rss/politics"},
        {"name": "Hindustan Times", "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"},
        {"name": "NDTV India", "url": "https://feeds.feedburner.com/ndtvnews-india-news"},
        {"name": "Deccan Herald", "url": "https://www.deccanherald.com/rss-feeds/feed-national"},
        {"name": "The Wire", "url": "https://thewire.in/feed"},
        {"name": "Scroll.in", "url": "https://scroll.in/feed"},
        {"name": "FirstPost India", "url": "https://www.firstpost.com/rss/india.xml"},
        {"name": "Tribune India", "url": "https://www.tribuneindia.com/rss/feed?category=nation"},
    ],
    "pakistan_narratives": [
        {"name": "Dawn - Pakistan", "url": "https://www.dawn.com/feeds/home"},
        {"name": "The News International", "url": "https://www.thenews.com.pk/rss/1/1"},
        {"name": "Geo News", "url": "https://www.geo.tv/rss/1"},
        {"name": "Express Tribune", "url": "https://tribune.com.pk/feed/"},
        {"name": "ARY News", "url": "https://arynews.tv/feed/"},
        {"name": "Pakistan Observer", "url": "https://pakobserver.net/feed/"},
        {"name": "The Nation Pakistan", "url": "https://nation.com.pk/rss/"},
    ],
    "western_media": [
        {"name": "BBC South Asia", "url": "http://feeds.bbci.co.uk/news/world/south_asia/rss.xml"},
        {"name": "The Guardian - India", "url": "https://www.theguardian.com/world/india/rss"},
        {"name": "Al Jazeera - Asia", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "The Diplomat - India", "url": "https://thediplomat.com/feed/"},
        {"name": "Asia Times", "url": "https://asiatimes.com/feed/"},
        {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/"},
        # Google News targeted searches — India specific
        {"name": "GNews: India Pakistan", "url": "https://news.google.com/rss/search?q=india+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: India China border", "url": "https://news.google.com/rss/search?q=india+china+border&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: India criticism", "url": "https://news.google.com/rss/search?q=india+human+rights+OR+india+press+freedom+OR+india+democracy&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Kashmir", "url": "https://news.google.com/rss/search?q=kashmir+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: India protest", "url": "https://news.google.com/rss/search?q=india+protest+OR+india+bandh+OR+india+agitation&hl=en&gl=IN&ceid=IN:en"},
    ],
    "neighbours": [
        {"name": "Daily Star - Bangladesh", "url": "https://www.thedailystar.net/frontpage/rss.xml"},
        {"name": "The Kathmandu Post", "url": "https://kathmandupost.com/rss"},
        {"name": "Daily Mirror - Sri Lanka", "url": "https://www.dailymirror.lk/rss"},
        {"name": "MyRepublica - Nepal", "url": "https://myrepublica.nagariknetwork.com/feed"},
        {"name": "Mizzima - Myanmar", "url": "https://mizzima.com/feed"},
        {"name": "GNews: Nepal India", "url": "https://news.google.com/rss/search?q=nepal+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Bangladesh India", "url": "https://news.google.com/rss/search?q=bangladesh+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Maldives India", "url": "https://news.google.com/rss/search?q=maldives+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Sri Lanka India", "url": "https://news.google.com/rss/search?q=sri+lanka+india&hl=en&gl=US&ceid=US:en"},
    ],
    "social_india": [
        # Reddit — India-specific only
        {"name": "Reddit r/india Hot", "url": "https://www.reddit.com/r/india/hot.json?limit=25"},
        {"name": "Reddit r/IndiaSpeaks", "url": "https://www.reddit.com/r/IndiaSpeaks/hot.json?limit=20"},
        {"name": "Reddit r/indiadiscussion", "url": "https://www.reddit.com/r/indiadiscussion/hot.json?limit=15"},
        {"name": "Reddit r/geopolitics India", "url": "https://www.reddit.com/r/geopolitics/search.json?q=india&sort=hot&restrict_sr=1&limit=15"},
        {"name": "Reddit r/worldnews India", "url": "https://www.reddit.com/r/worldnews/search.json?q=india&sort=hot&restrict_sr=1&t=day&limit=20"},
        {"name": "Reddit r/kashmirconflict", "url": "https://www.reddit.com/r/kashmirconflict/hot.json?limit=15"},
        {"name": "HN: India geopolitics", "url": "https://hnrss.org/newest?q=india+geopolitics+OR+india+pakistan+OR+india+china"},
    ],
}

# ── INDIA RELEVANCE — must contain at least one of these ──────────────────────

INDIA_MUST_MATCH = [
    "india", "indian", "bharat", "bharatiya", "modi", "delhi", "mumbai",
    "kashmir", "hindutva", "rss ", "bjp", "congress party", "lok sabha",
    "rajya sabha", "indian army", "indian navy", "indian air force",
    "pakistan india", "india pakistan", "india china", "india us",
    "india russia", "india israel", "india nepal", "india bangladesh",
    "india sri lanka", "india maldives", "india myanmar", "india bhutan",
    "india afghanistan", "new delhi", "hindu nationalist", "hindus",
    "arunachal", "ladakh", "doklam", "galwan", "loc ", "line of control",
    "brahmos", "drdo", "isro", "quad india", "brics india", "sco india",
    "khalistan", "naxal", "maoist india", "northeast india", "manipur",
    "assam", "punjab india", "farmers india", "rupee", "rbi india",
]

# ── SIGNAL KEYWORDS ───────────────────────────────────────────────────────────

SIGNAL_KEYWORDS = {
    "pakistan_narrative": [
        "kashmir", "azad kashmir", "pok", "isi", "ceasefire india",
        "loc violation", "surgical strike", "india pakistan", "hafiz saeed",
        "masood azhar", "pakistan condemns india", "india aggression",
        "hindutva", "rss", "bjp communal", "islamophobia india",
        "minority persecution india", "modi fascism", "hindu nationalist",
        "india cruelty", "india atrocities", "occupied kashmir",
        "indian forces", "kashmir human rights",
    ],
    "western_criticism": [
        "india democratic backsliding", "press freedom india", "india authoritarian",
        "india human rights", "minority rights india", "religious freedom india",
        "india crackdown", "india internet shutdown", "india surveillance",
        "india dissent", "india ngo", "fcra india", "india ranking",
        "india corruption", "india inequality", "india caste",
        "india modi criticism", "india freedom", "india repression",
        "india journalists", "rsf india", "cpj india",
    ],
    "protest_dissent": [
        "protest india", "bandh", "demonstration india", "strike india",
        "farmers protest", "student protest india", "opposition india",
        "rally india", "march india", "india unrest", "lathi charge",
        "india sedition", "uapa", "india agitation", "india shutdown",
        "india demands", "india blockade", "india workers strike",
    ],
    "neighbour_hostile": [
        "nepal india border", "nepal china india", "nepal treaty india",
        "bangladesh india", "bangladesh protest india", "india out maldives",
        "china maldives", "bhutan china india", "myanmar india border",
        "afghanistan india", "taliban india", "india hegemony",
        "india interference", "india influence neighbour",
        "anti india", "india imperialism",
    ],
    "strategic_military": [
        "arunachal pradesh china", "doklam", "galwan", "lac india",
        "india china border", "india nuclear", "india missile",
        "india defence", "india navy", "indian ocean", "quad india",
        "india us relations", "india russia sanctions", "india arms",
        "drdo", "agni", "brahmos", "india military exercise",
        "india deployment", "india troops", "india airforce",
    ],
    "terrorism_security": [
        "india terror", "naxal", "maoist india", "jem", "let ",
        "india blast", "india attack", "india intelligence",
        "india separatist", "khalistan", "khalistani",
        "india northeast insurgency", "kashmir militants",
        "india security forces", "encounter kashmir",
    ],
}

HIGH_IMPORTANCE_TRIGGERS = [
    "breaking", "urgent", "exclusive", "ceasefire", "war", "strike",
    "nuclear", "crisis", "emergency", "condemns india", "sanctions india",
    "expelled", "killed", "attack", "blast", "invasion", "border clash",
    "escalation", "protest india", "bandh", "arrest", "coup",
    "india tension", "india warns", "india responds",
]

def is_india_relevant(text):
    """Hard filter — must mention India in some form."""
    text_lower = text.lower()
    for kw in INDIA_MUST_MATCH:
        if kw in text_lower:
            return True
    return False

def score_importance(text):
    text_lower = text.lower()
    score = 0
    for trigger in HIGH_IMPORTANCE_TRIGGERS:
        if trigger in text_lower:
            score += 2
    for category, keywords in SIGNAL_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                score += 1
    return min(score, 10)

def detect_signals(text):
    text_lower = text.lower()
    detected = []
    for category, keywords in SIGNAL_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                detected.append(category)
                break
    return list(set(detected))

# ── RSS FEED FETCHER ──────────────────────────────────────────────────────────

def fetch_rss(feed_info, category, max_items=10):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; IndiaSignalMonitor/1.0)"}
        resp = requests.get(feed_info["url"], headers=headers, timeout=12)
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries[:max_items]:
            title = entry.get("title", "").strip()
            summary = re.sub(r'<[^>]+>', '', entry.get("summary", entry.get("description", ""))).strip()[:400]
            link = entry.get("link", "")
            pub = entry.get("published", entry.get("updated", ""))
            combined = f"{title} {summary}"

            # HARD FILTER: must be India relevant
            if not is_india_relevant(combined):
                continue

            signals = detect_signals(combined)
            importance = score_importance(combined)

            items.append({
                "title": title,
                "summary": summary[:300],
                "link": link,
                "source": feed_info["name"],
                "category": category,
                "signals": signals,
                "importance": importance,
                "published": pub,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"  ✗ {feed_info['name']} — {e}")
    return items

# ── REDDIT JSON FETCHER ───────────────────────────────────────────────────────

def fetch_reddit_json(feed_info, category):
    items = []
    try:
        headers = {"User-Agent": "IndiaSignalMonitor/1.0"}
        resp = requests.get(feed_info["url"], headers=headers, timeout=12)
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        for post in posts:
            p = post["data"]
            title = p.get("title", "")
            selftext = p.get("selftext", "")[:300]
            link = f"https://reddit.com{p.get('permalink', '')}"
            score = p.get("score", 0)
            combined = f"{title} {selftext}"

            # HARD FILTER
            if not is_india_relevant(combined):
                continue

            signals = detect_signals(combined)
            importance = score_importance(combined)
            # For Reddit, boost importance by engagement
            if score > 1000:
                importance = min(importance + 2, 10)
            elif score > 500:
                importance = min(importance + 1, 10)

            pub_ts = p.get("created_utc", 0)
            items.append({
                "title": title,
                "summary": selftext or f"👍 {score} upvotes · 💬 {p.get('num_comments',0)} comments",
                "link": link,
                "source": feed_info["name"],
                "category": category,
                "signals": signals,
                "importance": importance,
                "reddit_score": score,
                "published": datetime.fromtimestamp(pub_ts, tz=timezone.utc).isoformat() if pub_ts else "",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"  ✗ {feed_info['name']} — {e}")
    return items

# ── MAIN ──────────────────────────────────────────────────────────────────────

def crawl_all():
    all_items = []
    stats = defaultdict(int)

    print(f"\n{'='*60}")
    print(f"India Signal Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    REDDIT_URLS = [f["url"] for f in FEEDS.get("social_india", []) if "reddit.com" in f["url"]]

    for category, feed_list in FEEDS.items():
        print(f"\n[{category.upper()}]")
        for feed in feed_list:
            print(f"  {feed['name']} ...", end=" ", flush=True)
            # Route Reddit JSON feeds differently
            if "reddit.com" in feed["url"] and feed["url"].endswith(".json") or "search.json" in feed["url"]:
                items = fetch_reddit_json(feed, category)
            else:
                items = fetch_rss(feed, category)
            print(f"{len(items)} India-relevant items")
            all_items.extend(items)
            stats[category] += len(items)
            time.sleep(0.4)

    # Deduplicate by title
    seen = set()
    deduped = []
    for item in all_items:
        key = re.sub(r'\W+', '', item["title"].lower())[:60]
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    # Sort: importance desc, then by date desc
    deduped.sort(key=lambda x: (x["importance"], x.get("reddit_score", 0)), reverse=True)

    # Signal summary
    signal_counts = defaultdict(int)
    for item in deduped:
        for sig in item.get("signals", []):
            signal_counts[sig] += 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(deduped),
        "category_stats": dict(stats),
        "signal_summary": dict(signal_counts),
        "top_signals": sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "items": deduped,
    }

    import os
    os.makedirs("data", exist_ok=True)
    with open("data/topics.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # summary.json — ALL items (frontend reads top_items)
    summary = {
        "generated_at": output["generated_at"],
        "total_items": output["total_items"],
        "signal_summary": output["signal_summary"],
        "top_signals": output["top_signals"],
        "top_items": deduped,  # ALL items, not just top 50
    }
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ Done. {len(deduped)} India-relevant items saved.")
    print(f"  Signal breakdown: {dict(signal_counts)}")
    print(f"  Category stats: {dict(stats)}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    crawl_all()
