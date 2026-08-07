"""API tests cho phân quyền ``require_roles`` (Phase 1).

Kiểm tra contract HTTP 403 khi user thiếu role, và ràng buộc ``ADMIN_EMAILS``
(admin ngoài danh sách cho phép vẫn bị từ chối). Service layer được
monkeypatch — không cần DB thật.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from core.config import settings
from core.dependencies import get_current_user, require_roles
from fastapi import Depends, FastAPI


def _make_app(roles: tuple[str, ...]) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected(user: Any = Depends(require_roles(*roles))) -> dict[str, Any]:
        return {"user_id": str(user.id), "role": user.role}

    return app


def _install_user(app: FastAPI, role: str, email: str) -> None:
    fake_user = SimpleNamespace(
        id=uuid.uuid4(), role=role, email=email, is_active=True
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        return await c.get(path)


@pytest.mark.asyncio
async def test_user_forbidden_on_host_endpoint() -> None:
    app = _make_app(("host",))
    _install_user(app, role="user", email="user@example.com")
    resp = await _get(app, "/protected")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_host_allowed_on_host_endpoint() -> None:
    app = _make_app(("host",))
    _install_user(app, role="host", email="host@example.com")
    resp = await _get(app, "/protected")
    assert resp.status_code == 200
    assert resp.json()["role"] == "host"


@pytest.mark.asyncio
async def test_host_forbidden_on_admin_endpoint() -> None:
    app = _make_app(("admin",))
    _install_user(app, role="host", email="host@example.com")
    resp = await _get(app, "/protected")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_in_allowed_list_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "admin_emails", ["boss@example.com"])
    app = _make_app(("admin",))
    _install_user(app, role="admin", email="boss@example.com")
    resp = await _get(app, "/protected")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_outside_allowed_list_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defense in depth: role=admin trong DB nhưng email không trong ADMIN_EMAILS → 403."""
    monkeypatch.setattr(settings, "admin_emails", ["boss@example.com"])
    app = _make_app(("admin",))
    _install_user(app, role="admin", email="intruder@example.com")
    resp = await _get(app, "/protected")
    assert resp.status_code == 403
