/**
 * Trade Terminal — trung tâm giao dịch: chọn mã, biểu đồ nến real-time,
 * sổ lệnh, đặt lệnh, danh mục cập nhật live và lịch sử lệnh.
 */
"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/common/Button";
import { IconChat } from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { OrderBook } from "@/components/trade/OrderBook";
import { OrderTable } from "@/components/trade/OrderTable";
import { Portfolio } from "@/components/trade/Portfolio";
import { TradePanel } from "@/components/trade/TradePanel";
import { PriceChart } from "@/components/companies/PriceChart";
import { MentorChat } from "@/components/mentor/MentorChat";
import { listCompanies } from "@/services/companies";
import { usePriceStream } from "@/hooks/usePriceStream";
import { useTrade } from "@/hooks/useTrade";
import { parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

export default function TradePage() {
  const trade = useTrade();

  const [companies, setCompanies] = useState<CompanyResponse[]>([]);
  const [companiesStatus, setCompaniesStatus] = useState<AsyncStatus>("idle");
  const [companiesError, setCompaniesError] = useState<string | null>(null);
const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  const loadCompanies = async () => {
    setCompaniesStatus("loading");
    setCompaniesError(null);
    try {
      const response = await listCompanies({ limit: 100 });
      setCompanies(response.items);
      setCompaniesStatus("success");
    } catch (error) {
      setCompaniesStatus("error");
      setCompaniesError(error instanceof Error ? error.message : "Không tải được danh sách công ty.");
    }
  };

  useEffect(() => {
    void loadCompanies();
  }, []);

  useEffect(() => {
    if (selectedSymbol === null && companies.length > 0) {
      setSelectedSymbol(companies[0].symbol);
    }
  }, [companies, selectedSymbol]);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.symbol === selectedSymbol) ?? null,
    [companies, selectedSymbol],
  );

  const priceStream = usePriceStream(selectedSymbol ?? "");

  const livePrices = useMemo(() => {
    if (priceStream.snapshot === null) {
      return new Map<string, number>();
    }
    return new Map<string, number>([[selectedSymbol ?? "", priceStream.snapshot.price]]);
  }, [priceStream.snapshot, selectedSymbol]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Bàn giao dịch"
        description="Biểu đồ nến real-time, sổ lệnh, đặt lệnh và danh mục — một quầy duy nhất."
        actions={
          <Button
            variant="secondary"
            onClick={() => {}}
            aria-label="Hỏi Mentor tài chính"
          >
            <IconChat className="h-4 w-4" />
            Hỏi Mentor
          </Button>
        }
      />

      {/* Thanh chọn mã */}
      <div className="flex flex-wrap items-center gap-2">
        {companiesStatus === "loading" && companies.length === 0 ? (
          <span className="text-sm text-ink-500 dark:text-granite-400">Đang tải danh sách công ty…</span>
        ) : companiesStatus === "error" ? (
          <span className="text-sm text-red-600 dark:text-red-400">
            {companiesError} —{" "}
            <button type="button" className="font-semibold underline" onClick={() => void loadCompanies()}>
              Thử lại
            </button>
          </span>
        ) : (
          <>
            <div className="flex flex-1 gap-2 overflow-x-auto pb-1">
              {companies.map((company) => {
                const active = company.symbol === selectedSymbol;
                return (
                  <button
                    key={company.id}
                    type="button"
                    onClick={() => setSelectedSymbol(company.symbol)}
                    className={cn(
                      "shrink-0 rounded-lg border px-3 py-1.5 text-left transition-colors",
                      active
                        ? "border-brand-500 bg-brand-500 text-granite-950 shadow-board"
                        : "border-ink-200 bg-[#FFFDF8] text-ink-700 hover:border-brand-500 hover:text-brand-700 dark:border-granite-700 dark:bg-granite-900 dark:text-granite-200 dark:hover:border-brand-400 dark:hover:text-brand-300",
                    )}
                  >
                    <span className="board-num text-sm font-black">{company.symbol}</span>
                    <span
                      className={cn(
                        "board-num ml-2 text-xs",
                        active ? "text-granite-900/80" : "text-ink-400 dark:text-granite-400",
                      )}
                    >
                      {formatCompactPrice(company.current_price)}
                    </span>
                  </button>
                );
              })}
            </div>
            {priceStream.snapshot !== null && (
              <span className="stamp stamp-success animate-flicker-on">
                <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-mkt-up" />
                Live
              </span>
            )}
          </>
        )}
      </div>

      {/* Chart + Order book */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {selectedCompany !== null && (
            <PriceChart
              symbol={selectedCompany.symbol}
              companyName={selectedCompany.name}
              snapshot={priceStream.snapshot}
              ticks={priceStream.ticks}
            />
          )}
        </div>
        <OrderBook symbol={selectedSymbol ?? ""} price={priceStream.snapshot?.price ?? null} />
      </div>

      {/* Panel đặt lệnh + Danh mục */}
      <div className="grid gap-4 lg:grid-cols-3">
        <TradePanel
          companies={companies}
          companiesLoading={companiesStatus === "loading"}
          companiesError={companiesError}
          companyId={selectedCompany?.id ?? undefined}
          onCompanyIdChange={(id) => {
            const company = companies.find((item) => item.id === id);
            if (company !== undefined) {
              setSelectedSymbol(company.symbol);
            }
          }}
        />
        <div className="lg:col-span-2">
          <Portfolio
            portfolio={trade.portfolio}
            status={trade.status}
            error={trade.error}
            onRetry={trade.refresh}
            livePrices={livePrices}
          />
        </div>
      </div>

      {/* Lịch sử lệnh */}
      <OrderTable
        orders={trade.orders}
        companies={companies}
        status={trade.status}
        error={trade.error}
        onRetry={trade.refresh}
        onCancel={(orderId) => void trade.cancelOrder(orderId)}
      />

      <MentorChat />
    </div>
  );
}

/** Hiển thị giá rút gọn cho chip chọn mã. */
function formatCompactPrice(value: string): string {
  const parsed = parseDecimal(value);
  if (parsed >= 1_000_000) {
    return `${(parsed / 1_000_000).toFixed(1)}tr`;
  }
  if (parsed >= 1_000) {
    return `${(parsed / 1_000).toFixed(1)}k`;
  }
  return parsed.toFixed(1);
}
