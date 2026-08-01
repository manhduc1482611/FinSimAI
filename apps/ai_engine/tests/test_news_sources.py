"""Test nguồn tin RSS: parse feed, nhận diện XML, fetch có retry, lọc trùng."""

import asyncio

import httpx
import pytest

from integrations.news_sources import (
    NewsArticle,
    NewsSource,
    NewsSourceError,
    dedupe_articles,
    fetch_feed,
    fetch_source_with_retry,
    looks_like_xml,
    parse_feed,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Feed Test</title>
    <item>
      <title>Cổ phiếu ngân hàng tăng mạnh phiên sáng</title>
      <link>https://example.com/1</link>
      <description><![CDATA[Diễn biến thị trường hôm nay <b>tích cực</b>.]]></description>
      <pubDate>Wed, 01 Jan 2025 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Tin thứ hai</title>
      <link>https://example.com/2</link>
    </item>
  </channel>
</rss>
"""

SAMPLE_RSS_BYTES = SAMPLE_RSS.encode("utf-8")

SOURCE = NewsSource(id="test", name="Nguồn Test", url="https://example.com/rss")


class TestLooksLikeXml:
    def test_accepts_xml_content_type(self):
        assert looks_like_xml("application/rss+xml; charset=utf-8", b"<rss>")
        assert looks_like_xml("text/xml", b"whatever")

    def test_rejects_html(self):
        assert not looks_like_xml("text/html; charset=utf-8", b"<!doctype html><html>")
        assert not looks_like_xml("", b"<html>")

    def test_detects_xml_by_body_when_type_missing(self):
        assert looks_like_xml("", SAMPLE_RSS_BYTES)


class TestParseFeed:
    def test_parses_entries(self):
        articles = parse_feed(SOURCE, SAMPLE_RSS_BYTES)
        assert len(articles) == 2
        first = articles[0]
        assert first.title == "Cổ phiếu ngân hàng tăng mạnh phiên sáng"
        assert first.url == "https://example.com/1"
        assert first.source_id == "test"
        assert "tích cực" in first.summary
        assert first.published_at.year == 2025

    def test_skips_entries_without_link(self):
        broken = SAMPLE_RSS_BYTES.replace(b"<link>https://example.com/2</link>", b"")
        articles = parse_feed(SOURCE, broken)
        assert all(article.url for article in articles)

    def test_empty_feed_returns_empty(self):
        empty = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
        assert parse_feed(SOURCE, empty) == []


class TestFetchFeed:
    def test_fetch_ok(self):
        def handler(request):
            return httpx.Response(
                200,
                content=SAMPLE_RSS_BYTES,
                headers={"content-type": "application/rss+xml"},
            )

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await fetch_feed(client, SOURCE)

        raw = asyncio.run(run())
        assert raw.startswith(b"<?xml")

    def test_fetch_rejects_html(self):
        def handler(request):
            return httpx.Response(200, content=b"<!doctype html>", headers={"content-type": "text/html"})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await fetch_feed(client, SOURCE)

        with pytest.raises(NewsSourceError):
            asyncio.run(run())

    def test_fetch_raises_on_http_error(self):
        def handler(request):
            return httpx.Response(500, content=b"error")

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                await fetch_feed(client, SOURCE)

        with pytest.raises(NewsSourceError):
            asyncio.run(run())


class TestRetry:
    class FakeSleep:
        def __init__(self):
            self.calls: list[float] = []

        async def __call__(self, delay):
            self.calls.append(delay)

    def test_retries_and_succeeds(self):
        attempts = {"n": 0}

        async def handler(request):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise httpx.ConnectError("lỗi mạng tạm thời", request=request)
            return httpx.Response(200, content=SAMPLE_RSS_BYTES, headers={"content-type": "application/rss+xml"})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await fetch_source_with_retry(
                    SOURCE,
                    retries=3,
                    base_delay=0.001,
                    sleep=self.FakeSleep(),
                    client=client,
                )

        articles = asyncio.run(run())
        assert len(articles) == 2
        assert attempts["n"] == 2

    def test_gives_up_after_retries(self):
        async def handler(request):
            raise httpx.ConnectError("lỗi liên tục", request=request)

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                return await fetch_source_with_retry(
                    SOURCE,
                    retries=2,
                    base_delay=0.001,
                    sleep=self.FakeSleep(),
                    client=client,
                )

        with pytest.raises(NewsSourceError):
            asyncio.run(run())


class TestDedupe:
    def test_removes_duplicates_by_url(self):
        a = NewsArticle(source_id="s", source_name="S", title="A", url="https://x/1")
        b = NewsArticle(source_id="s", source_name="S", title="B", url="https://x/1")
        c = NewsArticle(source_id="s", source_name="S", title="C", url="https://x/2")
        result = dedupe_articles([a, b, c])
        assert [article.title for article in result] == ["A", "C"]
