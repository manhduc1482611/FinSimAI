"""API tests cho /contests và /admin — auth 403, contract create/activate/join.

Không cần DB thật: override ``get_db`` bằng fake session, override
``get_current_user`` bằng user giả (giống test_roles.py).
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from core.dependencies import get_current_user, get_db
from fastapi import FastAPI
from models.contest import Contest
from schemas.contest import ContestCreateRequest, build_config
from services import contest_service
from sqlalchemy.ext.asyncio import AsyncSession


class _FakeDB:
    """Fake AsyncSession đủ cho create (unique_slug/commit/refresh) và generate."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def execute(self, stmt: Any) -> SimpleNamespace:
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
            scalar=lambda: 0,
            scalars=lambda: SimpleNamespace(all=lambda: []),
            all=lambda: [],
        )

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "is_active", None) is None:
                obj.is_active = True
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(timezone.utc)
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = obj.created_at

    async def commit(self) -> None:
        await self.flush()

    async def refresh(self, obj: Any) -> None:
        await self.flush()


def _make_app() -> FastAPI:
    from api.v1.admin import router as admin_router
    from api.v1.contests import router as contests_router

    app = FastAPI()
    app.include_router(contests_router)
    app.include_router(admin_router)
    return app


def _install(
    app: FastAPI, role: str, email: str, user_id: uuid.UUID | None = None
) -> SimpleNamespace:
    fake_user = SimpleNamespace(
        id=user_id or uuid.uuid4(), role=role, email=email, is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: _FakeDB()
    return fake_user


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _post(app: FastAPI, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
    async with await _client(app) as c:
        return await c.post(path, json=json or {})


async def _get(app: FastAPI, path: str) -> httpx.Response:
    async with await _client(app) as c:
        return await c.get(path)


def _make_contest(owner_id: uuid.UUID, slug: str = "ct", status: str = "draft") -> SimpleNamespace:
    config = build_config(
        ContestCreateRequest(name="Contest", slug=slug, template="classic")
    )
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        name="Contest",
        description=None,
        status=status,
        config=config.model_dump(mode="json"),
        owner_id=owner_id,
        starts_at=None,
        ends_at=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


# ────────────────────────────────────────────────────────────────────────────
# Auth contract
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_user_forbidden_to_create_contest() -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")
    resp = await _post(app, "/contests", {"name": "X"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_host_can_create_contest() -> None:
    app = _make_app()
    _install(app, role="host", email="host@example.com")
    resp = await _post(
        app,
        "/contests",
        {"name": "Cuộc thi A", "template": "classic", "industry": "công nghệ"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "cuoc-thi-a"
    assert body["status"] == "draft"
    assert body["config"]["template"] == "classic"
    assert body["config"]["rules"]["start_cash"] == "100000000.00"


@pytest.mark.asyncio
async def test_host_forbidden_on_admin_endpoints() -> None:
    app = _make_app()
    _install(app, role="host", email="host@example.com")
    resp = await _get(app, "/admin/users")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_forbidden_on_admin_endpoints() -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")
    resp = await _get(app, "/admin/contests")
    assert resp.status_code == 403


# ────────────────────────────────────────────────────────────────────────────
# Ownership & activation
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_host_cannot_activate_other_contest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _make_app()
    owner_id = uuid.uuid4()
    contest = _make_contest(owner_id=owner_id)
    other_host = _install(app, role="host", email="other@example.com")
    assert other_host.id != owner_id
    monkeypatch.setattr(contest_service, "get_contest", _async_return(contest))
    resp = await _post(app, f"/contests/{contest.slug}/activate")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_activate_runs_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _make_app()
    owner = _install(app, role="host", email="owner@example.com")
    contest = _make_contest(owner_id=owner.id, status="draft")
    monkeypatch.setattr(contest_service, "get_contest", _async_return(contest))
    generated: list[str] = []

    async def fake_activate(db: Any, c: Any) -> Any:
        generated.append(c.slug)
        return c

    monkeypatch.setattr(contest_service, "activate_contest", fake_activate)
    resp = await _post(app, f"/contests/{contest.slug}/activate")
    assert resp.status_code == 200
    assert generated == [contest.slug]


@pytest.mark.asyncio
async def test_join_draft_contest_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _make_app()
    contest = _make_contest(owner_id=uuid.uuid4(), status="draft")
    _install(app, role="user", email="user@example.com")
    monkeypatch.setattr(contest_service, "get_contest", _async_return(contest))
    resp = await _post(app, f"/contests/{contest.slug}/join")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_join_active_contest_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _make_app()
    contest = _make_contest(owner_id=uuid.uuid4(), status="active")
    _install(app, role="user", email="user@example.com")
    monkeypatch.setattr(contest_service, "get_contest", _async_return(contest))
    monkeypatch.setattr(contest_service, "get_membership", _async_return(None))
    joined: list[str] = []

    async def fake_join(db: Any, user: Any, c: Any) -> Any:
        joined.append(c.slug)
        return SimpleNamespace(contest_id=c.id, user_id=user.id)

    monkeypatch.setattr(contest_service, "join_contest", fake_join)
    resp = await _post(app, f"/contests/{contest.slug}/join")
    assert resp.status_code == 200
    assert resp.json()["joined"] is True
    assert joined == [contest.slug]


def _async_return(value: Any) -> Callable[..., Awaitable[Any]]:
    async def _fn(*args: Any, **kwargs: Any) -> Any:
        return value

    return _fn


# ────────────────────────────────────────────────────────────────────────────
# Generator (service layer, fake db)
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_content_creates_companies_news_social() -> None:
    from models.company import Company
    from models.news import News
    from models.social import SocialPost

    db = _FakeDB()
    contest = _make_contest(owner_id=uuid.uuid4())
    contest.config = build_config(
        ContestCreateRequest(
            name="Contest",
            template="classic",
            industry="công nghệ",
            company_count=3,
        )
    ).model_dump(mode="json")

    result = await contest_service.generate_content(
        cast(AsyncSession, db), cast(Contest, contest)
    )

    companies = [o for o in db.added if isinstance(o, Company)]
    news = [o for o in db.added if isinstance(o, News)]
    social = [o for o in db.added if isinstance(o, SocialPost)]
    assert len(companies) == 3
    assert all(c.contest_id == contest.id for c in companies)
    assert all(c.symbol == s for c, s in zip(companies, result.config["content"]["symbols"]))
    assert len(news) >= 3
    assert len(social) >= 3
    assert all(n.contest_id == contest.id for n in news)
    assert all(s.contest_id == contest.id for s in social)
    assert result.status == "active"
    assert result.config["content"]["generated"] is True
    assert result.config["content"]["company_count"] == 3


@pytest.mark.asyncio
async def test_generate_content_idempotent() -> None:
    db = _FakeDB()
    contest = _make_contest(owner_id=uuid.uuid4())
    contest.config = build_config(
        ContestCreateRequest(name="Contest", template="micro", company_count=3)
    ).model_dump(mode="json")

    first = await contest_service.generate_content(
        cast(AsyncSession, db), cast(Contest, contest)
    )
    added_after_first = len(db.added)
    second = await contest_service.generate_content(
        cast(AsyncSession, db), cast(Contest, contest)
    )

    assert second is first
    assert len(db.added) == added_after_first  # không nhân đôi dữ liệu
    assert second.config["content"]["generated"] is True


@pytest.mark.asyncio
async def test_generate_content_no_auto_content() -> None:
    from models.news import News
    from models.social import SocialPost

    db = _FakeDB()
    contest = _make_contest(owner_id=uuid.uuid4())
    contest.config = build_config(
        ContestCreateRequest(
            name="Contest", template="classic", auto_news=False, auto_social=False
        )
    ).model_dump(mode="json")

    await contest_service.generate_content(cast(AsyncSession, db), cast(Contest, contest))
    news = [o for o in db.added if isinstance(o, News)]
    social = [o for o in db.added if isinstance(o, SocialPost)]
    assert news == []
    assert social == []
    assert Decimal(contest.config["content"]["news_count"]) == 0
