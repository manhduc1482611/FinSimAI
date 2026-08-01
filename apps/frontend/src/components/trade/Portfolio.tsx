/**
 * Portfolio — bảng danh mục dạng terminal: tổng NAV/Cash/PnL + danh sách vị thế.
 *
 * Real-time: khi có `livePrices` (symbol → giá từ WS price_tick), giá trị thị
 * trường và PnL được tính theo giá live thay vì giá trong snapshot portfolio.
 */
"use client";

import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { Skeleton } from "@/components/common/Skeleton";
import { computeTotalUnrealizedPnl } from "@/utils/pnl";
import { formatCompactVND, formatNumber, formatQuantity, parseDecimal } from "@/utils/format";
import type { PortfolioListResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";
import { cn } from "@/utils/cn";

export interface PortfolioProps {
  portfolio: PortfolioListResponse | null;
  status: AsyncStatus;
  error: string | null;
  onRetry: () => void;
  /** Giá live theo symbol (từ WS prices) — dùng để tính giá trị theo thời gian thực. */
  livePrices?: ReadonlyMap<string, number>;
}

export function Portfolio({ portfolio, status, error, onRetry, livePrices }: PortfolioProps) {
  const items = portfolio?.items ?? [];
  const totalNav = portfolio !== null ? parseDecimal(portfolio.total_nav) : null;
  const totalCash = portfolio !== null ? parseDecimal(portfolio.total_cash) : null;
  const totalPnl = computeTotalUnrealizedPnl(items);

  const stats: Array<{ label: string; value: string; tone?: string }> = [
    {
      label: "NAV",
      value: totalNav !== null ? formatCompactVND(totalNav) : "—",
    },
    {
      label: "Tiền mặt",
      value: totalCash !== null ? formatCompactVND(totalCash) : "—",
    },
    {
      label: "Lãi/lỗ chưa hiện thực",
      value: items.length > 0 ? `${totalPnl >= 0 ? "+" : ""}${formatCompactVND(totalPnl)}` : "—",
      tone: items.length > 0 ? (totalPnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400") : undefined,
    },
    {
      label: "Vị thế",
      value: `${items.length} mã`,
    },
  ];

  return (
    <Card>
      <CardHeader
        title="Danh mục"
        description={livePrices !== undefined && livePrices.size > 0 ? "Giá trị cập nhật real-time" : undefined}
        action={
          <button
            type="button"
            className="text-xs font-medium text-brand-600 hover:underline disabled:cursor-wait disabled:opacity-50"
            onClick={onRetry}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Đang tải..." : "Làm mới"}
          </button>
        }
      />
      <CardBody className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-lg bg-ink-50 px-3 py-2.5 dark:bg-ink-900/60">
              <p className="text-[10px] uppercase tracking-wide text-ink-400 dark:text-ink-500">
                {stat.label}
              </p>
              <p className={cn("mt-0.5 text-sm font-bold text-ink-900 dark:text-ink-100", stat.tone)}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        {status === "loading" ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-2/3" />
          </div>
        ) : status === "error" ? (
          <p className="text-sm text-red-600 dark:text-red-400">
            {error ?? "Không tải được danh mục."}{" "}
            <button type="button" className="font-semibold underline" onClick={onRetry}>
              Thử lại
            </button>
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-dashed border-ink-300 py-8 text-center text-sm text-ink-500 dark:border-ink-700 dark:text-ink-400">
            Chưa có vị thế nào. Đặt lệnh mua để bắt đầu xây dựng danh mục.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-400 dark:border-ink-700 dark:text-ink-500">
                  <th className="px-2 py-2 font-semibold">Mã</th>
                  <th className="px-2 py-2 text-right font-semibold">KL</th>
                  <th className="px-2 py-2 text-right font-semibold">Giá vốn</th>
                  <th className="px-2 py-2 text-right font-semibold">Giá hiện tại</th>
                  <th className="px-2 py-2 text-right font-semibold">Giá trị</th>
                  <th className="px-2 py-2 text-right font-semibold">Lãi/lỗ</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const livePrice = livePrices?.get(item.symbol);
                  const effectivePrice = livePrice ?? parseDecimal(item.current_price);
                  const quantity = parseDecimal(item.quantity);
                  const averageBuy = parseDecimal(item.average_buy_price);
                  const marketValue = quantity * effectivePrice;
                  const costBasis = quantity * averageBuy;
                  const pnl = marketValue - costBasis;
                  const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
                  return (
                    <tr key={item.company_id} className="border-b border-ink-100 last:border-0 dark:border-ink-700">
                      <td className="px-2 py-3">
                        <p className="font-bold text-ink-900 dark:text-ink-100">{item.symbol}</p>
                        <p className="max-w-[10rem] truncate text-xs text-ink-400 dark:text-ink-500">
                          {item.company_name}
                        </p>
                      </td>
                      <td className="px-2 py-3 text-right text-ink-700 dark:text-ink-300">
                        {formatQuantity(quantity)}
                      </td>
                      <td className="px-2 py-3 text-right text-ink-700 dark:text-ink-300">
                        {formatNumber(averageBuy, 2)}
                      </td>
                      <td className="px-2 py-3 text-right text-ink-700 dark:text-ink-300">
                        {formatNumber(effectivePrice, 2)}
                        {livePrice !== undefined && (
                          <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-brand-500 align-middle" aria-label="Giá live" title="Giá real-time từ WebSocket" />
                        )}
                      </td>
                      <td className="px-2 py-3 text-right font-medium text-ink-900 dark:text-ink-100">
                        {formatNumber(marketValue, 2)}
                      </td>
                      <td className="px-2 py-3 text-right">
                        <span
                          className={cn(
                            "font-semibold",
                            pnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
                          )}
                        >
                          {pnl >= 0 ? "+" : ""}
                          {formatNumber(pnl, 2)}
                        </span>
                        <span className="ml-1 text-xs text-ink-400 dark:text-ink-500">
                          ({pnlPct >= 0 ? "+" : ""}
                          {formatNumber(pnlPct, 2)}%)
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
