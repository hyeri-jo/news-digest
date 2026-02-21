#!/usr/bin/env python3
"""
Self-test suite for fetch_digest.py
지금까지 발생한 에러들을 기반으로 만든 테스트셋

실행: python test_digest.py
환경변수 있으면 통합 테스트까지, 없으면 단위 테스트만 실행
"""

import os
import json
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock

# ── 테스트 대상 import ──────────────────────────────────────────────────────
from fetch_digest import (
    FEEDS,
    fetch_feed,
    cluster_articles,
    post_to_slack,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. 의존성 / 임포트 테스트  (과거 에러: ModuleNotFoundError: anthropic)
# ══════════════════════════════════════════════════════════════════════════════
class TestImports(unittest.TestCase):

    def test_feedparser_importable(self):
        import feedparser
        self.assertTrue(True)

    def test_anthropic_importable(self):
        """requirements.txt에 anthropic이 빠졌을 때 잡아냄"""
        import anthropic
        self.assertTrue(True)

    def test_stdlib_modules(self):
        import os, json, urllib.request
        self.assertTrue(True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 환경변수 테스트  (과거 에러: KeyError, 잘못된 API 키로 403)
# ══════════════════════════════════════════════════════════════════════════════
class TestEnvVars(unittest.TestCase):

    REQUIRED = ["SLACK_WEBHOOK_URL", "ANTHROPIC_API_KEY"]

    def test_env_vars_present(self):
        """GitHub Secrets / 로컬 환경변수 누락 감지"""
        missing = [k for k in self.REQUIRED if not os.environ.get(k)]
        self.assertEqual(
            missing, [],
            f"필수 환경변수 누락: {missing}\n"
            "GitHub: Settings → Secrets → Actions 에서 추가하세요."
        )

    def test_slack_webhook_format(self):
        url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not url:
            self.skipTest("SLACK_WEBHOOK_URL 미설정 — 건너뜀")
        self.assertTrue(
            url.startswith("https://hooks.slack.com/"),
            f"SLACK_WEBHOOK_URL 형식이 잘못됨: {url[:40]}..."
        )

    def test_anthropic_key_format(self):
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            self.skipTest("ANTHROPIC_API_KEY 미설정 — 건너뜀")
        self.assertTrue(
            key.startswith("sk-ant-"),
            f"ANTHROPIC_API_KEY 형식이 잘못됨 (sk-ant- 로 시작해야 함)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 3. RSS 피드 테스트  (과거 에러: TradedVC 등 일부 피드 빈 결과)
# ══════════════════════════════════════════════════════════════════════════════
class TestFeeds(unittest.TestCase):

    # 반드시 기사가 와야 하는 핵심 피드
    MUST_WORK = ["The Verge", "TechCrunch", "Wired", "Google Trends"]

    def test_feed_urls_defined(self):
        """FEEDS 딕셔너리에 모든 매체가 있는지 확인"""
        expected = [
            "The Verge", "TechCrunch", "Wired", "404 Media", "Bloomberg",
            "Business Insider", "Fortune", "Forbes",
            "New York Times", "WSJ", "Google Trends",
        ]
        for name in expected:
            self.assertIn(name, FEEDS, f"FEEDS에 '{name}' 없음")

    def test_core_feeds_return_articles(self):
        """핵심 피드가 실제로 기사를 반환하는지 확인 (네트워크 필요)"""
        for name in self.MUST_WORK:
            with self.subTest(feed=name):
                articles = fetch_feed(name, FEEDS[name])
                self.assertGreater(
                    len(articles), 0,
                    f"'{name}' 피드에서 기사를 가져오지 못함 — URL 확인: {FEEDS[name]}"
                )

    def test_fetch_returns_title_and_link(self):
        """반환된 기사에 title과 link가 있는지 확인"""
        articles = fetch_feed("The Verge", FEEDS["The Verge"])
        if not articles:
            self.skipTest("The Verge 피드 응답 없음")
        for a in articles:
            self.assertIn("title", a)
            self.assertIn("link", a)
            self.assertTrue(a["title"], "title이 비어 있음")
            self.assertTrue(a["link"].startswith("http"), f"link 형식 이상: {a['link']}")

    def test_all_feeds_reachable(self):
        """모든 피드 URL에 HTTP 접근 가능한지 확인 (4xx/5xx 감지)"""
        failures = []
        for name, url in FEEDS.items():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    if r.status >= 400:
                        failures.append(f"{name}: HTTP {r.status}")
            except Exception as e:
                failures.append(f"{name}: {e}")
        if failures:
            print("\n[피드 접근 실패 목록]")
            for f in failures:
                print(f"  • {f}")
        # 12개 중 9개 이상은 반드시 성공해야 함
        self.assertLessEqual(
            len(failures), 3,
            f"피드 접근 실패 {len(failures)}개:\n" + "\n".join(failures)
        )


# ══════════════════════════════════════════════════════════════════════════════
# 4. Claude JSON 파싱 테스트  (과거 에러: 마크다운 코드펜스로 감싸진 JSON)
# ══════════════════════════════════════════════════════════════════════════════
class TestClusterParsing(unittest.TestCase):

    SAMPLE_DIGEST = {
        "The Verge": [
            {"title": "Xbox chief Phil Spencer is leaving Microsoft", "link": "https://theverge.com/1"},
            {"title": "SCOTUS rules Trump tariffs illegal", "link": "https://theverge.com/2"},
        ],
        "Bloomberg": [
            {"title": "Microsoft Names Sharma to Lead Xbox", "link": "https://bloomberg.com/1"},
            {"title": "OpenAI Revenue Forecast $280B by 2030", "link": "https://bloomberg.com/2"},
        ],
        "TechCrunch": [
            {"title": "Phil Spencer Retires From Xbox", "link": "https://techcrunch.com/1"},
            {"title": "Anthropic rolls out bug-hunting AI tool", "link": "https://techcrunch.com/2"},
        ],
    }

    def _parse_raw(self, raw):
        """fetch_digest.py 와 동일한 파싱 로직"""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw).get("clusters", [])

    def test_parse_plain_json(self):
        raw = '{"clusters": [{"topic": "Xbox", "summary": "요약", "indices": [0, 2, 4]}]}'
        clusters = self._parse_raw(raw)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["topic"], "Xbox")

    def test_parse_json_with_code_fence(self):
        """Claude가 ```json ... ``` 으로 감싸서 줄 때"""
        raw = '```json\n{"clusters": [{"topic": "Xbox", "summary": "요약", "indices": [0]}]}\n```'
        clusters = self._parse_raw(raw)
        self.assertEqual(len(clusters), 1)

    def test_parse_json_with_plain_fence(self):
        """Claude가 ``` ... ``` 으로 감싸서 줄 때 (json 없이)"""
        raw = '```\n{"clusters": [{"topic": "Xbox", "summary": "요약", "indices": [0]}]}\n```'
        clusters = self._parse_raw(raw)
        self.assertEqual(len(clusters), 1)

    def test_empty_digest_returns_no_clusters(self):
        clusters, remaining = cluster_articles({})
        self.assertEqual(clusters, [])
        self.assertEqual(remaining, {})

    def test_cluster_articles_with_mock(self):
        """실제 API 호출 없이 cluster_articles 로직 검증"""
        mock_response_json = json.dumps({
            "clusters": [{
                "topic": "Xbox 리더십 교체",
                "summary": "Phil Spencer가 Microsoft Xbox를 떠나고 Asha Sharma가 새 수장이 됩니다.",
                "indices": [0, 2, 4]
            }]
        })
        mock_content = MagicMock()
        mock_content.text = mock_response_json
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        with patch("fetch_digest.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_response
            clusters, remaining = cluster_articles(self.SAMPLE_DIGEST)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["topic"], "Xbox 리더십 교체")
        # 클러스터에 포함된 기사는 remaining에서 제거됐는지 확인
        all_remaining = [a for arts in remaining.values() for a in arts]
        remaining_titles = [a["title"] for a in all_remaining]
        self.assertNotIn("Xbox chief Phil Spencer is leaving Microsoft", remaining_titles)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Slack 발송 테스트  (과거 에러: 403, webhook URL 미등록)
# ══════════════════════════════════════════════════════════════════════════════
class TestSlack(unittest.TestCase):

    def test_slack_ping(self):
        """실제 Slack webhook으로 핑 메시지 전송 (환경변수 있을 때만)"""
        url = os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            self.skipTest("SLACK_WEBHOOK_URL 미설정 — 건너뜀")
        status = post_to_slack(url, "_[test] news-digest 셀프 테스트 통과 ✓_")
        self.assertEqual(status, 200, f"Slack webhook 응답 코드: {status}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    unittest.main(verbosity=2)
