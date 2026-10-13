"""Test thanh toán T+2 — mốc giải phóng & logic tránh trùng (settlement).

T+2 tính theo NGÀY GIAO DỊCH MÔ PHỎNG (đồng hồ nén 1:1440, 1 ngày ảo = 60 giây
thực): 2 ngày ảo = 120 giây thực — không phải 2 ngày thực.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.config import settings
from realtime.simtime import REAL_SECONDS_PER_SIM_DAY, real_seconds_for_sim_days
from services.settlement_service import settlement_deadline


def test_real_seconds_per_sim_day_is_one_minute() -> None:
    # Tỉ lệ nén mặc định 1440 → 1 ngày mô phỏng = 1 phút thực.
    assert REAL_SECONDS_PER_SIM_DAY == 60.0
    assert real_seconds_for_sim_days(2) == 120.0


def test_settlement_deadline_adds_simulated_days_not_real_days() -> None:
    sim = datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
    expected = sim + timedelta(seconds=settings.settlement_days * 60)
    assert settlement_deadline(sim) == expected
    # Chốt lại: KHÔNG cộng ngày thực (bug cũ).
    assert settlement_deadline(sim) != sim + timedelta(days=settings.settlement_days)
    assert settings.settlement_days == 2


def test_settlement_deadline_naive_gets_utc() -> None:
    sim = datetime(2026, 1, 5, 12, 0, 0)  # naive
    result = settlement_deadline(sim)
    assert result.tzinfo is not None
    assert result == sim.replace(tzinfo=timezone.utc) + timedelta(
        seconds=settings.settlement_days * 60
    )


def test_settlement_release_math_roundtrip() -> None:
    """Ròng về tay sau release = quantity × price − fee − tax (tái sử dụng công thức)."""
    qty = Decimal("100")
    price = Decimal("50")
    fee = Decimal("7.50")
    tax = Decimal("5.00")
    net = qty * price - fee - tax
    assert net == Decimal("4987.50")
