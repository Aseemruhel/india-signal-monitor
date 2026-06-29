#!/usr/bin/env python3
"""
India Geopolitical Signal Monitor
Crawls RSS feeds, Reddit, and public sources for signals relevant to India:
- Pakistan narratives targeting India
- Western media criticism of India
- Neighbour country developments
- Protest calls / internal dissent signals
- General India geopolitics
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
    ],
    "pakistan_narratives": [
        {"name": "Dawn - Pakistan", "url": "https://www.dawn.com/feeds/home"},
        {"name": "The News International", "url": "https://www.thenews.com.pk/rss/1/1"},
        {"name": "Geo News", "url": "https://www.geo.tv/rss/1"},
        {"name": "Express Tribune", "url": "https://tribune.com.pk/feed/india"},
        {"name": "ARY News", "url": "https://arynews.tv/feed/"},
        {"name": "Pakistan Observer", "url": "https://pakobserver.net/feed/"},
    ],
    "western_media": [
        {"name": "BBC South Asia", "url": "http://feeds.bbci.co.uk/news/world/south_asia/rss.xml"},
        {"name": "The Guardian - India", "url": "https://www.theguardian.com/world/india/rss"},
        {"name": "Al Jazeera - Asia", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "Reuters - India", "url": "https://feeds.reuters.com/reuters/INtopNews"},
        {"name": "NYT - Asia Pacific", "url": "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml"},
        {"name": "Washington Post - World", "url": "https://feeds.washingtonpost.com/rss/world"},
        {"name": "Foreign Policy", "url": "https://foreignpolicy.com/feed/"},
        {"name": "The Diplomat", "url": "https://thediplomat.com/feed/"},
        {"name": "Asia Times", "url": "https://asiatimes.com/feed/"},
    ],
    "neighbours": [
        {"name": "Daily Star - Bangladesh", "url": "https://www.thedailystar.net/frontpage/rss.xml"},
        {"name": "The Kathmandu Post", "url": "https://kathmandupost.com/rss"},
        {"name": "Daily Mirror - Sri Lanka", "url": "https://www.dailymirror.lk/rss"},
        {"name": "MyRepublica - Nepal", "url": "https://myrepublica.nagariknetwork.com/feed"},
        {"name": "Bhutan Broadcasting Service", "url": "https://www.bbs.bt/news/feed/"},
        {"name": "Mizzima - Myanmar", "url": "https://mizzima.com/feed"},
        {"name": "Afghan Voice Agency", "url": "https://www.ava.af/en/feed/"},
    ],
    "global_strategic": [
        {"name": "Hacker News (geopolitics via HN)", "url": "https://hnrss.org/newest?q=india+china+pakistan"},
        {"name": "Reddit r/geopolitics", "url": "https://www.reddit.com/r/geopolitics/.rss"},
        {"name": "Reddit r/india", "url": "https://www.reddit.com/r/india/.rss"},
        {"name": "Reddit r/worldnews India flair", "url": "https://www.reddit.com/r/worldnews/search.rss?q=india&sort=hot&restrict_sr=1"},
        {"name": "Google News - India", "url": "https://news.google.com/rss/search?q=india+geopolitics&hl=en-IN&gl=IN&ceid=IN:en"},
        {"name": "Google News - India Pakistan", "url": "https://news.google.com/rss/search?q=india+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "Google News - India China", "url": "https://news.google.com/rss/search?q=india+china+border&hl=en&gl=US&ceid=US:en"},
    ],
}

# ── SIGNAL KEYWORDS ───────────────────────────────────────────────────────────

SIGNAL_KEYWORDS = {
    "pakistan_narrative": [
        "kashmir", "azad kashmir", "pok", "isi", "imf pakistan", "ceasefire",
        "loc violation", "surgical strike", "india pakistan", "hafiz saeed",
        "masood azhar", "pakistan condemns india", "india aggression",
        "hindu nationalism", "rss", "bjp communal", "islamophobia india",
        "minority persecution india", "modi fascism", "hindutva",
    ],
    "western_criticism": [
        "india democratic backsliding", "press freedom india", "india authoritarian",
        "india human rights", "minority rights india", "religious freedom india",
        "india crackdown", "india internet shutdown", "india surveillance",
        "india protest", "india dissent", "india ngo", "fcra india",
        "india ranking", "india corruption", "india inequality",
        "india caste discrimination", "india modi criticism",
    ],
    "protest_dissent": [
        "protest india", "bandh", "demonstration india", "strike india",
        "farmers protest", "student protest india", "opposition india",
        "rally india", "march india", "india unrest", "police lathi charge",
        "india sedition", "uapa arrest", "india crackdown", "dissent",
        "india shutdown", "india agitation",
    ],
    "neighbour_hostile": [
        "nepal india border", "nepal china", "nepal treaty india",
        "bangladesh india", "hasina india", "bangladesh protest india",
        "sri lanka india", "maldives india", "china maldives", "india out maldives",
        "bhutan china", "bhutan india", "myanmar india border",
        "afghanistan india", "taliban india", "china india neighbour",
        "india influence", "india hegemony", "india interference",
    ],
    "strategic_military": [
        "arunachal pradesh china", "doklam", "galwan", "lac india",
        "india china border", "india nuclear", "india missile",
        "india defence", "india military", "india navy", "indian ocean",
        "quad india", "india us relations", "india russia sanctions",
        "india arms", "india drdo", "india agni", "india brahmos",
    ],
    "terrorism_security": [
        "india terror", "naxal", "maoist india", "jem", "let",
        "india blast", "india attack", "india intelligence", "raw india",
        "india security", "india separatist", "khalistan", "khalistani",
        "india northeast insurgency", "manipur", "kashmir militants",
    ],
}

# ── IMPORTANCE SCORING ────────────────────────────────────────────────────────

HIGH_IMPORTANCE_TRIGGERS = [
    "breaking", "urgent", "exclusive", "ceasefire", "war", "strike",
    "nuclear", "crisis", "emergency", "condemns", "sanctions", "expelled",
    "killed", "attack", "blast", "invasion", "border clash", "escalation",
    "protest", "bandh", "arrest", "coup", "resignation",
]

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
    return min(score, 10)  # cap at 10

def detect_signals(text):
    text_lower = text.lower()
    detected = []
    for category, keywords in SIGNAL_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                detected.append(category)
                break
    return list(set(detected))

# ── FEED FETCHER ──────────────────────────────────────────────────────────────

def fetch_feed(feed_info, category, max_items=8):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; IndiaSignalMonitor/1.0)"}
        resp = requests.get(feed_info["url"], headers=headers, timeout=12)
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries[:max_items]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            # Strip HTML tags from summary
            summary = re.sub(r'<[^>]+>', '', summary)[:400]
            link = entry.get("link", "")
            pub = entry.get("published", entry.get("updated", ""))

            combined_text = f"{title} {summary}"
            signals = detect_signals(combined_text)
            importance = score_importance(combined_text)

            # For Pakistan/neighbour/western sources: only include if India-relevant
            if category in ["pakistan_narratives", "neighbours", "western_media"]:
                if importance == 0 and not signals:
                    continue

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
        print(f"  ✗ Failed: {feed_info['name']} — {e}")
    return items

# ── REDDIT JSON FALLBACK ──────────────────────────────────────────────────────

def fetch_reddit_json(subreddit, limit=15):
    items = []
    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        headers = {"User-Agent": "IndiaSignalMonitor/1.0"}
        resp = requests.get(url, headers=headers, timeout=12)
        data = resp.json()
        for post in data["data"]["children"]:
            p = post["data"]
            title = p.get("title", "")
            selftext = p.get("selftext", "")[:300]
            link = f"https://reddit.com{p.get('permalink', '')}"
            score = p.get("score", 0)
            combined = f"{title} {selftext}"
            signals = detect_signals(combined)
            importance = score_importance(combined)
            if importance > 0 or signals:
                items.append({
                    "title": title,
                    "summary": selftext or f"Reddit score: {score} | Comments: {p.get('num_comments',0)}",
                    "link": link,
                    "source": f"Reddit r/{subreddit}",
                    "category": "global_strategic",
                    "signals": signals,
                    "importance": importance,
                    "published": datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc).isoformat(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
    except Exception as e:
        print(f"  ✗ Reddit r/{subreddit} failed — {e}")
    return items

# ── MAIN CRAWLER ──────────────────────────────────────────────────────────────

def crawl_all():
    all_items = []
    stats = defaultdict(int)

    print(f"\n{'='*60}")
    print(f"India Signal Monitor — Crawl started {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    for category, feed_list in FEEDS.items():
        print(f"\n[{category.upper()}]")
        for feed in feed_list:
            print(f"  Fetching: {feed['name']} ...", end=" ")
            items = fetch_feed(feed, category)
            print(f"{len(items)} items")
            all_items.extend(items)
            stats[category] += len(items)
            time.sleep(0.5)  # polite delay

    # Reddit JSON direct fetch
    print("\n[REDDIT DIRECT]")
    for sub in ["india", "geopolitics", "worldnews", "pakistan", "chinaindia"]:
        print(f"  Fetching r/{sub} ...", end=" ")
        items = fetch_reddit_json(sub)
        print(f"{len(items)} relevant items")
        all_items.extend(items)

    # Deduplicate by title similarity
    seen_titles = set()
    deduped = []
    for item in all_items:
        title_key = re.sub(r'\W+', '', item["title"].lower())[:60]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(item)

    # Sort by importance descending
    deduped.sort(key=lambda x: x["importance"], reverse=True)

    # Build summary stats
    signal_counts = defaultdict(int)
    for item in deduped:
        for sig in item["signals"]:
            signal_counts[sig] += 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": len(deduped),
        "category_stats": dict(stats),
        "signal_summary": dict(signal_counts),
        "top_signals": sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        "items": deduped,
    }

    # Write output
    import os
    os.makedirs("data", exist_ok=True)
    with open("data/topics.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Also write a lightweight summary
    summary = {
        "generated_at": output["generated_at"],
        "total_items": output["total_items"],
        "signal_summary": output["signal_summary"],
        "top_signals": output["top_signals"],
        "top_items": deduped[:50],  # top 50 by importance for quick dashboard load
    }
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ Crawl complete. {len(deduped)} unique items written to data/topics.json")
    print(f"Signal breakdown: {dict(signal_counts)}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    crawl_all()
