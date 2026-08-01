"""Unit tests cho luồng phạt cooldown (Bước 5.1) — không cần Postgres thật.

Fake session thay thế ``AsyncSession``: chỉ đủ trả lời các query mà
``penalty_service`` thực sự phát ra (users / trap_events / orders), giúp kiểm
tra đúng nghiệp vụ khóa-mở-khóa mà không phụ thuộc DB.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from clients.math_grpc_client import math_grpc_client
from models.trade import Order
from models.trap import TrapEvent
from models.user import User
from services import penalty_service


def make_user(**overrides) -> User:
    defaults = {
        "id": uuid.uuid4(),
        "risk_score": 10,
        "cash_balance": Decimal("100000000.00"),
        "frozen_cash": Decimal("0.00"),
        "cooldown_until": None,
    }
    return User(**{**defaults, **overrides})


def make_order(**overrides) -> Order:
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "side": "buy",
        "type": "limit",
        "status": "pending",
        "price": Decimal("100.00"),
        "quantity": Decimal("100"),
        "filled_quantity": Decimal("0"),
        "frozen_cash": Decimal("10000.00"),
        "frozen_quantity": Decimal("0"),
    }
    return Order(**{**defaults, **overrides})


class FakeScalarResult:
    """Wrap danh sách row để giả lập ``Result`` / ``ScalarResult`` của SQLAlchemy."""

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
    """Row cho ``select(User.risk_score)`` — truy cập theo tên cột."""

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class FakeSession:
    """Fake ``AsyncSession`` — dispatch theo bảng xuất hiện trong SQL đã compile."""

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
        # SQL với literal_binds: `users.id = 'uuid'` / `trap_events.user_id = 'uuid'`
        import re

        match = re.search(rf"{column} = '([0-9a-fA-F-]+)'", sql)
        if not match:
            return None
        try:
            return uuid.UUID(match.group(1))
        except ValueError:
            return None

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        table = self._table_from_sql(sql)

        if table == "users":
            user_id = self._uuid_param(sql, "users.id")
            user = self.users.get(user_id) if user_id else None
            # `SELECT users.risk_score FROM ...` (projection 1 cột) → FakeRow;
            # `SELECT users.id, users.risk_score, ...` (entity đầy đủ) → User.
            if sql.lstrip().startswith("SELECT users.risk_score FROM"):
                rows = [FakeRow(risk_score=user.risk_score)] if user else []
            else:
                rows = [user] if user else []
            return FakeScalarResult(rows)

        if table == "trap_events":
            user_id = self._uuid_param(sql, "trap_events.user_id")
            events = [
                e
                for e in self.trap_events
                if (user_id is None or e.user_id == user_id) and e.resolved_at is None
            ]
            events.sort(key=lambda e: e.detected_at, reverse=True)
            return FakeScalarResult(events)

        if table == "orders":
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

        raise AssertionError(f"Unexpected statement for table: {sql}")

    @staticmethod
    def _table_from_sql(sql: str) -> str | None:
        if "FROM users" in sql:
            return "users"
        if "FROM trap_events" in sql:
            return "trap_events"
        if "FROM orders" in sql:
            return "orders"
        return None


def _patch_math(monkeypatch: pytest.MonkeyPatch, *, cooldown_seconds: float = 0.0):
    async def fake_check_penalty_status(risk_score: int, trap_severity: int):
        return {
            "cooldown_seconds": cooldown_seconds,
            "risk_score_delta": trap_severity,
            "points_deducted": 0,
            "new_risk_score": min(100, risk_score + trap_severity),
            "success": True,
        }

    monkeypatch.setattr(
        math_grpc_client, "check_penalty_status", fake_check_penalty_status
    )


# ─── get_penalty_status ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_unlocked_when_no_cooldown() -> None:
    db = FakeSession()
    user = make_user()
    db.install(user)

    status = await penalty_service.get_penalty_status(user.id, db)

    assert status["success"] is True
    assert status["locked"] is False
    assert status["remaining_seconds"] == 0
    assert status["cooldown_until"] is None
    assert status["risk_score"] == user.risk_score


@pytest.mark.asyncio
async def test_status_locked_returns_remaining_and_reason() -> None:
    db = FakeSession()
    user = make_user(
        risk_score=55,
        cooldown_until=datetime.now(timezone.utc) + timedelta(seconds=300),
    )
    db.install(user)
    db.add(
        TrapEvent(
            user_id=user.id,
            type="fomo",
            severity=4,
            description="Đặt lệnh đu đỉnh",
            points_deducted=50,
            detected_at=datetime.now(timezone.utc),
            simulated_at=datetime.now(timezone.utc),
        )
    )

    status = await penalty_service.get_penalty_status(user.id, db)

    assert status["locked"] is True
    assert 0 < status["remaining_seconds"] <= 300
    assert status["risk_score"] == 55
    assert status["reason"] is not None
    assert "fomo" in status["reason"]


@pytest.mark.asyncio
async def test_status_lazy_clears_expired_cooldown() -> None:
    db = FakeSession()
    user = make_user(cooldown_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    db.install(user)

    status = await penalty_service.get_penalty_status(user.id, db)

    assert status["locked"] is False
    assert status["cooldown_until"] is None
    assert user.cooldown_until is None  # đã được gỡ


@pytest.mark.asyncio
async def test_status_user_not_found() -> None:
    db = FakeSession()
    status = await penalty_service.get_penalty_status(uuid.uuid4(), db)
    assert status["success"] is False


# ─── enforce_cooldown ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enforce_cooldown_allows_when_unlocked() -> None:
    db = FakeSession()
    user = make_user()
    db.install(user)
    assert await penalty_service.enforce_cooldown(user.id, db) is None


@pytest.mark.asyncio
async def test_enforce_cooldown_blocks_when_locked() -> None:
    db = FakeSession()
    user = make_user(cooldown_until=datetime.now(timezone.utc) + timedelta(seconds=60))
    db.install(user)

    lock = await penalty_service.enforce_cooldown(user.id, db)

    assert lock is not None
    assert lock["locked"] is True
    assert lock["remaining_seconds"] > 0


# ─── apply_penalty ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_penalty_sets_risk_and_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_math(monkeypatch, cooldown_seconds=30.0)
    db = FakeSession()
    user = make_user(risk_score=20)
    db.install(user)

    result = await penalty_service.apply_penalty(
        user.id, 4, db, trap_type="panic", description="Cắt lỗ theo cảm xúc"
    )

    assert result["success"] is True
    assert result["new_risk_score"] == 24
    assert user.risk_score == 24
    assert user.cooldown_until is not None
    assert result["cooldown_until"] is not None
    assert len(db.trap_events) == 1
    assert db.trap_events[0].type == "panic"
    assert db.trap_events[0].points_deducted == 0


@pytest.mark.asyncio
async def test_apply_penalty_math_failure_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_failure(risk_score: int, trap_severity: int):
        return {"success": False, "cooldown_seconds": 0.0, "new_risk_score": risk_score}

    monkeypatch.setattr(math_grpc_client, "check_penalty_status", fake_failure)
    db = FakeSession()
    user = make_user()
    db.install(user)

    result = await penalty_service.apply_penalty(user.id, 3, db)

    assert result["success"] is False
    assert user.cooldown_until is None
    assert len(db.trap_events) == 0


@pytest.mark.asyncio
async def test_apply_penalty_cancels_pending_orders_to_cover_deduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_check(risk_score: int, trap_severity: int):
        return {
            "cooldown_seconds": 30.0,
            "risk_score_delta": 20,
            "points_deducted": 200,
            "new_risk_score": min(100, risk_score + 20),
            "success": True,
        }

    monkeypatch.setattr(math_grpc_client, "check_penalty_status", fake_check)
    db = FakeSession()
    user = make_user(
        risk_score=30,
        cash_balance=Decimal("100.00"),
        frozen_cash=Decimal("110.00"),
    )
    db.install(user)
    now = datetime.now(timezone.utc)
    db.add(
        make_order(
            user_id=user.id,
            price=Decimal("10.00"),
            quantity=Decimal("10"),
            frozen_cash=Decimal("80.00"),
            created_at=now,
        )
    )
    db.add(
        make_order(
            user_id=user.id,
            price=Decimal("10.00"),
            quantity=Decimal("10"),
            frozen_cash=Decimal("30.00"),
            created_at=now + timedelta(seconds=1),
        )
    )

    result = await penalty_service.apply_penalty(user.id, 5, db)

    assert result["success"] is True
    assert user.cash_balance == Decimal("0.00")  # 100 + 80 + 20 - 200
    assert user.frozen_cash == Decimal("10.00")  # 110 - 80 (cancel) - 20 (partial)
    assert db.orders[0].status == "cancelled"
    assert db.orders[1].frozen_cash == Decimal("10.00")  # 30 - 20
    assert db.rolled_back is False


@pytest.mark.asyncio
async def test_apply_penalty_rolls_back_when_short(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(risk_score: int, trap_severity: int):
        return {
            "cooldown_seconds": 30.0,
            "risk_score_delta": 20,
            "points_deducted": 500,
            "new_risk_score": min(100, risk_score + 20),
            "success": True,
        }

    monkeypatch.setattr(math_grpc_client, "check_penalty_status", fake_check)
    db = FakeSession()
    user = make_user(cash_balance=Decimal("100.00"))
    db.install(user)

    result = await penalty_service.apply_penalty(user.id, 5, db)

    assert result["success"] is False
    assert db.rolled_back is True
    assert len(db.trap_events) == 0


# ─── clear_cooldown ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_cooldown_cannot_shorten_penalty() -> None:
    db = FakeSession()
    user = make_user(cooldown_until=datetime.now(timezone.utc) + timedelta(seconds=120))
    db.install(user)

    result = await penalty_service.clear_cooldown(user.id, db)

    assert result["locked"] is True
    assert result["cleared"] is False
    assert user.cooldown_until is not None  # chưa được gỡ


@pytest.mark.asyncio
async def test_clear_cooldown_after_expiry_resolves_traps() -> None:
    db = FakeSession()
    user = make_user(cooldown_until=datetime.now(timezone.utc) - timedelta(seconds=1))
    db.install(user)
    event = TrapEvent(
        user_id=user.id,
        type="fomo",
        severity=3,
        points_deducted=25,
        detected_at=datetime.now(timezone.utc),
        simulated_at=datetime.now(timezone.utc),
    )
    db.add(event)

    result = await penalty_service.clear_cooldown(user.id, db)

    assert result["success"] is True
    assert result["cleared"] is True
    assert result["locked"] is False
    assert user.cooldown_until is None
    assert event.resolved_at is not None


@pytest.mark.asyncio
async def test_clear_cooldown_noop_when_never_locked() -> None:
    db = FakeSession()
    user = make_user()
    db.install(user)

    result = await penalty_service.clear_cooldown(user.id, db)

    assert result["success"] is True
    assert result["cleared"] is False
    assert result["locked"] is False


# ─── helper: reason ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reason_falls_back_when_no_trap_event() -> None:
    db = FakeSession()
    user = make_user()
    db.install(user)
    assert await penalty_service._penalty_reason(user.id, db) is not None
