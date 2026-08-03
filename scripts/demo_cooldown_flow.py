"""Demo luồng (Bước 5.1): vi phạm + bị phạt (cooldown) + khóa giao dịch + phát phạt.

Chạy:  uv run python scripts/demo_cooldown_flow.py
Không cần Postgres / Redis / math_engine — dùng FakeSession + giả lập gRPC.
"""

import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "demo-secret")
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "apps" / "backend_gateway")
)

from clients.math_client import math_client  # noqa: E402
from models.trade import Order  # noqa: E402
from models.trap import TrapEvent  # noqa: E402
from models.user import User  # noqa: E402
from services import penalty_service  # noqa: E402


def make_user(**overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "risk_score": 10,
        "cash_balance": Decimal("1000000.00"),
        "frozen_cash": Decimal("0.00"),
        "cooldown_until": None,
    }
    return User(**{**defaults, **overrides})


class FakeScalarResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        if not self._rows:
            raise ValueError("No row was found when one was required")
        return self._rows[0]

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeRow:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class FakeSession:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.trap_events: list[TrapEvent] = []
        self.orders: list[Order] = []
        self.added: list = []
        self.rolled_back = False

    def install(self, user: User) -> None:
        self.users[user.id] = user

    def add(self, obj) -> None:
        if isinstance(obj, TrapEvent):
            self.trap_events.append(obj)
        elif isinstance(obj, Order):
            self.orders.append(obj)
        self.added.append(obj)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self.rolled_back = True

    def _uuid_param(self, sql: str, column: str) -> uuid.UUID | None:
        match = re.search(rf"{column} = '([0-9a-fA-F-]+)'", sql)
        if not match:
            return None
        try:
            return uuid.UUID(match.group(1))
        except ValueError:
            return None

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        if "FROM users" in sql:
            user_id = self._uuid_param(sql, "users.id")
            user = self.users.get(user_id) if user_id else None
            if sql.lstrip().startswith("SELECT users.risk_score FROM"):
                rows = [FakeRow(risk_score=user.risk_score)] if user else []
            else:
                rows = [user] if user else []
            return FakeScalarResult(rows)

        if "FROM trap_events" in sql:
            user_id = self._uuid_param(sql, "trap_events.user_id")
            events = [
                e
                for e in self.trap_events
                if (user_id is None or e.user_id == user_id)
                and e.resolved_at is None
            ]
            events.sort(key=lambda e: e.detected_at, reverse=True)
            return FakeScalarResult(events)

        if "FROM orders" in sql:
            user_id = self._uuid_param(sql, "orders.user_id")
            rows = [
                o
                for o in self.orders
                if o.user_id == user_id
                and o.side == "buy"
                and o.status in ("pending", "partially_filled")
                and o.quantity > o.filled_quantity
            ]
            rows.sort(key=lambda o: o.created_at)
            return FakeScalarResult(rows)

        raise AssertionError(f"Unexpected statement: {sql}")


async def main() -> None:
    async def fake_check_penalty_status(risk_score: int, trap_severity: int):
        return {
            "success": True,
            "cooldown_seconds": 30.0,
            "risk_score_delta": trap_severity * 2,
            "points_deducted": 10_000,
            "new_risk_score": min(100, risk_score + trap_severity * 2),
        }

    setattr(math_client, "check_penalty_status", fake_check_penalty_status)

    db = FakeSession()
    user = make_user(risk_score=10)
    db.install(user)

    print("=" * 72)
    print("DEMO 5.1 — Vi phạm + Bị phạt (Cooldown) + Khóa giao dịch + Gửi phạt")
    print("=" * 72)

    print("\n[1] Tài khoản ban đầu")
    print(f"    risk_score = {user.risk_score}, cash = {user.cash_balance}")

    print("\n[2] Engine phát hiện vi phạm FOMO + POST /risk/penalties (severity=4)")
    result = await penalty_service.apply_penalty(
        user.id, 4, db, trap_type="fomo", description="Đặt lệnh đuổi giá"
    )
    print(f"    risk_score: 10 -> {result['new_risk_score']}")
    print(f"    cash: 1000000.00 -> {user.cash_balance}")
    print(f"    cooldown_until: {result['cooldown_until']}")
    print(f"    trap_event ghi nhận: {len(db.trap_events)} vi phạm")

    print("\n[3] Đặt lệnh ngay + enforce_cooldown (API sẽ trả HTTP 423)")
    lock = await penalty_service.enforce_cooldown(user.id, db)
    print(f"    locked = {lock['locked']}, remaining = {lock['remaining_seconds']}s")
    print(f"    reason = \"{lock['reason']}\"")

    print("\n[4] Cố gắng gửi phạt sớm + bị từ chối (không thả phạt thật ngắn)")
    early = await penalty_service.clear_cooldown(user.id, db)
    print(
        f"    cleared = {early['cleared']}, locked = {early['locked']}, "
        f"remaining = {early['remaining_seconds']}s"
    )

    print("\n[5] Giả lập: thời gian chờ 30s đã qua...")
    user.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)

    print("\n[6] POST /risk/cooldown/clear (nút 'Hoàn tất phân tích') + mở khóa")
    cleared = await penalty_service.clear_cooldown(user.id, db)
    print(f"    cleared = {cleared['cleared']}, locked = {cleared['locked']}")
    print(f"    trap resolved = {db.trap_events[0].resolved_at is not None}")

    print("\n[7] Đặt lệnh lại + enforce_cooldown trả None (được phép giao dịch)")
    allowed = await penalty_service.enforce_cooldown(user.id, db)
    print(f"    allowed = {allowed is None}")

    print("\n[8] Vi phạm lần 2 + quá hạn + GET /risk/cooldown tự lazy-clear (không cần nút)")
    await penalty_service.apply_penalty(
        user.id, 2, db, trap_type="panic", description="Cắt lỗ theo cảm xúc"
    )
    relock = await penalty_service.enforce_cooldown(user.id, db)
    print(f"    locked = {relock['locked']}, risk = {user.risk_score}")
    user.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    status = await penalty_service.get_penalty_status(user.id, db)
    print(f"    locked = {status['locked']}, cooldown_until = {status['cooldown_until']}")
    print(f"    trap resolved (lazy) = {db.trap_events[1].resolved_at is not None}")

    print("\nDONE — luồng khóa/mở khóa hoạt động đúng.")


if __name__ == "__main__":
    asyncio.run(main())
