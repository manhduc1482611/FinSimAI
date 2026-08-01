/**
 * Tính toán PnL phía client dùng cho bảng danh mục (Portfolio).
 * Mọi số liệu từ API đều là Decimal dạng string → parse trước khi tính.
 */
import type { PortfolioResponse } from "@finsim/shared-types/generated/api-types";

import { parseDecimal } from "@/utils/format";

export interface PositionPnl {
  /** Giá vốn = quantity × average_buy_price */
  costBasis: number;
  /** Giá trị thị trường = quantity × current_price */
  marketValue: number;
  /** Lãi/lỗ chưa thực hiện = marketValue - costBasis */
  pnl: number;
  /** Tỷ lệ so với giá vốn (%), giữ nguyên dấu */
  pnlPct: number;
}

/** Tính PnL cho một vị thế trong danh mục. */
export function computePositionPnl(item: PortfolioResponse): PositionPnl {
  const quantity = parseDecimal(item.quantity);
  const averageBuyPrice = parseDecimal(item.average_buy_price);
  const currentPrice = parseDecimal(item.current_price);

  const costBasis = quantity * averageBuyPrice;
  const marketValue = quantity * currentPrice;
  const pnl = marketValue - costBasis;
  const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;

  return { costBasis, marketValue, pnl, pnlPct };
}

/** Tổng lãi/lỗ chưa thực hiện của toàn danh mục. */
export function computeTotalUnrealizedPnl(
  items: PortfolioResponse[],
): number {
  return items.reduce(
    (total, item) => total + computePositionPnl(item).pnl,
    0,
  );
}
