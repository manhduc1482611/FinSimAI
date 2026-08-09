"""API tests cho /ai/content — endpoint nội bộ nhận nội dung AI sinh ra.

Không cần DB thật: override ``get_db`` bằng fake session và override các helper
truy vấn (company lookup / dedupe) để kiểm tra mapping + đếm insert.
"""

import uuid
from typing import Any

import httpx
import pytest
from core.config import settings
from core.dependencies import get_db
from fastapi import FastAPI
from models.news import News
from models.social import SocialPost

from api.v1.ai_sync import (
    _company_by_symbol,
    _news_title_exists,
    _social_post_exists,
    router,
)

INTERNAL_KEY = "test-internal-key-123"


class _FakeDB:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        pass


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _install(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    *,
    company_symbol: str | None = "AAA",
) -> _FakeDB:
    monkeypatch.setattr(settings, "internal_api_key", INTERNAL_KEY)
    db = _FakeDB()
    app.dependency_overrides[get_db] = lambda: db
    company_id = uuid.uuid4()

    async def fake_company_by_symbol(db: Any, symbol: str | None) -> uuid.UUID | None:
        return company_id if symbol == company_symbol else None

    async def fake_news_exists(db: Any, title: str) -> bool:
        return False

    async def fake_social_exists(db: Any, content: str) -> bool:
        return False

    monkeypatch.setattr("api.v1.ai_sync._company_by_symbol", fake_company_by_symbol)
    monkeypatch.setattr("api.v1.ai_sync._news_title_exists", fake_news_exists)
    monkeypatch.setattr("api.v1.ai_sync._social_post_exists", fake_social_exists)
    return db


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _batch() -> dict[str, Any]:
    return {
        "articles": [
            {
                "title": "Nhà đầu tư thận trọng trước nhịp điều chỉnh",
                "summary": "Tóm tắt",
                "content": "Nội dung bài báo.",
                "category": "macro_domestic",
                "sentiment": "negative",
                "impact_score": 4,
                "company_symbol": "AAA",
            },
            {
                "title": "Cổ phiếu AAA tăng mạnh sau kết quả kinh doanh",
                "summary": "Tóm tắt",
                "content": "Nội dung bài báo doanh nghiệp.",
                "category": "company",
                "sentiment": "positive",
                "impact_score": 6,
            },
        ],
        "social_posts": [
            {
                "author_name": "Tin đồn từ cộng đồng",
                "persona_type": "rumor_birds",
                "content": "Nghe nói AAA sắp công bố tin lớn, anh em để ý.",
                "sentiment": "negative",
                "virality_score": 7,
                "company_symbol": "AAA",
                "has_deception": True,
            }
        ],
    }


@pytest.mark.asyncio
async def test_missing_internal_key_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_api_key", "")
    app = _make_app()
    async with await _client(app) as c:
        resp = await c.post("/ai/content", json=_batch())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_wrong_internal_key_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_api_key", INTERNAL_KEY)
    app = _make_app()
    async with await _client(app) as c:
        resp = await c.post(
            "/ai/content",
            json=_batch(),
            headers={"X-Internal-Api-Key": "wrong-key"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ingest_maps_content_and_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    db = _install(app, monkeypatch)
    async with await _client(app) as c:
        resp = await c.post(
            "/ai/content", json=_batch(), headers={"X-Internal-Api-Key": INTERNAL_KEY}
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body == {"inserted_news": 2, "inserted_social_posts": 1, "skipped_news": 0, "skipped_social_posts": 0}

    news_items = [obj for obj in db.added if isinstance(obj, News)]
    assert len(news_items) == 2
    macro = next(n for n in news_items if n.category == "vĩ mô")
    company = next(n for n in news_items if n.category == "doanh nghiệp")
    assert macro.company_id is not None  # symbol AAA → company_id
    assert company.company_id is None
    assert all(n.is_ai_generated for n in news_items)
    assert company.impact_score == 6

    posts = [obj for obj in db.added if isinstance(obj, SocialPost)]
    assert len(posts) == 1
    assert posts[0].is_trap is True
    assert posts[0].persona_type == "rumor_birds"
    assert posts[0].company_id is not None


@pytest.mark.asyncio
async def test_ingest_skips_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    db = _install(app, monkeypatch)

    async def fake_news_exists(db: Any, title: str) -> bool:
        return True

    async def fake_social_exists(db: Any, content: str) -> bool:
        return True

    monkeypatch.setattr("api.v1.ai_sync._news_title_exists", fake_news_exists)
    monkeypatch.setattr("api.v1.ai_sync._social_post_exists", fake_social_exists)

    async with await _client(app) as c:
        resp = await c.post(
            "/ai/content", json=_batch(), headers={"X-Internal-Api-Key": INTERNAL_KEY}
        )
    assert resp.status_code == 201
    assert resp.json() == {"inserted_news": 0, "inserted_social_posts": 0, "skipped_news": 2, "skipped_social_posts": 1}
    assert db.added == []
