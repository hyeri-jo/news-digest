#!/usr/bin/env python3
"""Daily news digest — fetches headlines from RSS feeds and sends to Slack."""

import os
import json
import urllib.request
import feedparser
from datetime import datetime, timedelta, timezone

FEEDS = {
    "The Verge":        "https://www.theverge.com/rss/index.xml",
    "TechCrunch":       "https://techcrunch.com/feed/",
    "Wired":            "https://www.wired.com/feed/rss",
    "404 Media":        "https://www.404media.co/rss/",
    "Bloomberg":        "https://feeds.bloomberg.com/technology/news.rss",
    "Business Insider": "https://feeds.businessinsider.com/custom/all",
    "Fortune":          "https://fortune.com/feed/",
    "Forbes":           "https://www.forbes.com/innovation/feed2/",
    "New York Times":   "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "WSJ":              "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "TradedVC":         "https://www.tradedvc.com/rss.xml",
    "Google Trends":    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
}

MAX_ARTICLES = 10   # per source
HOURS_LOOKBACK = 24 # only show articles from the last 24 hours


def fetch_feed(name, url):
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)
        articles = []
        for entry in feed.entries[:MAX_ARTICLES]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
            if published is None or published >= cutoff:
                articles.append({
                    "title": entry.get("title", "(No title)").strip(),
                    "link":  entry.get("link", "#"),
                })
        return articles
    except Exception as e:
        print(f"  [WARN] {name}: {e}")
        return []


def post_to_slack(webhook_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        return res.status


def send_slack(digest, date_str):
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    total = sum(len(v) for v in digest.values())

    # Header message
    post_to_slack(webhook_url, {
        "text": f"*Daily News Digest — {date_str}*  |  {total} articles · {len(digest)} sources"
    })

    # One message per source
    for source, articles in digest.items():
        if not articles:
            continue
        lines = [f"*{source}*"]
        for a in articles:
            lines.append(f"• <{a['link']}|{a['title']}>")
        post_to_slack(webhook_url, {"text": "\n".join(lines)})

    print(f"Slack digest sent ({total} articles)")


def main():
    date_str = datetime.now().strftime("%B %d, %Y")
    digest = {}
    for name, url in FEEDS.items():
        print(f"Fetching {name}...")
        digest[name] = fetch_feed(name, url)

    send_slack(digest, date_str)


if __name__ == "__main__":
    main()
