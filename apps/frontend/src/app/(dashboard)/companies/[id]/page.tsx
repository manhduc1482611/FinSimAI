/** Chi tiết doanh nghiệp — sức khỏe tài chính, chỉ số định giá và hành động. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card, CardBody } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
import { Spinner } from "@/components/common/Spinner";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { FinancialReport } from "@/components/companies/FinancialReport";
import { HealthScore } from "@/components/companies/HealthScore";
import { getCompany } from "@/services/companies";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";
import { formatCompactVND, formatNumber, parseDecimal } from "@/utils/format";
import { sectorLabel } from "@/utils/domain";

export default function CompanyDetailPage({ params }: { params: { id: string } }) {
  const [company, setCompany] = useState<CompanyResponse | null>(null);
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setStatus("loading");
    setError(null);
    try {
      setCompany(await getCompany(params.id));
      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Không tải được doanh nghiệp");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  if (status === "loading" && company === null) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (status === "error" || company === null) {
    return <ErrorPanel error={error} onRetry={() => void load()} />;
  }

  const price = parseDecimal(company.current_price);
  const marketCap = company.market_cap !== null ? parseDecimal(company.market_cap) : null;

  return (
    <div className="mx-auto max-w-5xl">
      <nav className="mb-4 text-sm text-ink-500">
        <Link href="/companies" className="hover:text-brand-700 dark:hover:text-brand-300">
          ← Doanh nghiệp
        </Link>
      </nav>

      <Card>
        <CardBody className="px-6 py-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-ink-900 dark:text-slip">{company.symbol}</h1>
              <p className="mt-1 text-sm text-ink-500 dark:text-granite-400">{company.name}</p>
              <p className="text-xs text-ink-400 dark:text-granite-400">{sectorLabel(company.sector)}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-3xl font-bold text-ink-900 dark:text-slip board-num">
                {formatNumber(price, 2)}
                <span className="ml-1 text-sm font-normal text-ink-400 dark:text-granite-400">₫</span>
              </p>
              <p className="text-xs text-ink-400 dark:text-granite-400">
                Vốn hóa {marketCap !== null ? formatCompactVND(marketCap) : "—"}
              </p>
            </div>
          </div>

          {company.description !== null && (
            <p className="mt-4 text-sm leading-relaxed text-ink-700 dark:text-granite-300">
              {company.description}
            </p>
          )}
        </CardBody>
      </Card>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <HealthScore score={company.health_score} />
        </div>
        <div className="lg:col-span-2">
          <FinancialReport company={company} />
        </div>
      </div>

      <Card className="mt-6">
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ink-900 dark:text-slip">Giao dịch nhanh</h3>
            <p className="text-sm text-ink-500 dark:text-granite-400">
              Đặt lệnh mua/bán {company.symbol} tại mức giá {formatNumber(price, 2)} ₫
            </p>
          </div>
          <Link href="/trade">
            <Button size="sm">Mở bàn giao dịch</Button>
          </Link>
        </CardBody>
      </Card>
    </div>
  );
}
