/**
 * CompanyList — grid danh sách doanh nghiệp theo trạng thái tải.
 */
"use client";

import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconEmpty } from "@/components/common/Icon";
import { SkeletonGrid } from "@/components/common/Skeleton";
import { CompanyCard } from "@/components/companies/CompanyCard";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

export interface CompanyListProps {
  companies: CompanyResponse[];
  total: number;
  status: AsyncStatus;
  error: string | null;
  onRetry: () => void;
}

export function CompanyList({
  companies,
  total,
  status,
  error,
  onRetry,
}: CompanyListProps) {
  if (status === "loading") {
    return <SkeletonGrid count={6} />;
  }

  if (status === "error") {
    return <ErrorPanel error={error} onRetry={onRetry} />;
  }

  if (companies.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-ink-300 bg-white px-6 py-16 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ink-100 text-ink-400">
          <IconEmpty className="h-6 w-6" />
        </div>
        <h3 className="text-sm font-semibold text-ink-900">Không tìm thấy doanh nghiệp</h3>
        <p className="mt-1 text-sm text-ink-500">
          Hãy thử thay đổi từ khóa hoặc ngành khác.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {companies.map((company) => (
          <CompanyCard key={company.id} company={company} />
        ))}
      </div>
      <p className="mt-4 text-xs text-ink-400">
        Hiển thị {companies.length} / {total} công ty
      </p>
    </div>
  );
}
