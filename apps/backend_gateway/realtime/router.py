"""Gắn các endpoint WebSocket vào ứng dụng FastAPI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from realtime.connection_manager import (
    SERVER_RESTART_CLOSE_CODE,
    ConnectionManager,
    connection_manager,
)
from realtime.mentor_ws import MentorStreamProvider
from realtime.price_ws import PriceBroadcaster
from realtime.trade_ws import TradeNotifier

WS_PATHS = {
    "prices": "/ws/prices",
    "trades": "/ws/trades",
    "mentor": "/ws/mentor",
}


def register_websocket_routes(
    app: FastAPI,
    *,
    manager: ConnectionManager | None = None,
    price_broadcaster: PriceBroadcaster | None = None,
    trade_notifier: TradeNotifier | None = None,
    mentor_provider: MentorStreamProvider | None = None,
) -> None:
    """Đăng ký cả 3 endpoint WebSocket (giá / khớp lệnh / mentor)."""
    from realtime import mentor_ws, price_ws, trade_ws

    app.add_websocket_route(
        WS_PATHS["prices"],
        price_ws.create_price_endpoint(manager, price_broadcaster),
    )
    app.add_websocket_route(
        WS_PATHS["trades"],
        trade_ws.create_trade_endpoint(manager, trade_notifier),
    )
    app.add_websocket_route(
        WS_PATHS["mentor"],
        mentor_ws.create_mentor_endpoint(manager, mentor_provider),
    )


async def start_ws_background(app: FastAPI) -> dict[str, Any]:
    """Khởi động task nền của WebSocket layer. Trả về handle để stop.

    Attach Backplane (Redis Pub/Sub) vào ConnectionManager trước khi start các
    broadcaster — từ đây mọi ``broadcast_to_room`` đi qua Redis để phát tán giữa
    các worker/replica, không chỉ trong RAM của process hiện tại.
    """
    from realtime import backplane, price_ws, trade_ws

    connection_manager.attach_backplane(backplane.backplane)
    await backplane.backplane.start()
    await price_ws.price_broadcaster.start()
    await trade_ws.trade_notifier.start()
    return {
        "price_broadcaster": price_ws.price_broadcaster,
        "trade_notifier": trade_ws.trade_notifier,
        "backplane": backplane.backplane,
    }


async def stop_ws_background(handles: dict[str, Any]) -> None:
    # 1) Tách backplane trước để việc đóng client không phát sinh sub/unsub Redis.
    connection_manager.detach_backplane()
    # 2) Đóng mọi kết nối với close code 1012 (Service Restart): client biết server
    #    đang rolling restart → reconnect có backoff + jitter, không Thundering Herd
    #    lên POST /auth/ws-ticket khi N worker khởi động lại cùng lúc.
    await connection_manager.shutdown_connections(
        code=SERVER_RESTART_CLOSE_CODE,
        reason="server restart — reconnect",
    )
    for name, component in handles.items():
        try:
            stop = getattr(component, "stop")
            if callable(stop):
                await stop()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to stop %s", name)
