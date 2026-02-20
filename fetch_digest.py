#!/usr/bin/env python3
"""Daily news digest — fetches headlines from RSS feeds and sends via Resend."""

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

MAX_ARTICLES = 15   # per source
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
            # Include if within lookback window, or if timestamp is unavailable
            if published is None or published >= cutoff:
                articles.append({
                    "title": entry.get("title", "(No title)").strip(),
                    "link":  entry.get("link", "#"),
                })
        return articles
    except Exception as e:
        print(f"  [WARN] {name}: {e}")
        return []


def build_html(digest, date_str):
    sections = ""
    for source, articles in digest.items():
        if not articles:
            sections += f"""
            <div style="margin-bottom:28px;">
              <h2 style="font-size:16px;color:#555;border-bottom:1px solid #eee;padding-bottom:4px;">{source}</h2>
              <p style="color:#aaa;font-size:13px;margin:4px 0 0 4px;">No articles found in the last 24 hours.</p>
            </div>"""
            continue
        items = "".join(
            f'<li style="margin-bottom:6px;">'
            f'<a href="{a["link"]}" style="color:#1a0dab;text-decoration:none;">{a["title"]}</a>'
            f'</li>'
            for a in articles
        )
        sections += f"""
        <div style="margin-bottom:28px;">
          <h2 style="font-size:16px;color:#222;border-bottom:2px solid #f0f0f0;padding-bottom:6px;">{source} <span style="font-weight:normal;color:#999;font-size:13px;">({len(articles)})</span></h2>
          <ul style="padding-left:18px;margin:8px 0 0 0;line-height:1.75;font-size:14px;">{items}</ul>
        </div>"""

    total = sum(len(v) for v in digest.values())
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
             max-width:680px;margin:0 auto;padding:24px 20px;color:#333;background:#fff;">
  <h1 style="font-size:22px;color:#111;margin-bottom:4px;">Daily News Digest</h1>
  <p style="color:#888;font-size:13px;margin-top:0;">{date_str} &nbsp;·&nbsp; {total} articles across {len(digest)} sources</p>
  <hr style="border:none;border-top:1px solid #eee;margin:16px 0 24px;">
  {sections}
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0 12px;">
  <p style="color:#bbb;font-size:11px;text-align:center;">Delivered by your news digest bot via GitHub Actions</p>
</body>
</html>"""


def build_plaintext(digest, date_str):
    lines = [f"Daily News Digest — {date_str}", "=" * 50, ""]
    for source, articles in digest.items():
        lines.append(f"[ {source} ]")
        if not articles:
            lines.append("  No articles in the last 24 hours.")
        else:
            for a in articles:
                lines.append(f"  • {a['title']}")
                lines.append(f"    {a['link']}")
        lines.append("")
    return "\n".join(lines)


def send_email(html_content, plain_content, date_str):
    api_key   = os.environ["RESEND_API_KEY"]
    recipient = os.environ["RECIPIENT_EMAIL"]
    from_addr = os.environ.get("FROM_EMAIL", "Daily Digest <onboarding@resend.dev>")

    payload = json.dumps({
        "from":    from_addr,
        "to":      [recipient],
        "subject": f"Daily Digest — {date_str}",
        "html":    html_content,
        "text":    plain_content,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        print(f"Email sent → {recipient} (status {res.status})")


def main():
    date_str = datetime.now().strftime("%B %d, %Y")
    digest = {}
    for name, url in FEEDS.items():
        print(f"Fetching {name}...")
        digest[name] = fetch_feed(name, url)

    html  = build_html(digest, date_str)
    plain = build_plaintext(digest, date_str)
    send_email(html, plain, date_str)


if __name__ == "__main__":
    main()
