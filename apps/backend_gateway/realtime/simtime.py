"""Công cụ thời gian mô phỏng (time compression) dùng cho luồng WebSocket.

Bản local mirror của `engine.time_compression.compressor` (math_engine) để tránh
phụ thuộc chéo giữa hai workspace apps. Quy ước: 1 phút thực = 1 ngày giao dịch ảo
(ratio = 1440).

HAI HỆ ĐỒNG HỒ — không được trộn:
- ``sim_now()`` / ``sim_now_epoch()``: mốc "HIỆN TẠI" của thế giới mô phỏng, dùng
  làm ranh giới chống look-ahead. Toàn bộ cột ``simulated_at`` trong DB được ghi
  bằng đồng hồ thực UTC, nên ranh giới as-of cũng phải là đồng hồ thực UTC —
  đây là chuẩn duy nhất cho mọi truy vấn đọc dữ liệu người dùng.
- ``format_sim_label()`` / ``real_to_sim_epoch()``: CHỈ dùng để hiển thị nhãn
  thời gian nén (1 phút thực = 1 ngày sim) trên UI/WS — không bao giờ so sánh
  với cột ``simulated_at`` trong DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

SIM_SECONDS_PER_DAY = 86400
DEFAULT_COMPRESSION_RATIO = 1440.0
DEFAULT_BASE_YEAR = 2026


def sim_now() -> datetime:
    """Thời điểm hiện tại của thế giới mô phỏng (UTC) — ranh giới as-of.

    Mọi bản ghi (news/social/order/transaction) ghi ``simulated_at`` bằng đồng hồ
    thực UTC nên hàm này trả về đồng hồ thực UTC. Không bao giờ dùng
    ``datetime.now()`` rải rác trong code — luôn gọi hàm này để có một nguồn
    thời gian duy nhất, dễ thay đổi sau này khi chuyển sang sim-clock thuần.
    """
    return datetime.now(timezone.utc)


def sim_now_epoch() -> float:
    """Epoch giây (thực UTC) của mốc hiện tại — tiện cho so sánh số học."""
    return sim_now().timestamp()


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
