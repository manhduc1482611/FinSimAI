"""Test chống look-ahead bias: mọi API đọc công khai phải lọc as-of.

Nguyên tắc: nội dung có ``simulated_at`` trong TƯƠNG LAI (bài sinh trước, lên
lịch phát hành sau) không bao giờ được trả về cho người dùng — dù qua list hay
detail. Test chặn statement SQL gửi xuống DB và kiểm tra điều kiện
``simulated_at <= <mốc hiện tại>`` tồn tại.
"""

import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from core.dependencies import get_current_user_optional, get_db
from fastapi import FastAPI
from realtime.simtime import sim_now
from sqlalchemy import BinaryExpression


class _CapturingDB:
    """Fake AsyncSession: bắt statement để kiểm tra where clause."""

    def __init__(self) -> None:
        self.captured_stmts: list[Any] = []
        self._get_results: dict[Any, Any] = {}

    def queue_get(self, key: Any, value: Any) -> None:
        self._get_results[key] = value

    async def get(self, model: Any, key: Any) -> Any:
        return self._get_results.get(key)

    async def execute(self, stmt: Any) -> SimpleNamespace:
        self.captured_stmts.append(stmt)
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
            scalar=lambda: 0,
            scalars=lambda: SimpleNamespace(all=lambda: []),
            all=lambda: [],
        )


def _install(app: FastAPI) -> _CapturingDB:
    fake_db = _CapturingDB()
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    return fake_db


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path)


def _stmt_where_columns(stmt: Any) -> list[str]:
    """Trích tên cột xuất hiện trong WHERE của statement (đệ quy boolean)."""
    columns: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, BinaryExpression):
            try:
                columns.append(node.left.key or "")
            except AttributeError:
                pass
        for child in node.get_children():
            walk(child)

    where = getattr(stmt, "whereclause", None)
    if where is not None:
        walk(where)
    return columns


def _make_app() -> FastAPI:
    from api.v1.news import router as news_router
    from api.v1.social import router as social_router

    app = FastAPI()
    app.include_router(news_router)
    app.include_router(social_router)
    return app


# ── News ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_news_filters_future_content() -> None:
    app = _make_app()
    db = _install(app)

    resp = await _get(app, "/news")

    assert resp.status_code == 200
    # paginate chạy 2 statement (count + page) — ít nhất 1 phải có as-of filter.
    assert any("simulated_at" in _stmt_where_columns(s) for s in db.captured_stmts), (
        "list_news phải lọc simulated_at <= sim_now()"
    )


@pytest.mark.asyncio
async def test_news_detail_hides_future_item() -> None:
    app = _make_app()
    db = _install(app)

    future_id = uuid.uuid4()
    db.queue_get(future_id, SimpleNamespace(simulated_at=sim_now() + timedelta(days=30)))

    resp = await _get(app, f"/news/{future_id}")
    assert resp.status_code == 404, "Tin tương lai không được lộ qua detail"


@pytest.mark.asyncio
async def test_news_detail_serves_past_item() -> None:
    app = _make_app()
    db = _install(app)

    past_id = uuid.uuid4()
    db.queue_get(
        past_id,
        SimpleNamespace(
            id=past_id,
            title="Đã phát hành",
            summary=None,
            content="Nội dung",
            source="Capia News",
            category="vĩ mô",
            sentiment="neutral",
            impact_score=5.0,
            contest_id=None,
            company_id=None,
            is_ai_generated=True,
            simulated_at=sim_now() - timedelta(hours=1),
            created_at=sim_now() - timedelta(hours=1),
        ),
    )

    resp = await _get(app, f"/news/{past_id}")
    assert resp.status_code == 200


# ── Social ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_social_filters_future_content() -> None:
    app = _make_app()
    db = _install(app)

    resp = await _get(app, "/social")

    assert resp.status_code == 200
    # paginate chạy 2 statement (count + page) — ít nhất 1 phải có as-of filter.
    assert any("simulated_at" in _stmt_where_columns(s) for s in db.captured_stmts), (
        "list_social phải lọc simulated_at <= sim_now()"
    )


@pytest.mark.asyncio
async def test_social_detail_hides_future_post() -> None:
    app = _make_app()
    db = _install(app)

    future_id = uuid.uuid4()
    db.queue_get(future_id, SimpleNamespace(simulated_at=sim_now() + timedelta(days=30)))

    resp = await _get(app, f"/social/{future_id}")
    assert resp.status_code == 404, "Bài đăng tương lai không được lộ qua detail"
