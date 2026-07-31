import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.config import settings


class RequestMetadataMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        raw_id = headers.get("X-Request-ID", "")
        try:
            uuid.UUID(raw_id)
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())
        else:
            request_id = raw_id

        start_time = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                m_headers = MutableHeaders(scope=message)
                m_headers["X-Request-ID"] = request_id
                m_headers["X-Process-Time"] = f"{time.perf_counter() - start_time:.4f}s"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_middleware(app: ASGIApp) -> None:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestMetadataMiddleware)
