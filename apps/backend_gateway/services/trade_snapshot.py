"""TradeSnapshotService — nguồn chân lý dữ liệu tài chính cho Mentor (Chế độ 3).

Theo docs/ai_mentor_3mode_plan.md v2.0 (mục 5.3.1): client KHÔNG gửi số liệu
tài chính (portfolio/cash/orders/giá/PNL) — do đó backend phải tự fetch từ DB
bằng ``user_id`` (đã xác thực qua JWT). Đây là lớp tách biệt để không bao giờ
tin payload client, tránh bị gửi giả để "lừa" mentor.

Chỉ những thứ server không biết tại thời điểm gõ (``selected_symbol``) được
nhận từ client, và vẫn được kiểm tra thuộc danh sách cổ phiếu hợp lệ.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class TradeSnapshot:
    """Snapshot danh mục - giá - lệnh của 1 user tại thời điểm hỏi mentor."""

    user_id: str
    selected_symbol: str | None = None
    cash_balance: Decimal | None = None
    total_nav: Decimal | None = None
    holdings: list[dict[str, Any]] = field(default_factory=list)
    open_orders: list[dict[str, Any]] = field(default_factory=list)
    current_price: Decimal | None = None
    # Dấu hiệu rủi ro tổng hợp (backend tính từ data thật để mentor phản biện).
    risk_flags: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        """Serialize snapshot thành văn bản đưa vào context prompt (grounding nguồn)."""
        lines: list[str] = []
        if self.cash_balance is not None:
            lines.append(f"- Tiền mặt khả dụng: {self.cash_balance:,.0f}")
        if self.total_nav is not None:
            lines.append(f"- Tổng giá trị danh mục (NAV): {self.total_nav:,.0f}")
        if self.selected_symbol and self.current_price is not None:
            lines.append(f"- Cổ phiếu đang chọn: {self.selected_symbol} (giá {self.current_price:,.2f})")
        if self.holdings:
            h_lines = []
            for h in self.holdings:
                alloc = h.get("allocation_pct")
                pnl = h.get("pnl_pct")
                h_lines.append(
                    f"  * {h.get('symbol')}: SL {h.get('quantity', 0):,.0f} cổ, "
                    f"giá TB {h.get('avg_price', 0):,.2f}, giá hiện tại {h.get('current_price', 0):,.2f}"
                    + (f", tỷ trọng {alloc:.1f}%" if alloc is not None else "")
                    + (f", lời/lỗ {pnl:+.1f}%" if pnl is not None else "")
                )
            lines.append("- Danh mục hiện tại:")
            lines.extend(h_lines)
        if self.open_orders:
            lines.append(f"- Đang có {len(self.open_orders)} lệnh chờ/hạn chế.")
        if self.risk_flags:
            lines.append(f"- Dấu hiệu rủi ro hệ thống nhận diện: {', '.join(self.risk_flags)}")
        return "\n".join(lines) if lines else "(không có dữ liệu danh mục)"


class TradeSnapshotService:
    """Fetch snapshot từ DB + price provider — nguồn chân lý, không tin client."""

    def __init__(self) -> None:
        self._symbol_cache: set[str] | None = None

    async def _valid_symbols(self, db: AsyncSession) -> set[str]:
        """Danh sách symbol hợp lệ của hệ thống (cache trong vòng đời service)."""
        if self._symbol_cache is not None:
            return self._symbol_cache
        from models.company import Company
        rows = (
            (await db.execute(select(Company.symbol).where(Company.is_active.is_(True))))
            .scalars().all()
        )
        self._symbol_cache = {str(s) for s in rows}
        return self._symbol_cache

    async def get_snapshot(
        self,
        db: AsyncSession,
        user_id: uuid.UUID | str,
        selected_symbol: str | None = None,
    ) -> TradeSnapshot:
        """Lấy snapshot đầy đủ từ DB. Không bao giờ nhận tiền/giá từ client."""
        # Validate symbol (nếu có) thuộc danh sách hợp lệ.
        valid_symbol = None
        if selected_symbol:
            syms = await self._valid_symbols(db)
            valid_symbol = selected_symbol if selected_symbol in syms else None
            if valid_symbol is None:
                logger.warning("selected_symbol không hợp lệ (bỏ qua): %s", selected_symbol)

        from models.company import Company
        from models.trade import Order, Portfolio
        from models.user import User

        user_uuid = uuid.UUID(str(user_id))
        # 1) Tiền mặt + tổng NAV.
        u = (await db.get(User, user_uuid))
        if u is None:
            return TradeSnapshot(user_id=str(user_id), selected_symbol=valid_symbol)

        total_nav = u.cash_balance + u.frozen_cash + u.settling_cash

        # 2) Danh mục (tỷ trọng, PNL, allot).
        pf_rows = (
            await db.execute(
                select(Portfolio, Company)
                .join(Company, Portfolio.company_id == Company.id)
                .where(Portfolio.user_id == user_uuid, Portfolio.quantity > 0)
            )
        ).all()
        holdings: list[dict[str, Any]] = []
        for pf, comp in pf_rows:
            mv = pf.quantity * comp.current_price
            cb = pf.quantity * pf.average_buy_price
            total_nav += mv
            alloc = (mv / total_nav * 100) if total_nav else Decimal("0")
            pnl = ((mv - cb) / cb * 100) if cb else Decimal("0")
            holdings.append({
                "symbol": comp.symbol,
                "quantity": pf.quantity,
                "avg_price": pf.average_buy_price,
                "current_price": comp.current_price,
                "market_value": mv,
                "allocation_pct": float(alloc),
                "pnl_pct": float(pnl),
            })

        # 3) Lệnh đang chờ/partial.
        order_rows = (
            await db.execute(
                select(Order, Company)
                .join(Company, Order.company_id == Company.id)
                .where(
                    Order.user_id == user_uuid,
                    Order.status.in_(("pending", "partially_filled")),
                )
                .order_by(Order.created_at.desc())
            )
        ).all()
        open_orders = [
            {
                "symbol": comp.symbol,
                "side": ord.side,
                "quantity": ord.quantity,
                "type": ord.type,
                "price": ord.price,
                "status": ord.status,
            }
            for ord, comp in order_rows
        ]

        # 4) Giá cổ phiếu đang chọn.
        current_price = None
        if valid_symbol:
            comp = (
                await db.execute(
                    select(Company).where(
                        Company.symbol == valid_symbol, Company.is_active.is_(True)
                    )
                )
            ).scalar_one_or_none()
            if comp is not None:
                current_price = comp.current_price
                # Bỏ symbol chọn nếu không sở hữu (chỉ đang xem, chưa có vị thế).
                has_position = any(h["symbol"] == valid_symbol for h in holdings)

        risk_flags = self._detect_risk_flags(holdings, open_orders, u)

        return TradeSnapshot(
            user_id=str(user_id),
            selected_symbol=valid_symbol,
            cash_balance=u.cash_balance,
            total_nav=total_nav,
            holdings=holdings,
            open_orders=open_orders,
            current_price=current_price,
            risk_flags=risk_flags,
        )

    @staticmethod
    def _detect_risk_flags(
        holdings: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        user: Any,
    ) -> list[str]:
        """Nhận diện nhanh các cờ rủi ro từ dữ liệu thật (deterministic, 0 token)."""
        flags: list[str] = []
        # Concentration: một mã chiếm > 40% NAV.
        for h in holdings:
            if h.get("allocation_pct", 0) > 40:
                flags.append("concentration")
                break
        # All-cash vs all-in: tiền mặt quá thấp so với NAV.
        cash = user.cash_balance or Decimal("0")
        if holdings:
            nav = cash + sum(h.get("market_value", 0) for h in holdings)
            if nav and (cash / nav) < Decimal("0.1"):
                flags.append("all_cash_low")
        # No stop-loss identification: có vị thế nhưng không lệnh giới hạn bảo vệ.
        if holdings and open_orders:
            sell_limits = [o for o in open_orders if o.get("side") == "sell"]
            if not sell_limits:
                flags.append("no_stop")
        # FOMO-ish: vị thế đang lãi lớn mà không có lệnh bảo vệ lợi nhuận.
        for h in holdings:
            if h.get("pnl_pct", 0) > 20 and not any(
                o.get("side") == "sell" for o in open_orders
            ):
                flags.append("fomo")
                break
        return flags


trade_snapshot_service = TradeSnapshotService()
