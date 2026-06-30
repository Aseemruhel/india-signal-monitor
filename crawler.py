#!/usr/bin/env python3
"""
India Geopolitical Signal Monitor
Tracks India-relevant signals + Pakistan/PoK human rights & minority issues
(VOPK, HRCP, Paank, Baloch, Sindhi, PoK minorities, etc.)
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
        {"name": "Reddit r/india Hot", "url": "https://www.reddit.com/r/india/hot.json?limit=25"},
        {"name": "Reddit r/IndiaSpeaks", "url": "https://www.reddit.com/r/IndiaSpeaks/hot.json?limit=20"},
        {"name": "Reddit r/indiadiscussion", "url": "https://www.reddit.com/r/indiadiscussion/hot.json?limit=15"},
        {"name": "Reddit r/geopolitics India", "url": "https://www.reddit.com/r/geopolitics/search.json?q=india&sort=hot&restrict_sr=1&limit=15"},
        {"name": "Reddit r/worldnews India", "url": "https://www.reddit.com/r/worldnews/search.json?q=india&sort=hot&restrict_sr=1&t=day&limit=20"},
        {"name": "Reddit r/kashmirconflict", "url": "https://www.reddit.com/r/kashmirconflict/hot.json?limit=15"},
        {"name": "HN: India geopolitics", "url": "https://hnrss.org/newest?q=india+geopolitics+OR+india+pakistan+OR+india+china"},
    ],
    # ── NEW: Pakistan minority / human-rights / PoK / Baloch monitoring ──────
    "pok_baloch_minorities": [
        # Voice of Karakoram / PoK-focused
        {"name": "GNews: Voice of Karakoram PoK", "url": "https://news.google.com/rss/search?q=%22voice+of+karakoram%22+OR+VOPK&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: PoK Gilgit Baltistan rights", "url": "https://news.google.com/rss/search?q=gilgit+baltistan+rights+OR+gilgit+protest&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: PoK minorities", "url": "https://news.google.com/rss/search?q=%22pakistan+occupied+kashmir%22+minorities+OR+rights&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Azad Kashmir protest", "url": "https://news.google.com/rss/search?q=azad+kashmir+protest+OR+azad+kashmir+rights&hl=en&gl=US&ceid=US:en"},
        # Human Rights Commission of Pakistan (HRCP)
        {"name": "HRCP official RSS", "url": "https://hrcp-web.org/hrcpweb/feed/"},
        {"name": "GNews: HRCP Pakistan", "url": "https://news.google.com/rss/search?q=%22Human+Rights+Commission+of+Pakistan%22+OR+HRCP&hl=en&gl=US&ceid=US:en"},
        # Paank (Baloch human rights org) and general Baloch rights
        {"name": "GNews: Paank Baloch rights", "url": "https://news.google.com/rss/search?q=Paank+Baloch+OR+%22Baloch+human+rights%22&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Balochistan enforced disappearances", "url": "https://news.google.com/rss/search?q=balochistan+%22enforced+disappearance%22+OR+balochistan+missing+persons&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Baloch protest crackdown", "url": "https://news.google.com/rss/search?q=baloch+protest+OR+balochistan+crackdown+OR+BYC+balochistan&hl=en&gl=US&ceid=US:en"},
        {"name": "Balochistan Post", "url": "https://thebalochistanpost.net/feed/"},
        {"name": "Balochwarna News", "url": "https://www.balochwarna.com/feed/"},
        # Sindhi, Pashtun, and general Pakistan minority rights
        {"name": "GNews: Sindhi rights Pakistan", "url": "https://news.google.com/rss/search?q=sindhi+rights+OR+sindh+nationalist+OR+JSMM&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: PTM Pashtun rights", "url": "https://news.google.com/rss/search?q=%22Pashtun+Tahafuz+Movement%22+OR+PTM+Pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Pakistan minorities persecution", "url": "https://news.google.com/rss/search?q=pakistan+minorities+persecution+OR+pakistan+hindu+forced+conversion+OR+pakistan+christian+persecution&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Pakistan blasphemy minorities", "url": "https://news.google.com/rss/search?q=pakistan+blasphemy+law+minority&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews: Ahmadi persecution Pakistan", "url": "https://news.google.com/rss/search?q=ahmadi+persecution+pakistan&hl=en&gl=US&ceid=US:en"},
        # Reddit communities tracking this
        {"name": "Reddit r/Balochistan", "url": "https://www.reddit.com/r/Balochistan/hot.json?limit=15"},
        {"name": "Reddit r/GilgitBaltistan", "url": "https://www.reddit.com/r/GilgitBaltistan/hot.json?limit=10"},
    ],
}

# ── RELEVANCE FILTERS ─────────────────────────────────────────────────────────

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

# Separate relevance check for the PoK/Baloch/minorities category —
# these don't need to mention "India" since they're inherently relevant
# to India's strategic/counter-narrative interest in Pakistan's internal fault lines
POK_BALOCH_MUST_MATCH = [
    "balochistan", "baloch", "gilgit", "baltistan", "pok ", "pok,",
    "azad kashmir", "pakistan occupied kashmir", "sindhi", "sindh",
    "pashtun", "ptm", "hrcp", "human rights commission of pakistan",
    "paank", "vopk", "voice of karakoram", "enforced disappearance",
    "missing persons pakistan", "ahmadi", "blasphemy law", "byc ",
    "baloch yakjehti", "minorities pakistan", "forced conversion",
    "christian persecution pakistan", "hindu pakistan minority",
]

def is_india_relevant(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in INDIA_MUST_MATCH)

def is_pok_baloch_relevant(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in POK_BALOCH_MUST_MATCH)

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
    # NEW signal category
    "pok_baloch_rights": [
        "balochistan", "baloch", "gilgit baltistan", "azad kashmir",
        "pakistan occupied kashmir", "sindhi nationalist", "pashtun tahafuz",
        "hrcp", "paank", "voice of karakoram", "enforced disappearance",
        "missing persons pakistan", "ahmadi persecution", "blasphemy law",
        "baloch yakjehti committee", "forced conversion", "minorities pakistan",
        "christian persecution pakistan", "pok protest", "gilgit protest",
        "baloch genocide", "baloch crackdown", "pakistan army balochistan",
    ],
}

HIGH_IMPORTANCE_TRIGGERS = [
    "breaking", "urgent", "exclusive", "ceasefire", "war", "strike",
    "nuclear", "crisis", "emergency", "condemns india", "sanctions india",
    "expelled", "killed", "attack", "blast", "invasion", "border clash",
    "escalation", "protest india", "bandh", "arrest", "coup",
    "india tension", "india warns", "india responds",
    "enforced disappearance", "baloch killed", "extrajudicial",
    "crackdown", "missing persons", "abducted", "custodial death",
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

            # Relevance check depends on category
            if category == "pok_baloch_minorities":
                if not is_pok_baloch_relevant(combined):
                    continue
            else:
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

            if category == "pok_baloch_minorities":
                # r/Balochistan and r/GilgitBaltistan are inherently on-topic,
                # so we don't hard-filter, just tag signals
                pass
            else:
                if not is_india_relevant(combined):
                    continue

            signals = detect_signals(combined)
            importance = score_importance(combined)
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

    for category, feed_list in FEEDS.items():
        print(f"\n[{category.upper()}]")
        for feed in feed_list:
            print(f"  {feed['name']} ...", end=" ", flush=True)
            is_reddit_json = "reddit.com" in feed["url"] and (".json" in feed["url"])
            if is_reddit_json:
                items = fetch_reddit_json(feed, category)
            else:
                items = fetch_rss(feed, category)
            print(f"{len(items)} relevant items")
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

    deduped.sort(key=lambda x: (x["importance"], x.get("reddit_score", 0)), reverse=True)

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

    summary = {
        "generated_at": output["generated_at"],
        "total_items": output["total_items"],
        "signal_summary": output["signal_summary"],
        "top_signals": output["top_signals"],
        "top_items": deduped,
    }
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ Done. {len(deduped)} relevant items saved.")
    print(f"  Signal breakdown: {dict(signal_counts)}")
    print(f"  Category stats: {dict(stats)}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    crawl_all()
