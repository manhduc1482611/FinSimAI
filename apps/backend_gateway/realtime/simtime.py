"""Công cụ thời gian mô phỏng (time compression) dùng cho luồng WebSocket.

Bản local mirror của `engine.time_compression.compressor` (math_engine) để tránh
phụ thuộc chéo giữa hai workspace apps. Quy ước: 1 phút thực = 1 ngày giao dịch ảo
(ratio = 1440).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

SIM_SECONDS_PER_DAY = 86400
DEFAULT_COMPRESSION_RATIO = 1440.0
DEFAULT_BASE_YEAR = 2026


def real_to_sim_epoch(
    now: datetime,
    anchor: datetime,
    ratio: float = DEFAULT_COMPRESSION_RATIO,
) -> float:
    """Quy đổi thời gian thực (real) sang giây mô phỏng (sim epoch)."""
    elapsed = (now - anchor).total_seconds()
    return max(elapsed, 0.0) * ratio


def sim_day_of(sim_epoch: float) -> int:
    return int(sim_epoch // SIM_SECONDS_PER_DAY)


def format_sim_label(
    sim_epoch: float,
    base_year: int = DEFAULT_BASE_YEAR,
    include_time: bool = True,
) -> str:
    """Định dạng mốc mô phỏng dạng ``YYYY-MM-DD HH:MM:SS (Sim Day N)``."""
    sim_epoch = max(sim_epoch, 0.0)
    start_date = datetime(base_year, 1, 1, tzinfo=timezone.utc)
    sim_dt = start_date + timedelta(seconds=sim_epoch)
    sim_day = int(sim_epoch // SIM_SECONDS_PER_DAY)

    if include_time:
        formatted_dt = sim_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        formatted_dt = sim_dt.strftime("%Y-%m-%d")

    return f"{formatted_dt} (Sim Day {sim_day})"
