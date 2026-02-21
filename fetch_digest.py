#!/usr/bin/env python3
"""Daily news digest — clusters top stories with Claude, sends to Slack."""

import os
import json
import urllib.request
import feedparser
import anthropic
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

MAX_ARTICLES = 10
HOURS_LOOKBACK = 24


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


def cluster_articles(digest):
    """Use Claude to find top 5 cross-source story clusters with summaries."""
    # Flatten all articles with a numeric index
    all_articles = []
    for source, articles in digest.items():
        for a in articles:
            all_articles.append({
                "idx":    len(all_articles),
                "source": source,
                "title":  a["title"],
                "link":   a["link"],
            })

    if not all_articles:
        return [], {s: v for s, v in digest.items()}

    article_list = "\n".join(
        f"[{a['idx']}] {a['source']}: {a['title']}"
        for a in all_articles
    )

    prompt = f"""Here are {len(all_articles)} news articles from various sources published today:

{article_list}

Identify the top 5 news stories covered by MULTIPLE sources (same event or topic in 2+ sources).
For each cluster:
- Write a 2-3 sentence neutral summary in Korean (한국어로)
- List the article indices that belong to this cluster

Return ONLY valid JSON, no extra text:
{{
  "clusters": [
    {{
      "topic": "간단한 토픽 제목 (한국어)",
      "summary": "2-3문장 요약.",
      "indices": [0, 3, 7]
    }}
  ]
}}

Order by number of sources covering the story (most first). Only include stories with 2+ sources."""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    clusters = json.loads(raw).get("clusters", [])[:5]

    # Enrich clusters with source names and links
    clustered_indices = set()
    for cluster in clusters:
        indices = cluster.get("indices", [])
        cluster["sources"] = list({all_articles[i]["source"] for i in indices if i < len(all_articles)})
        cluster["articles"] = [
            {"title": all_articles[i]["title"], "link": all_articles[i]["link"]}
            for i in indices if i < len(all_articles)
        ]
        clustered_indices.update(indices)

    # Build remaining (non-clustered) articles per source
    remaining = {source: [] for source in digest}
    for a in all_articles:
        if a["idx"] not in clustered_indices:
            remaining[a["source"]].append({"title": a["title"], "link": a["link"]})

    return clusters, remaining


def post_to_slack(webhook_url, text):
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        return res.status


def send_slack(digest, clusters, remaining, date_str):
    webhook_url = os.environ["SLACK_WEBHOOK_URL"]
    total = sum(len(v) for v in digest.values())

    # Header
    post_to_slack(webhook_url, f"*📰 Daily News Digest — {date_str}*  |  {total}개 기사 · {len(digest)}개 매체")

    # Top stories clusters
    if clusters:
        post_to_slack(webhook_url, "━━━━━━━━━━━━━━━━━━━━\n*📌 Top Stories*")
        for i, cluster in enumerate(clusters, 1):
            links_str = "  ".join(
                f"<{a['link']}|{src}>"
                for src, a in zip(cluster["sources"], cluster["articles"])
            )
            lines = [
                f"*{i}. {cluster['topic']}*",
                cluster["summary"],
                f"↗ {links_str}",
            ]
            post_to_slack(webhook_url, "\n".join(lines))

    # Remaining articles by source
    post_to_slack(webhook_url, "━━━━━━━━━━━━━━━━━━━━\n*📂 매체별 기사*")
    for source, articles in remaining.items():
        if not articles:
            continue
        lines = [f"*{source}*"]
        for a in articles:
            lines.append(f"• <{a['link']}|{a['title']}>")
        post_to_slack(webhook_url, "\n".join(lines))

    print(f"Slack digest sent — {len(clusters)} clusters, {total} total articles")


def main():
    date_str = datetime.now().strftime("%B %d, %Y")

    digest = {}
    for name, url in FEEDS.items():
        print(f"Fetching {name}...")
        digest[name] = fetch_feed(name, url)

    print("Clustering with Claude...")
    clusters, remaining = cluster_articles(digest)

    send_slack(digest, clusters, remaining, date_str)


if __name__ == "__main__":
    main()
