"""API tests cho /tasks và /admin/tasks — auth + contract của Nhiệm vụ & Thưởng.

Không cần DB thật: override ``get_db`` bằng fake session, override
``get_current_user`` bằng user giả (giống test_contests_api.py).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from core.dependencies import get_current_user, get_db
from fastapi import FastAPI
from models.task import Task
from services import task_service


class _Result:
    def __init__(self) -> None:
        self._first: Any = None

    def scalar_one_or_none(self) -> Any:
        return self._first

    def scalar(self) -> Any:
        return 0

    def scalars(self) -> "_Scalars":
        return _Scalars()

    def all(self) -> list[Any]:
        return []


class _Scalars:
    def all(self) -> list[Any]:
        return []


class _FakeDB:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.stored: dict[tuple[Any, uuid.UUID], Any] = {}

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def get(self, model: Any, obj_id: Any) -> Any:
        return self.stored.get((model, obj_id))

    async def execute(self, stmt: Any) -> _Result:
        result = _Result()
        tasks = [v for (m, _), v in self.stored.items() if m is Task]
        result._first = tasks[0] if tasks else None
        return result

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
            self.stored[(Task, obj.id)] = obj

    async def commit(self) -> None:
        await self.flush()

    async def refresh(self, obj: Any) -> None:
        await self.flush()


def _make_app() -> FastAPI:
    from api.v1.admin import router as admin_router
    from api.v1.tasks import admin_router as tasks_admin_router
    from api.v1.tasks import router as tasks_router

    app = FastAPI()
    app.include_router(tasks_router)
    app.include_router(admin_router)
    app.include_router(tasks_admin_router)
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


def _make_task(code: str = "daily_checkin") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        code=code,
        name="Điểm danh hằng ngày",
        description=None,
        category="daily",
        reward_amount=Decimal("5000.00"),
        target_count=1,
        reset_frequency="daily",
        is_active=True,
        sort_order=0,
        created_at=now,
        updated_at=now,
    )


def _async_return(value: Any) -> Any:
    async def _fn(*args: Any, **kwargs: Any) -> Any:
        return value

    return _fn


# ────────────────────────────────────────────────────────────────────────────
# User endpoints — contract
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_tasks_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")
    payload = {
        "streak_current": 3,
        "streak_longest": 5,
        "total_reward_earned": "10000.00",
        "tasks": [],
    }
    monkeypatch.setattr(task_service, "list_tasks", _async_return(payload))
    resp = await _get(app, "/tasks")
    assert resp.status_code == 200
    assert resp.json() == payload


@pytest.mark.asyncio
async def test_checkin_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")
    payload = {
        "already_checked_in": False,
        "current_streak": 4,
        "longest_streak": 4,
        "reward_earned": "5000.00",
    }
    monkeypatch.setattr(task_service, "checkin", _async_return(payload))
    resp = await _post(app, "/tasks/checkin")
    assert resp.status_code == 200
    assert resp.json() == payload


@pytest.mark.asyncio
async def test_report_mentor_chat_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")

    async def fake_report(db: Any, user: Any, event: str) -> tuple[bool, bool]:
        assert event == "mentor_chat"
        return True, False

    monkeypatch.setattr(task_service, "report_event", fake_report)
    resp = await _post(app, "/tasks/events", {"event": "mentor_chat"})
    assert resp.status_code == 200
    assert resp.json() == {"accepted": True, "rewarded": False}


@pytest.mark.asyncio
async def test_report_unknown_event_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")

    async def fake_report(db: Any, user: Any, event: str) -> tuple[bool, bool]:
        raise task_service.TaskEventUnknownError("Sự kiện không được phép: x")

    monkeypatch.setattr(task_service, "report_event", fake_report)
    resp = await _post(app, "/tasks/events", {"event": "x"})
    assert resp.status_code == 400
    assert "không được phép" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_task_conflict_when_not_claimable(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")

    async def fake_claim(db: Any, user: Any, task_id: Any) -> dict[str, Any]:
        raise task_service.TaskNotClaimableError("Bạn chưa đứng trong top 10")

    monkeypatch.setattr(task_service, "claim_task", fake_claim)
    resp = await _post(app, f"/tasks/{uuid.uuid4()}/claim")
    assert resp.status_code == 409
    assert "top 10" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_claim_task_not_found_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")

    async def fake_claim(db: Any, user: Any, task_id: Any) -> dict[str, Any]:
        raise task_service.TaskServiceError("Nhiệm vụ không tồn tại hoặc đã bị tắt")

    monkeypatch.setattr(task_service, "claim_task", fake_claim)
    resp = await _post(app, f"/tasks/{uuid.uuid4()}/claim")
    assert resp.status_code == 400


# ────────────────────────────────────────────────────────────────────────────
# Admin endpoints — auth + CRUD
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_user_forbidden_on_admin_tasks() -> None:
    app = _make_app()
    _install(app, role="user", email="user@example.com")
    resp = await _get(app, "/admin/tasks")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_host_forbidden_on_admin_tasks() -> None:
    app = _make_app()
    _install(app, role="host", email="host@example.com")
    resp = await _post(app, "/admin/tasks", {"code": "x", "name": "X", "category": "daily"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_tasks_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app()
    _install(app, role="admin", email="admin123@finsimai.local")
    payload = {"items": [], "total": 0}
    monkeypatch.setattr(
        "api.v1.tasks.paginate", _async_return(([], 0))
    )
    resp = await _get(app, "/admin/tasks")
    assert resp.status_code == 200
    assert resp.json() == payload


@pytest.mark.asyncio
async def test_admin_create_task_ok() -> None:
    app = _make_app()
    _install(app, role="admin", email="admin123@finsimai.local")
    resp = await _post(
        app,
        "/admin/tasks",
        {
            "code": "custom_task",
            "name": "Nhiệm vụ tùy chỉnh",
            "category": "learning",
            "reward_amount": "10000.00",
            "target_count": 2,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "custom_task"
    assert body["category"] == "learning"
    assert body["is_active"] is True
    assert body["reward_amount"] == "10000.00"


@pytest.mark.asyncio
async def test_admin_create_duplicate_code_conflict() -> None:
    app = _make_app()
    db = _FakeDB()
    task = _make_task(code="dup_task")
    db.stored[(Task, task.id)] = task
    _install(app, role="admin", email="admin123@finsimai.local")
    app.dependency_overrides[get_db] = lambda: db

    resp = await _post(
        app,
        "/admin/tasks",
        {"code": "dup_task", "name": "Dup", "category": "daily", "reward_amount": "1000.00"},
    )
    assert resp.status_code == 409
    assert "đã tồn tại" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_update_task_ok() -> None:
    app = _make_app()
    db = _FakeDB()
    task = _make_task(code="daily_checkin")
    db.stored[(Task, task.id)] = task
    _install(app, role="admin", email="admin123@finsimai.local")
    app.dependency_overrides[get_db] = lambda: db

    resp = await _patch(app, f"/admin/tasks/{task.id}", {"reward_amount": "7000.00"})
    assert resp.status_code == 200
    assert resp.json()["reward_amount"] == "7000.00"


@pytest.mark.asyncio
async def test_admin_delete_task_soft_deletes() -> None:
    app = _make_app()
    db = _FakeDB()
    task = _make_task(code="daily_checkin")
    db.stored[(Task, task.id)] = task
    _install(app, role="admin", email="admin123@finsimai.local")
    app.dependency_overrides[get_db] = lambda: db

    resp = await _delete(app, f"/admin/tasks/{task.id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_update_missing_task_not_found() -> None:
    app = _make_app()
    _install(app, role="admin", email="admin123@finsimai.local")
    resp = await _patch(app, f"/admin/tasks/{uuid.uuid4()}", {"reward_amount": "1.00"})
    assert resp.status_code == 404


async def _patch(app: FastAPI, path: str, json: dict[str, Any]) -> httpx.Response:
    async with await _client(app) as c:
        return await c.patch(path, json=json)


async def _delete(app: FastAPI, path: str) -> httpx.Response:
    async with await _client(app) as c:
        return await c.delete(path)
