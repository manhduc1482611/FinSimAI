/**
 * CompanyCard — thẻ doanh nghiệp: giá, sức khỏe tài chính, P/E, ROE.
 */
import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";

import { formatCompactVND, formatNumber, parseDecimal } from "@/utils/format";
import { sectorLabel } from "@/utils/domain";

function healthTone(score: number): "success" | "warning" | "danger" {
  if (score >= 80) {
    return "success";
  }
  if (score >= 60) {
    return "warning";
  }
  return "danger";
}

export function CompanyCard({ company }: { company: CompanyResponse }) {
  const price = parseDecimal(company.current_price);
  const marketCap = parseDecimal(company.market_cap);

  return (
    <Link
      href={`/companies/${company.id}`}
      className="card group flex flex-col p-4 transition-shadow hover:shadow-md"
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-base font-bold text-ink-900 dark:text-slip">{company.symbol}</p>
          <p className="truncate text-xs text-ink-500">{company.name}</p>
        </div>
        <Badge variant={healthTone(company.health_score)}>
          Sức khỏe {company.health_score}
        </Badge>
      </div>

      <div className="mt-3 flex items-end justify-between border-t border-line pt-3">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-ink-400">Giá</p>
          <p className="text-lg font-bold text-ink-900 dark:text-slip board-num">
            {formatNumber(price, 2)}
            <span className="ml-1 text-xs font-normal text-ink-400">₫</span>
          </p>
        </div>
        <div className="text-right text-xs text-ink-500">
          <p>P/E {company.pe_ratio !== null ? formatNumber(parseDecimal(company.pe_ratio)) : "—"}</p>
          <p>
            ROE{" "}
            {company.roe !== null ? `${formatNumber(parseDecimal(company.roe))}%` : "—"}
          </p>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-ink-400">
        <span>{sectorLabel(company.sector)}</span>
        <span>Vốn hóa {marketCap > 0 ? formatCompactVND(marketCap) : "—"}</span>
      </div>
    </Link>
  );
}
