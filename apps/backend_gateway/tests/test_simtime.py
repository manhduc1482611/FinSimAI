from datetime import datetime, timedelta, timezone

import pytest
from websockets.simtime import (
    DEFAULT_COMPRESSION_RATIO,
    SIM_SECONDS_PER_DAY,
    format_sim_label,
    real_to_sim_epoch,
    sim_day_of,
)

ANCHOR = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_epoch_zero_at_anchor() -> None:
    assert real_to_sim_epoch(ANCHOR, ANCHOR) == 0.0


def test_epoch_scales_by_ratio() -> None:
    one_minute = ANCHOR + timedelta(minutes=1)
    assert real_to_sim_epoch(one_minute, ANCHOR) == 60.0 * DEFAULT_COMPRESSION_RATIO
    assert real_to_sim_epoch(one_minute, ANCHOR) == SIM_SECONDS_PER_DAY


def test_epoch_never_negative() -> None:
    assert real_to_sim_epoch(ANCHOR - timedelta(hours=5), ANCHOR) == 0.0


def test_sim_day_boundaries() -> None:
    assert sim_day_of(0) == 0
    assert sim_day_of(SIM_SECONDS_PER_DAY - 1) == 0
    assert sim_day_of(SIM_SECONDS_PER_DAY) == 1
    assert sim_day_of(2.5 * SIM_SECONDS_PER_DAY) == 2


def test_format_sim_label() -> None:
    label = format_sim_label(0)
    assert label == "2026-01-01 00:00:00 (Sim Day 0)"

    label = format_sim_label(SIM_SECONDS_PER_DAY + 3600)
    assert label == "2026-01-02 01:00:00 (Sim Day 1)"

    assert format_sim_label(0, include_time=False) == "2026-01-01 (Sim Day 0)"


def test_format_sim_label_clamps_negative() -> None:
    assert format_sim_label(-100) == "2026-01-01 00:00:00 (Sim Day 0)"


def test_epoch_is_absolute_not_accumulated() -> None:
    """Sim epoch là hàm thuần của (now - anchor), KHÔNG tích lũy theo số lần gọi.

    Bảo vệ chống "timer cộng dồn": tỉ lệ 1:1440 nghĩa là 100ms trễ thực = 2.4 phút
    sim — nếu tick bị trễ do load, một timer cộng dồn sẽ càng ngày càng lệch. Hàm
    này tính lại tuyệt đối từ wall-clock mỗi lần nên trễ tick không tích lũy.
    """
    now = ANCHOR + timedelta(minutes=1)
    expected = 60.0 * DEFAULT_COMPRESSION_RATIO

    assert real_to_sim_epoch(now, ANCHOR) == expected
    # Gọi lặp lại với cùng mốc thực → kết quả không đổi (không có trạng thái tích lũy).
    assert real_to_sim_epoch(now, ANCHOR) == expected
    assert real_to_sim_epoch(now, ANCHOR) == expected

    # Tick trễ 100ms thực → sim lệch đúng 100ms * ratio so với đúng giờ,
    # KHÔNG cộng dồn sai số từ các lượt trước.
    on_time = real_to_sim_epoch(now, ANCHOR)
    late = real_to_sim_epoch(now + timedelta(milliseconds=100), ANCHOR)
    assert late - on_time == pytest.approx(0.1 * DEFAULT_COMPRESSION_RATIO)

