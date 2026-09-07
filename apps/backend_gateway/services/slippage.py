"""Mô hình trượt giá (slippage) & giới hạn thanh khoản khi khớp lệnh.

Lệnh lớn không khớp trọn ở một mức giá: giá fill xấu hơn ``market_price`` theo
``participation_ratio`` (khối lượng / độ sâu thanh khoản). Mua → giá cao hơn,
bán → giá thấp hơn, làm tròn theo tick size VN (0.01 cho giá toy < 1000; sau đó
10/50/100 cho các thang cao hơn — khớp với math engine).

Tất cả hàm ở đây là **thuần**, không đụng DB — dễ unit-test độc lập như
``_trade_costs``.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def vn_tick_size(price: Decimal) -> Decimal:
    """Tick size theo thang giá VN, khớp math engine ``_apply_vn_tick_size``.

    - giá < 1000: 0.01 (tick toy sim)
    - 1000 <= giá < 10000: 10
    - 10000 <= giá < 50000: 50
    - giá >= 50000: 100
    """
    p = Decimal(str(price))
    if p < Decimal("1000"):
        return Decimal("0.01")
    if p < Decimal("10000"):
        return Decimal("10")
    if p < Decimal("50000"):
        return Decimal("50")
    return Decimal("100")


def round_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Làm tròn giá về bội số nguyên lần tick (ROUND_HALF_UP)."""
    steps = (value / tick).quantize(Decimal("1"), ROUND_HALF_UP)
    return (steps * tick).quantize(_CENT)


def compute_fill_price(
    *,
    side: str,
    quantity: Decimal,
    market_price: Decimal,
    liquidity_depth: Decimal,
    impact_factor: Decimal | None = None,
) -> Decimal:
    """Giá fill đã tính slippage, làm tròn đúng tick size.

    ``impact_factor`` mặc định 0.5 (cấu hình) — tăng nếu cần độ nhạy thị trường.
    Nếu ``liquidity_depth <= 0`` hoặc ``quantity`` quá nhỏ, trả về giá thị trường
    (không trượt).
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"side phải là buy/sell, nhận: {side!r}")
    if quantity <= 0:
        raise ValueError("quantity phải > 0")

    market = Decimal(str(market_price))
    depth = Decimal(str(liquidity_depth))

    if depth <= 0:
        return market

    participation = Decimal(str(quantity)) / depth
    # Giới hạn tác động tối đa ±2% giá: Slippage mô phỏng này chỉ là chi phí
    # thực thi — không phản ánh biến động thị trường, nên giữ khiêm tốn để không
    # tạo fill giá phi lý. Lệnh nhỏ (tham gia thấp) gần như không trượt.
    participation = min(participation, Decimal("1"))
    k = Decimal(str(impact_factor if impact_factor is not None else Decimal("0.5")))
    impact = min(participation * k, Decimal("0.02"))

    direction = Decimal("1") if side == "buy" else Decimal("-1")
    raw = market * (Decimal("1") + direction * impact)
    tick = vn_tick_size(market)
    return round_to_tick(raw, tick)
