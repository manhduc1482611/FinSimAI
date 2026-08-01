"""Nguồn tin tức RSS của FinSimAI AI Engine.

Trách nhiệm:
- Định nghĩa các nguồn RSS ĐÃ KIỂM CHỨNG hoạt động cho thị trường VN
  (Google News RSS theo từ khoá + RSS VnExpress).
- Fetch nội dung feed qua HTTP async (``httpx``) có timeout + User-Agent.
- TỪ CHỐI nội dung HTML giả danh RSS — tránh nhét dữ liệu nhiễu vào pipeline.
- Parse feed bằng ``feedparser`` thành :class:`NewsArticle` chuẩn hoá.
- Loại trùng bài theo URL.

Nguyên tắc an toàn: luôn bó buộc timeout, không thực thi mã từ feed, chỉ đọc
trường dữ liệu cần thiết, tất cả hàm ngoài fetch đều thuần (pure) để dễ test.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
DEFAULT_USER_AGENT = "FinSimAI-Bot/0.1 (market simulation; local demo)"

# Nhận diện feed XML hợp lệ ngay cả khi thiếu content-type.
_XML_PREFIXES = (b"<?xml", b"<rss", b"<feed")


@dataclass(frozen=True)
class NewsSource:
    """Một nguồn RSS duy nhất."""

    id: str
    name: str
    url: str
    language: str = "vi"
    enabled: bool = True


@dataclass(frozen=True)
class NewsArticle:
    """Một bài báo chuẩn hoá sau khi parse feed."""

    source_id: str
    source_name: str
    title: str
    url: str
    published_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class FeedConfig:
    """Cấu hình một lần cào feed."""

    sources: tuple[NewsSource, ...]
    max_articles_per_source: int = 20
    max_concurrent: int = 4
    timeout: httpx.Timeout = field(default_factory=lambda: DEFAULT_TIMEOUT)
    user_agent: str = DEFAULT_USER_AGENT
    retries: int = 3
    base_delay: float = 1.0


class NewsSourceError(RuntimeError):
    """Lỗi fetch hoặc parse một nguồn RSS."""


def _google_news_url(query: str) -> str:
    from urllib.parse import urlencode

    params = {"q": f'"{query}"', "hl": "vi", "gl": "VN", "ceid": "VN:vi"}
    return f"https://news.google.com/rss/search?{urlencode(params)}"


def default_sources() -> tuple[NewsSource, ...]:
    """Danh sách nguồn mặc định — tất cả đã kiểm chứng trả về RSS hợp lệ."""
    google = [
        NewsSource(
            id=f"google_news_{index}",
            name=f"Google News (VN) — {query}",
            url=_google_news_url(query),
        )
        for index, query in enumerate(["chứng khoán", "VN-Index", "lãi suất", "bất động sản"])
    ]
    vnexpress = [
        NewsSource(id="vnexpress_kinh_doanh", name="VnExpress — Kinh doanh", url="https://vnexpress.net/rss/kinh-doanh.rss"),
        NewsSource(id="vnexpress_the_gioi", name="VnExpress — Thế giới", url="https://vnexpress.net/rss/the-gioi.rss"),
        NewsSource(id="vnexpress_bat_dong_san", name="VnExpress — Bất động sản", url="https://vnexpress.net/rss/bat-dong-san.rss"),
    ]
    return (*google, *vnexpress)


def default_feed_config(**overrides: Any) -> FeedConfig:
    """FeedConfig mặc định từ :func:`default_sources` (cho phép ghi đè)."""
    kwargs: dict[str, Any] = {"sources": default_sources()}
    kwargs.update(overrides)
    return FeedConfig(**kwargs)


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def _entry_datetime(entry: Any) -> datetime:
    """Lấy thời gian công bố từ feed; fallback về thời điểm hiện tại."""
    for key in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, key, None)
        if struct:
            try:
                return datetime.fromtimestamp(time.mktime(struct), tz=UTC)
            except (ValueError, OverflowError, TypeError):
                continue
    return datetime.now(UTC)


def looks_like_xml(content_type: str, body: bytes) -> bool:
    """Kiểm tra nội dung có vẻ là XML feed thật (không phải HTML)."""
    ctype = content_type.lower().split(";")[0].strip()
    if ctype in {
        "text/xml",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
    }:
        return True
    head = body[:512].lstrip().lower()
    return head.startswith(_XML_PREFIXES)


def parse_feed(source: NewsSource, raw: bytes) -> list[NewsArticle]:
    """Parse nội dung feed (bytes) thành danh sách bài chuẩn hoá."""
    parsed = feedparser.parse(raw)
    entries = parsed.entries or []
    articles: list[NewsArticle] = []
    for entry in entries:
        title = _clean(getattr(entry, "title", "") or "")
        url = (getattr(entry, "link", "") or "").strip()
        if not title or not url:
            continue
        summary = _clean(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
        articles.append(
            NewsArticle(
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=url,
                published_at=_entry_datetime(entry),
                summary=summary[:500],
            )
        )
    return articles


async def fetch_feed(client: httpx.AsyncClient, source: NewsSource) -> bytes:
    """Fetch nội dung feed; ném :class:`NewsSourceError` nếu không phải RSS."""
    try:
        response = await client.get(source.url)
    except httpx.HTTPError as exc:
        raise NewsSourceError(f"Lỗi mạng khi fetch {source.id}: {exc}") from exc
    if response.status_code != 200:
        raise NewsSourceError(f"{source.id} trả về HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "")
    if not looks_like_xml(content_type, response.content):
        raise NewsSourceError(
            f"{source.id} không trả về RSS hợp lệ (content-type={content_type!r})"
        )
    return response.content


async def fetch_source_articles(
    source: NewsSource,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list[NewsArticle]:
    """Fetch + parse một nguồn (client ngoài tuỳ chọn, dùng cho test)."""
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
    }
    if client is not None:
        raw = await fetch_feed(client, source)
    else:
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as inner_client:
            raw = await fetch_feed(inner_client, source)
    return parse_feed(source, raw)


async def fetch_source_with_retry(
    source: NewsSource,
    *,
    retries: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    client: httpx.AsyncClient | None = None,
) -> list[NewsArticle]:
    """Fetch có retry + backoff exponential; ném lỗi sau hết số lần thử."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return await fetch_source_articles(source, client=client)
        except (NewsSourceError, httpx.HTTPError) as exc:
            last_error = exc
            delay = base_delay * (2**attempt)
            logger.warning(
                "Fetch %s thất bại (lần %d/%d): %s — thử lại sau %.1fs",
                source.id,
                attempt + 1,
                retries,
                exc,
                delay,
            )
            await sleep(delay)
    raise NewsSourceError(
        f"Không fetch được {source.id} sau {retries} lần: {last_error}"
    ) from last_error


def dedupe_articles(articles: Sequence[NewsArticle]) -> list[NewsArticle]:
    """Loại bài trùng URL, giữ bản đầu tiên."""
    seen: set[str] = set()
    result: list[NewsArticle] = []
    for article in articles:
        key = article.url
        if key in seen:
            continue
        seen.add(key)
        result.append(article)
    return result
