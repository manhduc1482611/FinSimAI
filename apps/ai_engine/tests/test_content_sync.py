"""Test content_sync: no-op khi chưa cấu hình, POST đúng endpoint khi đã cấu hình."""

import pytest

from integrations import content_sync


async def test_sync_is_noop_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BACKEND_GATEWAY_URL", raising=False)
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    result = await content_sync.sync_content(
        articles=[{"title": "x"}], social_posts=[]
    )
    assert result is None


async def test_sync_posts_batch_to_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_GATEWAY_URL", "http://gateway:8000/")
    monkeypatch.setenv("INTERNAL_API_KEY", "secret")

    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, json: object, headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(content_sync.httpx, "AsyncClient", lambda **kw: FakeClient())

    await content_sync.sync_content(
        articles=[{"title": "bài A"}], social_posts=[{"content": "post B"}]
    )

    assert captured["url"] == "http://gateway:8000/api/v1/ai/content"
    assert captured["headers"] == {"X-Internal-Api-Key": "secret"}
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["articles"] == [{"title": "bài A"}]
    assert payload["social_posts"] == [{"content": "post B"}]
