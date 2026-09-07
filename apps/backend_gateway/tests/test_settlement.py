"""Test thanh toán T+2 — mốc giải phóng & logic tránh trùng (settlement)."""

from datetime import datetime, timezone
from decimal import Decimal

from core.config import settings
from services.settlement_service import settlement_deadline


def test_settlement_deadline_adds_settlement_days() -> None:
    sim = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    expected = datetime(2026, 1, 7, 12, 0, 0, tzinfo=timezone.utc)
    assert settlement_deadline(sim) == expected
    assert settings.settlement_days == 2


def test_settlement_deadline_naive_gets_utc() -> None:
    sim = datetime(2026, 1, 5, 12, 0, 0)  # naive
    result = settlement_deadline(sim)
    assert result.tzinfo is not None
    assert result == sim.replace(tzinfo=timezone.utc) + __import__(
        "datetime"
    ).timedelta(days=2)


def test_settlement_release_math_roundtrip() -> None:
    """Ròng về tay sau release = quantity × price − fee − tax (tái sử dụng công thức)."""
    qty = Decimal("100")
    price = Decimal("50")
    fee = Decimal("7.50")
    tax = Decimal("5.00")
    net = qty * price - fee - tax
    assert net == Decimal("4987.50")
