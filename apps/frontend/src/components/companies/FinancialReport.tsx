/**
 * FinancialReport — báo cáo tài chính cơ bản của công ty: PE, ROE, biên lợi
 * nhuận ròng, vốn hóa, khối lượng cổ phiếu lưu hành, độ biến động.
 */
"use client";

import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { IconBook } from "@/components/common/Icon";
import { formatCompactVND, formatNumber, parseDecimal } from "@/utils/format";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import { cn } from "@/utils/cn";

export interface FinancialReportProps {
  company: CompanyResponse;
}

/** Màu cho metric tỷ suất: giá trị dương → xanh, âm → đỏ. */
function rateColor(value: number): string {
  if (value >= 0) {
    return "text-mkt-up dark:text-mkt-up-400";
  }
  return "text-mkt-down dark:text-mkt-down-400";
}

function MetricBar({ value, max }: { value: number; max: number }) {
  const pct = Math.max(0, Math.min(100, (Math.abs(value) / max) * 100));
  const positive = value >= 0;
  return (
    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
      <div
        className={cn(
          "h-full rounded-full",
          positive ? "bg-mkt-up" : "bg-mkt-down",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function FinancialReport({ company }: FinancialReportProps) {
  const peRatio = company.pe_ratio !== null ? parseDecimal(company.pe_ratio) : null;
  const roe = company.roe !== null ? parseDecimal(company.roe) : null;
  const netMargin = company.net_margin !== null ? parseDecimal(company.net_margin) : null;
  const marketCap = company.market_cap !== null ? parseDecimal(company.market_cap) : null;
  const sharesOutstanding = parseDecimal(company.shares_outstanding);
  const volatility = parseDecimal(company.volatility);

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <IconBook className="h-4 w-4 text-ink-400" />
            Báo cáo tài chính
          </span>
        }
        description="Số liệu mô phỏng cho mục đích học tập"
      />
      <CardBody className="space-y-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <div>
            <p className="text-xs text-ink-500 dark:text-granite-400">P/E ratio</p>
            <p className="mt-0.5 text-sm font-bold text-ink-900 dark:text-slip board-num">
              {peRatio !== null ? formatNumber(peRatio, 2) : "—"}
            </p>
            <MetricBar value={peRatio ?? 0} max={50} />
          </div>

          <div>
            <p className="text-xs text-ink-500 dark:text-granite-400">ROE (%)</p>
            <p className={cn("mt-0.5 text-sm font-bold board-num", rateColor(roe ?? 0))}>
              {roe !== null ? `${roe >= 0 ? "+" : ""}${formatNumber(roe, 1)}%` : "—"}
            </p>
            <MetricBar value={roe ?? 0} max={50} />
          </div>

          <div>
            <p className="text-xs text-ink-500 dark:text-granite-400">Biên lợi nhuận ròng (%)</p>
            <p className={cn("mt-0.5 text-sm font-bold board-num", rateColor(netMargin ?? 0))}>
              {netMargin !== null
                ? `${netMargin >= 0 ? "+" : ""}${formatNumber(netMargin, 1)}%`
                : "—"}
            </p>
            <MetricBar value={netMargin ?? 0} max={50} />
          </div>

          <div>
            <p className="text-xs text-ink-500 dark:text-granite-400">Độ biến động (%)</p>
            <p className="mt-0.5 text-sm font-bold text-ink-900 dark:text-slip board-num">
              {formatNumber(volatility, 1)}%
            </p>
            <MetricBar value={volatility} max={50} />
          </div>
        </div>

        <div className="space-y-2 border-t border-line pt-3 dark:border-granite-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-500 dark:text-granite-400">Vốn hóa thị trường</span>
            <span className="font-semibold text-ink-900 dark:text-slip board-num">
              {marketCap !== null ? formatCompactVND(marketCap) : "—"}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-500 dark:text-granite-400">Cổ phiếu lưu hành</span>
            <span className="font-semibold text-ink-900 dark:text-slip board-num">
              {formatNumber(sharesOutstanding)} cổ phiếu
            </span>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
