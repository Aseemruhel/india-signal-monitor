#!/usr/bin/env python3
"""
India Pulse 360 — Geopolitical Intelligence Crawler
Version 3.0 — Clean rebuild with multi-label classification,
expanded alias matching, rolling date window, and Telegram HTML scraping.
"""

import json, feedparser, requests, re, hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import time
from email.utils import parsedate_to_datetime

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠ pip install beautifulsoup4 — Telegram scraping disabled")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

MAX_AGE_DAYS   = 4      # Rolling window — change to 2 for tighter freshness
MAX_ITEMS_FEED = 15     # Items fetched per RSS feed
MAX_ITEMS_TG   = 20     # Items scraped per Telegram channel
CRAWL_DELAY    = 0.4    # Seconds between feed fetches (polite)

CUTOFF = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)

# ══════════════════════════════════════════════════════════════════════════════
# FEED DEFINITIONS  (199 sources across 21 categories)
# ══════════════════════════════════════════════════════════════════════════════

FEEDS = {

    # ── BREAKING NEWS ─────────────────────────────────────────────────────────
    "breaking_news": [
        {"name": "Reuters Breaking",       "url": "https://feeds.reuters.com/reuters/worldNews"},
        {"name": "Reuters Top News",       "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "AP News India",          "url": "https://news.google.com/rss/search?q=india+site:apnews.com&hl=en&gl=US&ceid=US:en&tbs=qdr:d"},
        {"name": "AFP India",              "url": "https://news.google.com/rss/search?q=india+site:afp.com&hl=en&gl=US&ceid=US:en&tbs=qdr:d"},
        {"name": "BBC Breaking",           "url": "http://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "BBC South Asia",         "url": "http://feeds.bbci.co.uk/news/world/south_asia/rss.xml"},
        {"name": "Al Jazeera Breaking",    "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "NDTV Breaking",          "url": "https://feeds.feedburner.com/ndtvnews-top-stories"},
        {"name": "India Today Breaking",   "url": "https://www.indiatoday.in/rss/1206578"},
        {"name": "ANI News",               "url": "https://aninews.in/rss/"},
        {"name": "PTI India Today",        "url": "https://news.google.com/rss/search?q=PTI+news+india&hl=en&gl=IN&ceid=IN:en&tbs=qdr:d"},
        {"name": "GNews India Today",      "url": "https://news.google.com/rss/search?q=india&hl=en&gl=IN&ceid=IN:en&tbs=qdr:d"},
    ],

    # ── INDIA MEDIA ───────────────────────────────────────────────────────────
    "india_geopolitics": [
        {"name": "The Hindu National",     "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
        {"name": "The Hindu International","url": "https://www.thehindu.com/news/international/feeder/default.rss"},
        {"name": "Indian Express India",   "url": "https://indianexpress.com/section/india/feed/"},
        {"name": "Indian Express World",   "url": "https://indianexpress.com/section/world/feed/"},
        {"name": "LiveMint Politics",      "url": "https://www.livemint.com/rss/politics"},
        {"name": "Hindustan Times",        "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"},
        {"name": "NDTV India",             "url": "https://feeds.feedburner.com/ndtvnews-india-news"},
        {"name": "Deccan Herald",          "url": "https://www.deccanherald.com/rss-feeds/feed-national"},
        {"name": "The Wire",               "url": "https://thewire.in/feed"},
        {"name": "Scroll.in",              "url": "https://scroll.in/feed"},
        {"name": "FirstPost India",        "url": "https://www.firstpost.com/rss/india.xml"},
        {"name": "Tribune India",          "url": "https://www.tribuneindia.com/rss/feed?category=nation"},
        {"name": "Economic Times India",   "url": "https://economictimes.indiatimes.com/news/india/rssfeeds/1014008090.cms"},
    ],

    # ── PAKISTAN MEDIA ────────────────────────────────────────────────────────
    "pakistan_narratives": [
        {"name": "Dawn",                   "url": "https://www.dawn.com/feeds/home"},
        {"name": "The News International", "url": "https://www.thenews.com.pk/rss/1/1"},
        {"name": "Geo News",               "url": "https://www.geo.tv/rss/1"},
        {"name": "Express Tribune",        "url": "https://tribune.com.pk/feed/"},
        {"name": "ARY News",               "url": "https://arynews.tv/feed/"},
        {"name": "The Nation Pakistan",    "url": "https://nation.com.pk/rss/"},
        {"name": "Business Recorder",      "url": "https://www.brecorder.com/feed"},
        {"name": "Pakistan Today",         "url": "https://www.pakistantoday.com.pk/feed/"},
        {"name": "Daily Times Pakistan",   "url": "https://dailytimes.com.pk/feed/"},
        {"name": "Samaa English",          "url": "https://www.samaa.tv/feed/"},
        {"name": "GNews DGISPR",           "url": "https://news.google.com/rss/search?q=DGISPR+OR+%22Inter+Services+Public+Relations%22+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak Army",         "url": "https://news.google.com/rss/search?q=pakistan+army+statement+india&hl=en&gl=US&ceid=US:en"},
        # ── Baloch / PoK / Minorities (merged into Pakistan section) ─────────
        {"name": "HRCP RSS",               "url": "https://hrcp-web.org/hrcpweb/feed/"},
        {"name": "GNews VOPK",             "url": "https://news.google.com/rss/search?q=%22voice+of+karakoram%22+OR+VOPK&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Gilgit Baltistan", "url": "https://news.google.com/rss/search?q=gilgit+baltistan+rights+OR+gilgit+protest&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews PoK Minorities",   "url": "https://news.google.com/rss/search?q=%22pakistan+occupied+kashmir%22+minorities+OR+rights&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Paank Baloch",     "url": "https://news.google.com/rss/search?q=Paank+Baloch+OR+%22Baloch+human+rights%22&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch Disappear", "url": "https://news.google.com/rss/search?q=balochistan+%22enforced+disappearance%22+OR+balochistan+missing+persons&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch Crackdown", "url": "https://news.google.com/rss/search?q=baloch+protest+OR+balochistan+crackdown+OR+BYC+balochistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Sindhi Rights",    "url": "https://news.google.com/rss/search?q=sindhi+rights+OR+sindh+nationalist+OR+JSMM&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews PTM Pakistan",     "url": "https://news.google.com/rss/search?q=%22Pashtun+Tahafuz+Movement%22+OR+PTM+Pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak Minorities",   "url": "https://news.google.com/rss/search?q=pakistan+minorities+persecution+OR+pakistan+hindu+forced+conversion&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Ahmadi Pakistan",  "url": "https://news.google.com/rss/search?q=ahmadi+persecution+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch BBC/Reu",   "url": "https://news.google.com/rss/search?q=balochistan+site:bbc.com+OR+balochistan+site:reuters.com&hl=en&gl=US&ceid=US:en"},
        {"name": "SATP Pakistan",          "url": "https://www.satp.org/rss/pakistan.xml"},
        {"name": "r/Balochistan",          "url": "https://www.reddit.com/r/Balochistan/hot.json?limit=15"},
        {"name": "r/GilgitBaltistan",      "url": "https://www.reddit.com/r/GilgitBaltistan/hot.json?limit=10"},
    ],

    # ── WESTERN / INTERNATIONAL MEDIA ────────────────────────────────────────
    "western_media": [
        {"name": "BBC South Asia",         "url": "http://feeds.bbci.co.uk/news/world/south_asia/rss.xml"},
        {"name": "BBC World",              "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "Reuters World",          "url": "https://feeds.reuters.com/reuters/worldNews"},
        {"name": "Reuters India",          "url": "https://news.google.com/rss/search?q=india+site:reuters.com&hl=en&gl=US&ceid=US:en"},
        {"name": "AP News India",          "url": "https://news.google.com/rss/search?q=india+site:apnews.com&hl=en&gl=US&ceid=US:en"},
        {"name": "AFP India",              "url": "https://news.google.com/rss/search?q=india+site:afp.com&hl=en&gl=US&ceid=US:en"},
        {"name": "CNN World",              "url": "http://rss.cnn.com/rss/edition_world.rss"},
        {"name": "The Guardian India",     "url": "https://www.theguardian.com/world/india/rss"},
        {"name": "Al Jazeera Asia",        "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "TRT World",              "url": "https://www.trtworld.com/rss"},
        {"name": "The Diplomat",           "url": "https://thediplomat.com/feed/"},
        {"name": "Bloomberg India",        "url": "https://news.google.com/rss/search?q=india+site:bloomberg.com&hl=en&gl=US&ceid=US:en"},
        {"name": "The Economist India",    "url": "https://news.google.com/rss/search?q=india+site:economist.com&hl=en&gl=US&ceid=US:en"},
        {"name": "Nikkei Asia India",      "url": "https://news.google.com/rss/search?q=india+site:asia.nikkei.com&hl=en&gl=US&ceid=US:en"},
        {"name": "Gulf News World",        "url": "https://gulfnews.com/rss?section=world"},
        {"name": "Asia Times",             "url": "https://asiatimes.com/feed/"},
        {"name": "Foreign Policy",         "url": "https://foreignpolicy.com/feed/"},
        {"name": "NYT India",              "url": "https://news.google.com/rss/search?q=india+site:nytimes.com&hl=en&gl=US&ceid=US:en"},
        {"name": "WaPo India",             "url": "https://news.google.com/rss/search?q=india+site:washingtonpost.com&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews India Pakistan",   "url": "https://news.google.com/rss/search?q=india+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews India China",      "url": "https://news.google.com/rss/search?q=india+china+border&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews India Global",     "url": "https://news.google.com/rss/search?q=india+news+today&hl=en&gl=US&ceid=US:en&tbs=qdr:d"},
        {"name": "GNews India Criticism",  "url": "https://news.google.com/rss/search?q=india+human+rights+OR+india+press+freedom+OR+india+democracy&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews India Protest",    "url": "https://news.google.com/rss/search?q=india+protest+OR+india+bandh+OR+india+agitation&hl=en&gl=IN&ceid=IN:en"},
        {"name": "The Economist Asia",      "url": "https://www.economist.com/asia/rss.xml"},
        {"name": "The Economist World",     "url": "https://www.economist.com/international/rss.xml"},
        {"name": "Financial Times World",   "url": "https://www.ft.com/world?format=rss"},
        {"name": "Time World",              "url": "https://time.com/section/world/feed/"},
        {"name": "Foreign Affairs",         "url": "https://www.foreignaffairs.com/rss.xml"},
    ],

    # ── NEIGHBOURS ────────────────────────────────────────────────────────────
    "neighbours": [
        {"name": "Daily Star Bangladesh",  "url": "https://www.thedailystar.net/frontpage/rss.xml"},
        {"name": "Kathmandu Post",         "url": "https://kathmandupost.com/rss"},
        {"name": "Daily Mirror Sri Lanka", "url": "https://www.dailymirror.lk/rss"},
        {"name": "MyRepublica Nepal",      "url": "https://myrepublica.nagariknetwork.com/feed"},
        {"name": "Mizzima Myanmar",        "url": "https://mizzima.com/feed"},
        {"name": "Tolo News Afghanistan",  "url": "https://tolonews.com/rss.xml"},
        {"name": "GNews Afghanistan India","url": "https://news.google.com/rss/search?q=afghanistan+india+OR+taliban+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Nepal India",      "url": "https://news.google.com/rss/search?q=nepal+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Bangladesh India", "url": "https://news.google.com/rss/search?q=bangladesh+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Maldives India",   "url": "https://news.google.com/rss/search?q=maldives+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Sri Lanka India",  "url": "https://news.google.com/rss/search?q=sri+lanka+india&hl=en&gl=US&ceid=US:en"},
    ],

    # ── SOCIAL / REDDIT ───────────────────────────────────────────────────────
    "social_india": [
        {"name": "r/india",                "url": "https://www.reddit.com/r/india/hot.json?limit=25"},
        {"name": "r/IndiaSpeaks",          "url": "https://www.reddit.com/r/IndiaSpeaks/hot.json?limit=20"},
        {"name": "r/indiadiscussion",      "url": "https://www.reddit.com/r/indiadiscussion/hot.json?limit=15"},
        {"name": "r/geopolitics India",    "url": "https://www.reddit.com/r/geopolitics/search.json?q=india&sort=hot&restrict_sr=1&limit=15"},
        {"name": "r/worldnews India",      "url": "https://www.reddit.com/r/worldnews/search.json?q=india&sort=hot&restrict_sr=1&t=day&limit=20"},
        {"name": "r/kashmirconflict",      "url": "https://www.reddit.com/r/kashmirconflict/hot.json?limit=15"},
        {"name": "HN India geopolitics",   "url": "https://hnrss.org/newest?q=india+geopolitics+OR+india+pakistan+OR+india+china"},
    ],

    # ── POK / BALOCH / MINORITIES ─────────────────────────────────────────────
    "pok_baloch_minorities": [
        {"name": "GNews VOPK",             "url": "https://news.google.com/rss/search?q=%22voice+of+karakoram%22+OR+VOPK&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Gilgit Baltistan", "url": "https://news.google.com/rss/search?q=gilgit+baltistan+rights+OR+gilgit+protest&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews PoK Minorities",   "url": "https://news.google.com/rss/search?q=%22pakistan+occupied+kashmir%22+minorities+OR+rights&hl=en&gl=US&ceid=US:en"},
        {"name": "HRCP RSS",               "url": "https://hrcp-web.org/hrcpweb/feed/"},
        {"name": "GNews HRCP",             "url": "https://news.google.com/rss/search?q=%22Human+Rights+Commission+of+Pakistan%22+OR+HRCP&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Paank Baloch",     "url": "https://news.google.com/rss/search?q=Paank+Baloch+OR+%22Baloch+human+rights%22&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch Disappear", "url": "https://news.google.com/rss/search?q=balochistan+%22enforced+disappearance%22+OR+balochistan+missing+persons&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch Crackdown", "url": "https://news.google.com/rss/search?q=baloch+protest+OR+balochistan+crackdown+OR+BYC+balochistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Baloch BBC/Reu",   "url": "https://news.google.com/rss/search?q=balochistan+site:bbc.com+OR+balochistan+site:reuters.com&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Sindhi Rights",    "url": "https://news.google.com/rss/search?q=sindhi+rights+OR+sindh+nationalist+OR+JSMM&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews PTM Pakistan",     "url": "https://news.google.com/rss/search?q=%22Pashtun+Tahafuz+Movement%22+OR+PTM+Pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak Minorities",   "url": "https://news.google.com/rss/search?q=pakistan+minorities+persecution+OR+pakistan+hindu+forced+conversion+OR+pakistan+christian+persecution&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Ahmadi Pakistan",  "url": "https://news.google.com/rss/search?q=ahmadi+persecution+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "r/Balochistan",          "url": "https://www.reddit.com/r/Balochistan/hot.json?limit=15"},
        {"name": "r/GilgitBaltistan",      "url": "https://www.reddit.com/r/GilgitBaltistan/hot.json?limit=10"},
        {"name": "SATP Pakistan",           "url": "https://www.satp.org/rss/pakistan.xml"},
    ],

    # ── KASHMIR FOCUS ─────────────────────────────────────────────────────────
    "kashmir_focus": [
        {"name": "GNews Pak on Kashmir",   "url": "https://news.google.com/rss/search?q=pakistan+%22indian+kashmir%22+OR+pakistan+%22Jammu+and+Kashmir%22&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak FO Kashmir",   "url": "https://news.google.com/rss/search?q=pakistan+foreign+office+kashmir+OR+pakistan+condemns+kashmir&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak UN Kashmir",   "url": "https://news.google.com/rss/search?q=pakistan+kashmir+united+nations+OR+pakistan+kashmir+OIC&hl=en&gl=US&ceid=US:en"},
        {"name": "Dawn Kashmir",           "url": "https://www.dawn.com/feed/kashmir"},
        {"name": "GNews J&K Developments", "url": "https://news.google.com/rss/search?q=%22Jammu+and+Kashmir%22+OR+J%26K+government+OR+kashmir+assembly&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Kashmir Security", "url": "https://news.google.com/rss/search?q=kashmir+security+OR+kashmir+encounter+OR+kashmir+militant&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Kashmir Elections","url": "https://news.google.com/rss/search?q=kashmir+elections+OR+kashmir+assembly+OR+jammu+kashmir+politics&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Article 370",      "url": "https://news.google.com/rss/search?q=article+370+OR+kashmir+statehood+OR+kashmir+autonomy&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Kashmir HR",       "url": "https://news.google.com/rss/search?q=kashmir+human+rights+violation+OR+kashmir+crackdown&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Kashmir Press",    "url": "https://news.google.com/rss/search?q=kashmir+press+freedom+OR+kashmir+journalist&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Kashmir Shutdown", "url": "https://news.google.com/rss/search?q=kashmir+internet+shutdown+OR+kashmir+communication+blackout&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews BBC Kashmir",      "url": "https://news.google.com/rss/search?q=kashmir+site:bbc.com&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews AJ Kashmir",       "url": "https://news.google.com/rss/search?q=kashmir+site:aljazeera.com&hl=en&gl=US&ceid=US:en"},
    ],

    # ── SIKH / PUNJAB AFFAIRS ─────────────────────────────────────────────────
    # Tier 1 — high reliability direct RSS
    "sikh_punjab_affairs": [
        # ── TIER 1: Direct Punjab news RSS ───────────────────────────────────
        {"name": "Tribune India",              "url": "https://www.tribuneindia.com/rss/feed?category=nation"},
        {"name": "Tribune India Punjab",       "url": "https://www.tribuneindia.com/rss/feed?category=punjab"},
        {"name": "Punjabi Tribune",            "url": "https://punjabitribuneonline.com/feed/"},
        {"name": "Punjab Newsline",            "url": "https://www.punjabnewsline.com/rssfeed/"},
        {"name": "Punjab News Express",        "url": "https://punjabnewsexpress.com/rss-feeds"},
        {"name": "5 Dariya News",              "url": "https://www.5dariyanews.com/rss/punjab.xml"},
        {"name": "Rozana Spokesman",           "url": "https://www.rozanaspokesman.com/feed/"},
        {"name": "Media Punjab",               "url": "https://mediapunjab.com/feed/"},
        # ── TIER 2: National outlets — Punjab sections ────────────────────────
        {"name": "Indian Express Chandigarh",  "url": "https://indianexpress.com/section/cities/chandigarh/feed/"},
        {"name": "HT Chandigarh",              "url": "https://www.hindustantimes.com/feeds/rss/chandigarh-news/rssfeed.xml"},
        {"name": "TOI Chandigarh",             "url": "https://timesofindia.indiatimes.com/rssfeeds/7503122.cms"},
        {"name": "Sikh24",                     "url": "https://sikh24.com/feed/"},
        {"name": "The Sikh Times",             "url": "https://www.thesikhtimes.in/feed/"},
        # ── TIER 3: TV digital / regional ────────────────────────────────────
        {"name": "ABP Sanjha Punjab",          "url": "https://punjabi.abplive.com/feed"},
        {"name": "Zee Punjab News",            "url": "https://zeenews.india.com/rss/punjab-news.xml"},
        {"name": "News18 Punjab",              "url": "https://punjab.news18.com/commonfeeds/v1/eng/rss/news.xml"},
        {"name": "GNews PTC News Punjab",      "url": "https://news.google.com/rss/search?q=PTC+news+punjab+OR+ptcnews+punjab&hl=en&gl=IN&ceid=IN:en"},
        # ── Punjab government official sources ───────────────────────────────
        {"name": "GNews Punjab Govt DIPR",     "url": "https://news.google.com/rss/search?q=punjab+government+DIPR+OR+punjab+CMO+OR+punjab+cabinet&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Punjab Police",        "url": "https://news.google.com/rss/search?q=punjab+police+arrest+OR+punjab+police+operation&hl=en&gl=IN&ceid=IN:en"},
        # ── Security / Khalistan / Extremism ─────────────────────────────────
        {"name": "GNews Khalistan",            "url": "https://news.google.com/rss/search?q=khalistan+movement+OR+khalistani+OR+khalistan+referendum&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews SFJ",                  "url": "https://news.google.com/rss/search?q=%22Sikhs+for+Justice%22+OR+SFJ+khalistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Amritpal Singh",       "url": "https://news.google.com/rss/search?q=Amritpal+Singh+OR+%22Waris+Punjab+De%22&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Punjab Drugs Border",  "url": "https://news.google.com/rss/search?q=punjab+drugs+OR+punjab+border+smuggling+OR+punjab+narcotics&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Anti-Sikh",            "url": "https://news.google.com/rss/search?q=anti-sikh+OR+sikh+hate+crime+OR+gurdwara+vandalism&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Pak Khalistan ISI",    "url": "https://news.google.com/rss/search?q=pakistan+khalistan+OR+ISI+khalistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Khalistan Canada",     "url": "https://news.google.com/rss/search?q=khalistan+canada+OR+Nijjar+canada+india&hl=en&gl=CA&ceid=CA:en"},
        {"name": "GNews Pannun USA",           "url": "https://news.google.com/rss/search?q=Pannun+OR+khalistan+usa+india&hl=en&gl=US&ceid=US:en"},
        {"name": "r/Sikh",                     "url": "https://www.reddit.com/r/Sikh/hot.json?limit=15"},
        {"name": "r/punjab",                   "url": "https://www.reddit.com/r/punjab/hot.json?limit=15"},
    ],

    # ── TELEGRAM CHANNELS (direct t.me/s/ scraping) ───────────────────────────
    "telegram_channels": [
        # category_hint "none" = 100% India-focused, skip relevance filter
        # category_hint "india" = apply India keyword filter
        {"name": "Megh Updates",           "url": "https://t.me/s/MeghUpdates",          "category_hint": "none"},
        {"name": "OSINT Updates India",    "url": "https://t.me/s/OsintUpdates",         "category_hint": "india"},
        {"name": "OsintTV India",          "url": "https://t.me/s/OsntTV",               "category_hint": "india"},
        {"name": "Indian Defence Updates", "url": "https://t.me/s/indiandefenceupdates", "category_hint": "none"},
        {"name": "Conflict Watch HQ",      "url": "https://t.me/s/conflictwatchHQ",      "category_hint": "india"},
        {"name": "IntelSage",              "url": "https://t.me/s/IntelSage",            "category_hint": "india"},
        {"name": "Gore Unit Kashmir",      "url": "https://t.me/s/goreunit",             "category_hint": "india"},
        {"name": "Pakistan Pulse Intel",   "url": "https://t.me/s/PakPulseIntel",        "category_hint": "india"},
        {"name": "The Pulse Point Pak",    "url": "https://t.me/s/ThePulsePoint",        "category_hint": "india"},
        {"name": "Intel Slava Z",          "url": "https://t.me/s/intelslava",           "category_hint": "india"},
        {"name": "OSINT Defender",         "url": "https://t.me/s/OSINT_defender",       "category_hint": "india"},
        {"name": "Insider Paper",          "url": "https://t.me/s/InsiderPaper",         "category_hint": "india"},
        {"name": "BRICS News",             "url": "https://t.me/s/bricsnews",            "category_hint": "india"},
    ],

    # ── CHINA / BORDER / MARITIME ─────────────────────────────────────────────
    "border_territorial": [
        {"name": "GNews LAC PLA",          "url": "https://news.google.com/rss/search?q=LAC+china+infrastructure+OR+PLA+arunachal+OR+china+construction+border&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Doklam Bhutan",    "url": "https://news.google.com/rss/search?q=doklam+OR+bhutan+china+tri-junction+OR+bhutan+border+dispute&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Teesta Water",     "url": "https://news.google.com/rss/search?q=teesta+river+OR+india+bangladesh+water+sharing+OR+india+nepal+water+dispute&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Arunachal China",  "url": "https://news.google.com/rss/search?q=arunachal+china+renaming+OR+china+arunachal+claim+OR+zangnan&hl=en&gl=US&ceid=US:en"},
        {"name": "Global Times India",     "url": "https://news.google.com/rss/search?q=india+site:globaltimes.cn&hl=en&gl=US&ceid=US:en"},
        {"name": "Xinhua India",           "url": "https://news.google.com/rss/search?q=india+site:xinhuanet.com&hl=en&gl=US&ceid=US:en"},
        {"name": "SCMP India China",       "url": "https://news.google.com/rss/search?q=india+china+site:scmp.com&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Chinese Navy IO",  "url": "https://news.google.com/rss/search?q=chinese+navy+indian+ocean+OR+PLA+navy+indian+ocean&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Hambantota",       "url": "https://news.google.com/rss/search?q=hambantota+port+OR+gwadar+port+china+OR+string+of+pearls&hl=en&gl=US&ceid=US:en"},
        {"name": "The Diplomat",           "url": "https://thediplomat.com/feed/"},
        {"name": "War on the Rocks",        "url": "https://warontherocks.com/feed/"},
        {"name": "Breaking Defense",        "url": "https://breakingdefense.com/feed/"},
        {"name": "Defense News",            "url": "https://www.defensenews.com/arc/outboundfeeds/rss/"},
        {"name": "Naval News",              "url": "https://www.navalnews.com/feed/"},
        {"name": "The War Zone",            "url": "https://www.twz.com/feed"},
        {"name": "India Strategic",         "url": "https://indiastrategic.in/feed/"},
        {"name": "SCMP Asia",               "url": "https://www.scmp.com/rss/5/feed"},
    ],

    # ── ECONOMIC SECURITY ─────────────────────────────────────────────────────
    "economic_security": [
        {"name": "GNews China FDI India",  "url": "https://news.google.com/rss/search?q=china+fdi+india+OR+india+china+investment+block&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews India 5G Huawei",  "url": "https://news.google.com/rss/search?q=india+huawei+5g+OR+india+telecom+ban+china&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews India Semicond",   "url": "https://news.google.com/rss/search?q=india+semiconductor+OR+india+rare+earth+china&hl=en&gl=US&ceid=US:en"},
        {"name": "Bloomberg India Econ",   "url": "https://news.google.com/rss/search?q=india+economy+site:bloomberg.com&hl=en&gl=US&ceid=US:en"},
        {"name": "Nikkei India Economy",   "url": "https://news.google.com/rss/search?q=india+economy+site:asia.nikkei.com&hl=en&gl=US&ceid=US:en"},
        {"name": "ET Economy",             "url": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms"},
        {"name": "GNews India Sanctions",  "url": "https://news.google.com/rss/search?q=india+sanctions+OR+india+trade+war+OR+india+tariffs&hl=en&gl=US&ceid=US:en"},
        {"name": "Business Standard Eco",   "url": "https://www.business-standard.com/rss/economy-policy-10106.rss"},
        {"name": "LiveMint Economy",        "url": "https://www.livemint.com/rss/economy"},
        {"name": "Financial Express India", "url": "https://www.financialexpress.com/feed/"},
    ],

    # ── DISINFORMATION RESEARCH ───────────────────────────────────────────────
    "disinfo_research": [
        {"name": "GNews DFRLab India",     "url": "https://news.google.com/rss/search?q=%22Atlantic+Council%22+DFRLab+india+OR+DFRLab+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews EU DisinfoLab",    "url": "https://news.google.com/rss/search?q=%22EU+DisinfoLab%22+india+OR+%22EU+DisinfoLab%22+pakistan&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Meta Takedown",    "url": "https://news.google.com/rss/search?q=meta+coordinated+inauthentic+india+OR+twitter+takedown+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Fake News India",  "url": "https://news.google.com/rss/search?q=fake+news+network+india+pakistan+OR+disinformation+campaign+india&hl=en&gl=US&ceid=US:en"},
        {"name": "DFRLab Atlantic Council", "url": "https://dfrlab.org/feed/"},
    ],

    # ── COMMUNAL FLASHPOINTS ──────────────────────────────────────────────────
    "communal_flashpoints": [
        {"name": "GNews Worship Act",      "url": "https://news.google.com/rss/search?q=%22places+of+worship+act%22+OR+gyanvapi+OR+temple+mosque+dispute+india&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Communal India",   "url": "https://news.google.com/rss/search?q=communal+tension+india+OR+communal+violence+india+OR+religious+clash+india&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews ASI Mosque",       "url": "https://news.google.com/rss/search?q=mosque+temple+litigation+india+OR+ASI+survey+mosque&hl=en&gl=IN&ceid=IN:en"},
        {"name": "The Wire Communal",       "url": "https://thewire.in/category/communalism/feed"},
        {"name": "Two Circles",             "url": "https://twocircles.net/feed/"},
        {"name": "The Wire Minority",       "url": "https://thewire.in/category/minority/feed"},
    ],

    # ── NORTHEAST INDIA ───────────────────────────────────────────────────────
    "northeast_india": [
        {"name": "GNews Manipur",          "url": "https://news.google.com/rss/search?q=manipur+ethnic+conflict+OR+manipur+violence+OR+meitei+kuki&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Myanmar NE India", "url": "https://news.google.com/rss/search?q=myanmar+india+border+refugee+OR+myanmar+northeast+india+arms&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews NE Insurgency",    "url": "https://news.google.com/rss/search?q=northeast+india+insurgency+OR+assam+nagaland+militant&hl=en&gl=IN&ceid=IN:en"},
        {"name": "EastMojo",               "url": "https://www.eastmojo.com/feed/"},
        {"name": "India Today NE",         "url": "https://www.indiatodayne.in/rss.xml"},
        {"name": "Northeast Now",           "url": "https://nenow.in/feed"},
        {"name": "Morung Express Nagaland", "url": "https://morungexpress.com/feed"},
        {"name": "Pratidin Time Assam",     "url": "https://www.pratidintime.com/feed"},
        {"name": "Kanglaonline Manipur",    "url": "https://kanglaonline.com/feed/"},
        {"name": "The Sentinel Assam",      "url": "https://www.sentinelassam.com/feed/"},
    ],

    # ── EXTREMISM / BANNED ORGS ───────────────────────────────────────────────
    "extremism_banned_orgs": [
        {"name": "GNews PFI India",        "url": "https://news.google.com/rss/search?q=%22Popular+Front+of+India%22+OR+PFI+banned+OR+PFI+successor&hl=en&gl=IN&ceid=IN:en"},
        {"name": "NIA Press Releases",     "url": "https://nia.gov.in/rss-feed.htm"},
        {"name": "GNews NIA India",        "url": "https://news.google.com/rss/search?q=NIA+terror+case+OR+NIA+chargesheet+OR+NIA+raid&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews ISIS India",       "url": "https://news.google.com/rss/search?q=ISIS+recruitment+india+OR+jihadist+india+arrest&hl=en&gl=IN&ceid=IN:en"},
        {"name": "SATP India",              "url": "https://www.satp.org/rss/india.xml"},
        {"name": "Counter Extremism Proj",  "url": "https://www.counterextremism.com/feed"},
    ],

    # ── NAXAL / MAOIST ────────────────────────────────────────────────────────
    "naxal_insurgency": [
        {"name": "GNews Naxal Attack",     "url": "https://news.google.com/rss/search?q=naxal+attack+OR+maoist+attack+india+OR+naxalite+encounter&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Naxal Operation",  "url": "https://news.google.com/rss/search?q=naxal+surrender+OR+anti-naxal+operation+OR+CRPF+naxal&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews Bastar Maoist",    "url": "https://news.google.com/rss/search?q=bastar+maoist+OR+chhattisgarh+naxal+OR+red+corridor+india&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews CPI Maoist",       "url": "https://news.google.com/rss/search?q=%22CPI+Maoist%22+OR+naxal+banned&hl=en&gl=IN&ceid=IN:en"},
        {"name": "SATP India Maoist",       "url": "https://www.satp.org/rss/india-maoist.xml"},
    ],

    # ── INDIA CRITICS / THINK TANKS ───────────────────────────────────────────
    "india_critics": [
        {"name": "GNews V-Dem India",      "url": "https://news.google.com/rss/search?q=%22V-Dem%22+india+OR+%22Freedom+House%22+india+OR+EIU+india+democracy&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews HRW India",        "url": "https://news.google.com/rss/search?q=%22Human+Rights+Watch%22+india+OR+HRW+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Amnesty India",    "url": "https://news.google.com/rss/search?q=%22Amnesty+International%22+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews RSF India",        "url": "https://news.google.com/rss/search?q=%22Reporters+Without+Borders%22+india+OR+RSF+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews UN Rapporteur",    "url": "https://news.google.com/rss/search?q=%22UN+Special+Rapporteur%22+india&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Brookings India",  "url": "https://news.google.com/rss/search?q=india+site:brookings.edu&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews CSIS India",       "url": "https://news.google.com/rss/search?q=india+site:csis.org&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews Carnegie India",   "url": "https://news.google.com/rss/search?q=india+site:carnegieendowment.org&hl=en&gl=US&ceid=US:en"},
        {"name": "HRW Asia (direct)",       "url": "https://www.hrw.org/rss/node/20/feed"},
        {"name": "Amnesty Intl Asia",       "url": "https://www.amnesty.org/en/topic/asia-pacific/feed/"},
        {"name": "Foreign Affairs",         "url": "https://www.foreignaffairs.com/rss.xml"},
        {"name": "Foreign Policy S Asia",   "url": "https://foreignpolicy.com/category/south-asia/feed/"},
        {"name": "ORF Analysis",            "url": "https://www.orfonline.org/feed/"},
        {"name": "Carnegie Endowment",      "url": "https://carnegieendowment.org/rss/solr/?fa=pub&maxrows=25"},
        {"name": "Brookings India",         "url": "https://www.brookings.edu/topic/india/feed/"},
        {"name": "Chatham House",           "url": "https://www.chathamhouse.org/rss.xml"},
    ],

    # ── OSINT CHANNELS ────────────────────────────────────────────────────────
    "osint_channels": [
        {"name": "GNews Bellingcat India", "url": "https://news.google.com/rss/search?q=bellingcat+india+OR+bellingcat+pakistan+OR+bellingcat+kashmir&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews ORF India",        "url": "https://news.google.com/rss/search?q=%22Observer+Research+Foundation%22+OR+ORF+india&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews IDSA India",       "url": "https://news.google.com/rss/search?q=%22Manohar+Parrikar+Institute%22+OR+IDSA+india&hl=en&gl=IN&ceid=IN:en"},
        {"name": "GNews StratNews",        "url": "https://news.google.com/rss/search?q=stratnewsglobal+OR+%22Strat+News+Global%22&hl=en&gl=IN&ceid=IN:en"},
        {"name": "r/CredibleDefense",      "url": "https://www.reddit.com/r/CredibleDefense/search.json?q=india+OR+pakistan&sort=hot&restrict_sr=1&limit=15"},
        {"name": "GNews Cyber India",      "url": "https://news.google.com/rss/search?q=india+cyberattack+OR+APT+group+india+OR+CERT-In&hl=en&gl=US&ceid=US:en"},
        {"name": "GNews CERT-In",          "url": "https://www.cert-in.org.in/RSS/CIADRSS.xml"},
        {"name": "War on the Rocks",        "url": "https://warontherocks.com/feed/"},
        {"name": "Stimson Center",          "url": "https://www.stimson.org/feed/"},
        {"name": "IDSA New Releases",       "url": "https://idsa.in/feed/"},
        {"name": "Quwa Defence Pakistan",   "url": "https://quwa.org/feed/"},
        {"name": "India Strategic",         "url": "https://indiastrategic.in/feed/"},
        {"name": "Lawfare Blog",            "url": "https://www.lawfaremedia.org/feed"},
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# RELEVANCE: India keyword matching — expanded aliases for wire-agency phrasing
# ══════════════════════════════════════════════════════════════════════════════

INDIA_MUST_MATCH = [
    # Core
    "india", "indian", "bharat", "bharatiya",
    # Leadership & officials
    "modi", "narendra modi", "prime minister narendra", "amit shah",
    "jaishankar", "rajnath", "doval", "yogi adityanath", "shringla",
    # Institutions
    "lok sabha", "rajya sabha", "bjp", "congress party",
    "indian army", "indian navy", "indian air force", "iaf",
    "government of india", "indian government", "india's government",
    "mea india", "ministry of external affairs",
    # Geography
    "new delhi", "delhi", "mumbai", "arunachal", "ladakh",
    "manipur", "assam", "jammu",
    # Conflicts / strategic
    "doklam", "galwan", "loc ", "line of control",
    "brahmos", "drdo", "isro", "rupee", "rbi india",
    # Relations
    "india pakistan", "pakistan india", "india china", "india us",
    "india russia", "india-us", "india-china", "india-pakistan",
    "quad india", "brics india", "sco india", "india-", "india's",
    "south asia", "south asian",
    # Entities often used by wires instead of "India"
    "new delhi",  "hindustan", "subcontinental",
    "khalistan", "naxal", "maoist india",
    "northeast india", "26/11",
]

# PoK / Baloch / Minorities — no India mention required
POK_BALOCH_MUST_MATCH = [
    "balochistan", "baloch", "gilgit", "baltistan", "pok ", "pok,",
    "azad kashmir", "pakistan occupied kashmir", "sindhi", "sindh",
    "pashtun", "ptm", "hrcp", "human rights commission of pakistan",
    "paank", "vopk", "voice of karakoram", "enforced disappearance",
    "missing persons pakistan", "ahmadi", "blasphemy law", "byc ",
    "baloch yakjehti", "minorities pakistan", "forced conversion",
    "christian persecution pakistan", "hindu pakistan minority",
]

# Kashmir — any mention
KASHMIR_MUST_MATCH = [
    "kashmir", "jammu and kashmir", "j&k", "j & k", "article 370",
    "azad kashmir", "pok ", "line of control", "loc ",
    "srinagar", "pulwama", "anantnag", "baramulla", "kupwara",
    "gilgit baltistan", "kashmir valley", "kashmiri",
]

# Sikh / Punjab
SIKH_PUNJAB_MUST_MATCH = [
    "sikh", "sikhs", "khalistan", "khalistani", "punjab", "gurdwara",
    "amritsar", "nijjar", "pannun", "sikhs for justice", "sfj",
    "waris punjab de", "amritpal singh", "golden temple", "akal takht",
    "kartarpur", "shiromani akali dal",
]

def is_india_relevant(text):
    t = text.lower()
    return any(kw in t for kw in INDIA_MUST_MATCH)

def is_pok_baloch_relevant(text):
    t = text.lower()
    return any(kw in t for kw in POK_BALOCH_MUST_MATCH)

def is_kashmir_relevant(text):
    t = text.lower()
    return any(kw in t for kw in KASHMIR_MUST_MATCH)

def is_sikh_punjab_relevant(text):
    t = text.lower()
    return any(kw in t for kw in SIKH_PUNJAB_MUST_MATCH)

# Sources that bypass relevance filter entirely (official Indian govt feeds)
SOURCE_EXEMPT = {"NIA Press Releases", "GNews CERT-In"}

# ══════════════════════════════════════════════════════════════════════════════
# MULTI-LABEL SIGNAL CLASSIFICATION
# Each item gets ALL matching labels — not just the first.
# Expanded with aliases so wire-agency phrasing doesn't get missed.
# ══════════════════════════════════════════════════════════════════════════════

# Maps dashboard topic → list of (keyword_phrases)
# Phrases support multi-word matching for precision
TOPIC_CLASSIFIERS = {
    "pakistan": [
        # ── Must be Pakistan-as-subject (not passing mention) ──
        # Bare 'pakistan' removed — too many India articles mention it in passing
        # These phrases all require Pakistan to be the actor or explicit subject
        "islamabad", "rawalpindi",
        "fo spokesman pakistan", "fo spokesperson pakistan",
        "pakistan foreign office", "pakistan foreign ministry",
        "pakistan ministry of", "pakistan prime minister",
        "pakistan government", "pakistan's government",
        "ghq ", "ispr ", "dgispr ", "inter services public relations",
        "asim munir", "ishaq dar", "bilawal bhutto",
        "imran khan arrested", "imran khan released", "imran khan bail",
        "nawaz sharif", "shahbaz sharif",
        "pak army", "pakistan army", "pakistan air force",
        # ── Pakistan-as-actor phrases ──
        "pakistan condemns", "pakistan rejects", "pakistan warns",
        "pakistan calls on india", "pakistan demands india",
        "pakistan accuses india", "pakistan blames india",
        "pakistan threatens", "pakistan raises kashmir",
        "pakistan at un", "pakistan at oic",
        "islamabad accuses", "islamabad warns", "islamabad condemns",
        "islamabad rejects", "islamabad says india",
        # ── Pakistan economy/politics (explicit) ──
        "imf pakistan", "pakistan economic crisis", "pakistan default",
        "pakistan inflation", "pakistan elections", "pti pakistan",
        "pakistan budget", "pakistan cabinet",
        # ── Pakistan military/nuclear (explicit) ──
        "pakistan nuclear", "pakistan missile test", "pakistan test fire",
        "paf jet", "pakistan navy vessel",
        "pakistan military exercise", "pakistan test launches",
        # ── Pakistan-based terror (explicit) ──
        "jaish-e-mohammed", "jaish e mohammed",
        "lashkar-e-taiba", "lashkar e taiba",
        "hafiz saeed", "masood azhar", "salahuddin umar",
        "hizbul mujahideen", "al-badr pakistan",
        "pakistan based terror", "terror camps pakistan",
        "cross border terror pakistan",
        # ── Water/Indus (only when Pakistan is explicit agent) ──
        "pakistan indus waters", "pakistan blocks water",
        "islamabad water dispute",
    ],

    "baloch_minorities": [
        "balochistan", "baloch", "gilgit baltistan", "gilgit", "baltistan",
        "pok ", "azad kashmir", "pakistan occupied kashmir",
        "sindhi", "sindh nationalist", "jsmm",
        "pashtun tahafuz movement", "ptm ", "manzoor pashteen",
        "hrcp", "human rights commission of pakistan",
        "paank ", "voice of karakoram", "vopk",
        "enforced disappearance", "missing persons pakistan", "baloch disappear",
        "baloch genocide", "baloch crackdown", "pakistan army balochistan",
        "baloch yakjehti", "byc ", "mahrang baloch",
        "ahmadi", "blasphemy law", "blasphemy case",
        "forced conversion pakistan", "christian persecution pakistan",
        "hindu minority pakistan", "minorities pakistan",
        "sindhudesh", "sindhu desh", "jiye sindh",
    ],

    "sikh_punjab": [
        "sikh", "sikhs", "khalistan", "khalistani",
        "punjab india", "punjab news", "punjab police", "punjab crime",
        "amritsar", "gurdwara", "golden temple", "akal takht",
        "nijjar", "hardeep nijjar", "pannun", "gurpatwant",
        "sikhs for justice", "sfj ", "waris punjab de", "amritpal singh",
        "khalistan referendum", "khalistan vote", "sfj referendum",
        "anti-sikh", "sikh hate crime", "gurdwara vandalism",
        "canada india sikh", "khalistan canada", "khalistan uk",
        "isi khalistan", "pakistan khalistan", "pakistan funding khalistan",
        "operation blue star", "1984 sikh",
        "shiromani akali dal", "sad ", "parkash badal",
    ],

    "kashmir": [
        "kashmir", "kashmiri", "jammu and kashmir", "j&k",
        "srinagar", "pulwama", "anantnag", "baramulla", "kupwara",
        "line of control", "loc ", "ceasefire line",
        "article 370", "article 35a", "kashmir statehood", "j&k statehood",
        "kashmir assembly", "kashmir elections", "kashmir lieutenant governor",
        "kashmir encounter", "kashmir militant", "kashmir terrorist",
        "kashmir human rights", "kashmir crackdown", "kashmir press freedom",
        "kashmir internet shutdown", "kashmir blackout",
        "kashmir occupation", "occupied kashmir", "pakistan kashmir",
        "un kashmir", "oic kashmir", "kashmir un resolution",
        "azad kashmir", "mirpur", "muzaffarabad",
        "giligit baltistan",  # intentional alias
        "indus water treaty kashmir",
    ],

    "western_media": [
        # These items come from western_media category — tag everything from it
        # plus explicit criticism phrases
        "india democratic backsliding", "india autocratization",
        "press freedom india", "india authoritarian",
        "india human rights", "minority rights india",
        "religious freedom india", "india crackdown",
        "india internet shutdown", "india surveillance",
        "india ngo crackdown", "fcra india", "india civil society",
        "india ranking", "india corruption index",
        "india modi criticism", "bjp criticism",
        "india repression", "india journalists jailed",
        "rsf india", "cpj india", "committee to protect journalists india",
        "freedom house india", "v-dem india",
    ],

    "northeast": [
        "manipur", "meitei", "kuki", "nagaland", "assam",
        "arunachal", "meghalaya", "tripura", "mizoram", "sikkim",
        "northeast india", "north east india", "northeastern india",
        "bodo ", "nscn", "ulfa", "northeast insurgency",
        "northeast militant", "northeast unrest",
        "myanmar india border", "myanmar refugee india",
        "myanmar junta india", "moreh ",
        "inner line permit", "ilp ", "northeast flood",
        "northeast election",
    ],

    "economy": [
        "india economy", "indian economy", "india gdp",
        "india growth", "india recession", "india inflation",
        "india trade deficit", "india export", "india import",
        "india budget", "india fiscal", "india rbi",
        "india interest rate", "india rupee",
        "india investment", "india fdi", "india manufacturing",
        "make in india", "india semiconductor",
        "india china trade", "india us trade", "india tariff",
        "india sanctions", "india supply chain",
        "india rare earth", "india energy", "india oil",
        "india stock market", "sensex", "nifty",
        "india imf", "india world bank",
        "india economic crisis", "india slowdown",
    ],

    "naxal": [
        "naxal", "naxalite", "maoist india", "cpi maoist",
        "red corridor", "naxal attack", "maoist attack",
        "naxal encounter", "naxal surrender",
        "crpf naxal", "crpf maoist", "bsf naxal",
        "bastar", "chhattisgarh naxal", "jharkhand naxal",
        "odisha naxal", "andhra naxal", "telangana naxal",
        "anti-naxal operation", "naxal killed",
        "plfi", "tpc naxal", "mcc naxal",
    ],

    "communal": [
        "communal violence", "communal tension", "religious clash india",
        "communal riot", "mob lynching", "lynching india",
        "gyanvapi", "places of worship act", "worship act india",
        "temple mosque dispute", "mosque survey india", "asi survey mosque",
        "waqf board", "waqf amendment", "waqf act",
        "ram mandir", "babri", "demolition india",
        "cow vigilante", "cow protection india",
        "inter-religious violence", "minority attack india",
        "christian attack india", "church attack india",
        "love jihad", "conversion india", "anti-conversion",
        "vhp", "bajrang dal", "religious extremism india",
    ],

    "china": [
        "china india", "india china", "chinese",
        "pla ", "people's liberation army",
        "lac ", "line of actual control", "arunachal",
        "doklam", "galwan", "pangong", "depsang",
        "china border india", "india china border",
        "china threat india", "china aggression india",
        "global times india", "xinhua india",
        "china tibetan", "dalai lama china",
        "south china sea india", "quad china",
        "chinese navy", "pla navy", "china submarine",
        "hambantota", "gwadar", "string of pearls",
        "china maldives", "china nepal", "china sri lanka",
        "china bangladesh", "china bhutan",
        "belt and road india", "bri india",
        "huawei india", "china 5g india",
        "china rare earth india", "china supply chain india",
        "china fdi india", "china investment india",
        "dragon india", "india dragon",
    ],

    "neighbours": [
        "nepal india", "india nepal", "kathmandu india",
        "bangladesh india", "india bangladesh", "dhaka india",
        "sheikh hasina", "bangladesh interim",
        "sri lanka india", "india sri lanka", "colombo india",
        "maldives india", "india maldives", "male india",
        "india out maldives", "muizzu india",
        "bhutan india", "india bhutan", "thimphu india",
        "myanmar india", "india myanmar", "naypyidaw india",
        "afghanistan india", "india afghanistan", "kabul india",
        "taliban india",
        "neighbour india", "india neighbour",
        "india interference", "india hegemony",
        "south asia india",
    ],
}

# ── Auto-tag: category → topic label if keyword detection gets nothing ────────
CAT_AUTO_TOPIC = {
    "pok_baloch_minorities": "pakistan",    # merged into Pakistan section
    "kashmir_focus":         "kashmir",
    "sikh_punjab_affairs":   "sikh_punjab",
    "pakistan_narratives":   "pakistan",
    "border_territorial":    "china",
    "maritime_indian_ocean": "china",
    "communal_flashpoints":  "communal",
    "northeast_india":       "northeast",
    "naxal_insurgency":      "naxal",
    "economic_security":     "economy",
    "western_media":         "western_media",
    "neighbours":            "neighbours",
    "telegram_channels":     None,   # let keyword detection handle
}

# ── High-urgency flash triggers ───────────────────────────────────────────────
FLASH_TRIGGERS = [
    "breaking", "urgent", "just in", "flash:", "alert:",
    "border clash", "military standoff", "troops mobilized",
    "ceasefire violation", "airspace violation", "naval standoff",
    "diplomatic expulsion", "recalled ambassador", "crisis talks",
    "curfew imposed", "shoot at sight", "high alert",
    "emergency session", "national emergency",
    "india pakistan war", "india china war",
    "india attack", "india struck", "pakistan struck",
    "nuclear threat", "nuclear alert",
    "blast india", "explosion india",
    "terror attack india", "india terror",
    "naxal attack kills", "maoist ambush",
    "kashmir encounter kills", "killed in kashmir",
    "enforced disappearance", "mass arrest",
    "india china skirmish", "lac standoff",
]

# Sources that are 100% India-domestic — classify on TITLE ONLY to prevent
# RSS summary bleed-through from unrelated related-article snippets
INDIA_DOMESTIC_SOURCES = {
    "The Hindu National", "The Hindu International", "Indian Express India",
    "Indian Express World", "LiveMint Politics", "Hindustan Times",
    "NDTV India", "NDTV Breaking", "Deccan Herald", "The Wire", "Scroll.in",
    "FirstPost India", "Tribune India", "Economic Times India",
    "India Today Breaking", "ANI News", "EastMojo", "India Today NE",
    "Megh Updates", "Indian Defence Updates",
    # GNews targeting Indian domestic content (title-only Pakistan check)
    "GNews J&K Developments", "GNews Kashmir Security",
    "GNews Kashmir Elections", "GNews Article 370",
    "GNews Manipur", "GNews NE Insurgency", "GNews Myanmar NE India",
    "GNews Communal India", "GNews Worship Act", "GNews ASI Mosque",
    "GNews Naxal Attack", "GNews Naxal Operation",
    "GNews Bastar Maoist", "GNews CPI Maoist",
    "GNews Punjab Security", "GNews Amritpal Singh",
    "GNews India Today", "PTI India Today",
    "GNews NIA India", "GNews PFI India",
}

def classify_topics(text, title_only_text=None):
    """
    Multi-label classification — returns ALL matching topics.
    title_only_text: if provided, used for stricter matching on ambiguous topics
    like 'pakistan' to avoid summary bleed-through.
    """
    text_lower = text.lower()
    # For Pakistan specifically, we require the match in title if title_only is given
    # This prevents Kashmir articles whose summaries mention Pakistan in passing
    title_lower = title_only_text.lower() if title_only_text else text_lower

    matched = set()
    for topic, phrases in TOPIC_CLASSIFIERS.items():
        check_text = title_lower if topic == "pakistan" and title_only_text else text_lower
        for phrase in phrases:
            if phrase in check_text:
                matched.add(topic)
                break
    return list(matched)

def is_flashpoint(text):
    text_lower = text.lower()
    return any(t in text_lower for t in FLASH_TRIGGERS)

# ══════════════════════════════════════════════════════════════════════════════
# DATE UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def parse_pub_date(entry):
    """Extract timezone-aware datetime from feedparser entry."""
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None

def is_recent(pub_dt, is_breaking=False):
    if pub_dt is None:
        return None
    return pub_dt >= CUTOFF

def item_hash(title, summary=""):
    """Stable hash for deduplication — combines cleaned title + first 80 chars of summary."""
    raw = re.sub(r'\W+', ' ', (title + " " + summary[:80]).lower()).strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM CHANNEL FETCHER (direct t.me/s/ HTML scraping — no RSSHub needed)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_telegram_channel(feed_info, category):
    items = []
    if not BS4_AVAILABLE:
        print(f"  ✗ bs4 not available — skipping {feed_info['name']}")
        return items
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(feed_info["url"], headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ✗ {feed_info['name']} — HTTP {resp.status_code}")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        wraps = soup.find_all("div", class_="tgme_widget_message_wrap")

        for wrap in wraps[:MAX_ITEMS_TG]:
            text_el = wrap.find("div", class_="tgme_widget_message_text")
            if not text_el:
                continue
            raw_text = text_el.get_text(" ", strip=True)
            if not raw_text or len(raw_text) < 15:
                continue

            title = raw_text[:140].strip()
            if len(raw_text) > 140 and " " in raw_text[:137]:
                title = raw_text[:raw_text.rfind(" ", 0, 137)] + "…"
            summary = raw_text[:400]

            link_el = wrap.find("a", class_="tgme_widget_message_date")
            link = link_el.get("href", "") if link_el else ""

            time_el = wrap.find("time")
            pub_dt = None
            pub = ""
            if time_el:
                dt_str = time_el.get("datetime", "")
                if dt_str:
                    try:
                        pub_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        pub = pub_dt.isoformat()
                    except Exception:
                        pass

            recent = is_recent(pub_dt)
            if recent is False:
                continue
            if recent is None:
                continue  # Telegram items without date skipped

            combined = f"{title} {summary}"
            hint = feed_info.get("category_hint", "india")

            if hint == "none":
                pass
            elif not is_india_relevant(combined):
                continue

            topics = classify_topics(combined)
            auto = CAT_AUTO_TOPIC.get(category)
            if auto and auto not in topics:
                topics.append(auto)

            items.append({
                "title": title,
                "summary": summary[:300],
                "link": link,
                "source": feed_info["name"],
                "category": category,
                "topics": topics,
                "flashpoint": is_flashpoint(combined),
                "published": pub,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"  ✗ {feed_info['name']} — {e}")
    return items

# ══════════════════════════════════════════════════════════════════════════════
# RSS FEED FETCHER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_rss(feed_info, category):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; IndiaPulse360/3.0)"}
        resp = requests.get(feed_info["url"], headers=headers, timeout=12)
        parsed = feedparser.parse(resp.content)

        for entry in parsed.entries[:MAX_ITEMS_FEED]:
            title   = entry.get("title", "").strip()
            summary = re.sub(r'<[^>]+>', '', entry.get("summary",
                             entry.get("description", ""))).strip()[:500]
            link    = entry.get("link", "")
            pub_dt  = parse_pub_date(entry)
            pub     = pub_dt.isoformat() if pub_dt else ""

            # Use BOTH title + summary for classification (fixes title-only bug)
            combined = f"{title} {summary}"

            # ── DATE FILTER ──────────────────────────────────────────────────
            recent = is_recent(pub_dt)
            if recent is False:
                continue
            # Breaking news: allow undated items through (wire feeds sometimes
            # omit timestamps on very fresh stories)
            if recent is None and category != "breaking_news":
                continue

            # ── RELEVANCE FILTER ─────────────────────────────────────────────
            if feed_info["name"] in SOURCE_EXEMPT:
                pass  # official govt feed — always relevant
            else:
                hint = feed_info.get("category_hint", category)
                if hint == "pok_baloch_minorities" or hint == "pok_baloch":
                    if not is_pok_baloch_relevant(combined): continue
                elif hint == "kashmir_focus" or hint == "kashmir":
                    if not is_kashmir_relevant(combined): continue
                elif hint == "sikh_punjab_affairs" or hint == "sikh_punjab":
                    if not is_sikh_punjab_relevant(combined): continue
                elif hint == "none":
                    pass  # 100% India-focused source
                else:
                    # Default: India relevance — but also accept PoK/Baloch/Kashmir
                    # items that don't contain "India" explicitly (fixes missed items)
                    if not (is_india_relevant(combined)
                            or is_pok_baloch_relevant(combined)
                            or is_kashmir_relevant(combined)):
                        continue

            # ── MULTI-LABEL TOPIC CLASSIFICATION ────────────────────────────
            # For domestic India sources, pass title alone for Pakistan check
            # to prevent summary bleed-through false positives
            title_only = title if feed_info["name"] in INDIA_DOMESTIC_SOURCES else None
            topics = classify_topics(combined, title_only)

            # Auto-tag from category if no topic matched
            auto = CAT_AUTO_TOPIC.get(category)
            if auto and auto not in topics:
                topics.append(auto)

            items.append({
                "title":      title,
                "summary":    summary[:300],
                "link":       link,
                "source":     feed_info["name"],
                "category":   category,
                "topics":     topics,
                "flashpoint": is_flashpoint(combined),
                "published":  pub,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

    except Exception as e:
        print(f"  ✗ {feed_info['name']} — {e}")
    return items

# ══════════════════════════════════════════════════════════════════════════════
# REDDIT JSON FETCHER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_reddit_json(feed_info, category):
    items = []
    try:
        headers = {"User-Agent": "IndiaPulse360/3.0"}
        resp = requests.get(feed_info["url"], headers=headers, timeout=12)
        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post["data"]
            title    = p.get("title", "")
            selftext = p.get("selftext", "")[:400]
            link     = f"https://reddit.com{p.get('permalink', '')}"
            score    = p.get("score", 0)
            combined = f"{title} {selftext}"

            pub_ts = p.get("created_utc", 0)
            if pub_ts:
                pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                if pub_dt < CUTOFF:
                    continue
                pub = pub_dt.isoformat()
            else:
                continue

            # Baloch/PoK subreddits are inherently relevant
            if category not in ("pok_baloch_minorities", "sikh_punjab_affairs", "pakistan_narratives"):
                if not is_india_relevant(combined):
                    continue

            topics = classify_topics(combined, title)
            auto = CAT_AUTO_TOPIC.get(category)
            if auto and auto not in topics:
                topics.append(auto)

            items.append({
                "title":       title,
                "summary":     selftext or f"👍 {score} upvotes · 💬 {p.get('num_comments',0)} comments",
                "link":        link,
                "source":      feed_info["name"],
                "category":    category,
                "topics":      topics,
                "flashpoint":  is_flashpoint(combined),
                "reddit_score": score,
                "published":   pub,
                "fetched_at":  datetime.now(timezone.utc).isoformat(),
            })

    except Exception as e:
        print(f"  ✗ {feed_info['name']} — {e}")
    return items

# ══════════════════════════════════════════════════════════════════════════════
# MAIN CRAWLER
# ══════════════════════════════════════════════════════════════════════════════

def crawl_all():
    all_items = []
    stats = defaultdict(int)

    print(f"\n{'='*62}")
    print(f"  India Pulse 360 — Crawl {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*62}")

    for category, feed_list in FEEDS.items():
        print(f"\n[{category.upper()}]")
        for feed in feed_list:
            print(f"  {feed['name']:<35}", end=" ", flush=True)
            is_tg     = feed["url"].startswith("https://t.me/s/")
            is_reddit = "reddit.com" in feed["url"] and ".json" in feed["url"]

            if is_tg:
                items = fetch_telegram_channel(feed, category)
            elif is_reddit:
                items = fetch_reddit_json(feed, category)
            else:
                items = fetch_rss(feed, category)

            print(f"{len(items)} items")
            all_items.extend(items)
            stats[category] += len(items)
            time.sleep(CRAWL_DELAY)

    # ── DEDUPLICATE using content-hash ────────────────────────────────────────
    seen = set()
    deduped = []
    for item in all_items:
        h = item_hash(item["title"], item.get("summary", ""))
        if h not in seen:
            seen.add(h)
            deduped.append(item)

    # ── SORT: latest first ────────────────────────────────────────────────────
    deduped.sort(key=lambda x: x.get("published", ""), reverse=True)

    # ── TOPIC SUMMARY ─────────────────────────────────────────────────────────
    topic_counts = defaultdict(int)
    flash_count = 0
    for item in deduped:
        for t in item.get("topics", []):
            topic_counts[t] += 1
        if item.get("flashpoint"):
            flash_count += 1

    output = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "total_items":    len(deduped),
        "flashpoints":    flash_count,
        "category_stats": dict(stats),
        "topic_counts":   dict(topic_counts),
        "top_items":      deduped,        # ALL items — dashboard reads this key
        "items":          deduped,        # backward-compatible alias
    }

    import os
    os.makedirs("data", exist_ok=True)
    with open("data/summary.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open("data/topics.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*62}")
    print(f"  ✓ {len(deduped)} unique items  |  🔥 {flash_count} flashpoints")
    print(f"  Topic breakdown: {dict(topic_counts)}")
    print(f"{'='*62}\n")

if __name__ == "__main__":
    crawl_all()
