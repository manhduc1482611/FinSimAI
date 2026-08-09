/** Doanh nghiệp — bước 2 của hành trình: khám phá & phân tích cơ bản. */
"use client";

import { useCallback, useEffect, useState } from "react";

import { CompanyFilter, type CompanyFilters } from "@/components/companies/CompanyFilter";
import { CompanyList } from "@/components/companies/CompanyList";
import { CompanyMap } from "@/components/companies/CompanyMap";
import { PageHeader } from "@/components/common/PageHeader";
import { IconGrid, IconMap } from "@/components/common/Icon";
import { listCompanies } from "@/services/companies";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";
import { cn } from "@/utils/cn";

type CompanyView = "grid" | "map";

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<CompanyResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<CompanyFilters>({});
  const [view, setView] = useState<CompanyView>("grid");

  const load = useCallback(
    async (nextFilters: CompanyFilters) => {
      setStatus("loading");
      setError(null);
      try {
        const response = await listCompanies({
          sector: nextFilters.sector,
          search: nextFilters.search,
          limit: 60,
        });
        setCompanies(response.items);
        setTotal(response.total);
        setStatus("success");
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Không tải được danh sách doanh nghiệp");
      }
    },
    [],
  );

  useEffect(() => {
    void load(filters);
  }, [load, filters]);

  return (
    <div>
      <PageHeader
        title="Doanh nghiệp"
        description="Khám phá và so sánh sức khỏe tài chính của các công ty trong mô phỏng."
        actions={
          <div className="flex items-center gap-1 rounded-lg border border-line bg-[#FFFDF8] p-1 dark:border-granite-700 dark:bg-granite-900">
            <button
              type="button"
              onClick={() => setView("grid")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-bold transition-colors",
                view === "grid"
                  ? "bg-brand-500 text-granite-950 shadow-board"
                  : "text-ink-500 hover:bg-brand-500/10 dark:text-granite-400 dark:hover:bg-granite-800",
              )}
            >
              <IconGrid className="h-4 w-4" />
              Lưới
            </button>
            <button
              type="button"
              onClick={() => setView("map")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-bold transition-colors",
                view === "map"
                  ? "bg-brand-500 text-granite-950 shadow-board"
                  : "text-ink-500 hover:bg-brand-500/10 dark:text-granite-400 dark:hover:bg-granite-800",
              )}
            >
              <IconMap className="h-4 w-4" />
              Bản đồ
            </button>
          </div>
        }
      />
      <CompanyFilter
        value={filters}
        onChange={setFilters}
        onApply={() => void load(filters)}
        loading={status === "loading"}
      />
      {view === "grid" ? (
        <CompanyList
          companies={companies}
          total={total}
          status={status}
          error={error}
          onRetry={() => void load(filters)}
        />
      ) : (
        <CompanyMap companies={companies} />
      )}
    </div>
  );
}
