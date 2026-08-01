/**
 * NewsFilter — bộ lọc danh mục + sentiment; đổi giá trị → tự tải lại danh sách.
 */
"use client";

import { IconRefresh } from "@/components/common/Icon";
import { SelectField } from "@/components/common/Field";
import { useNewsStore } from "@/store/useNewsStore";
import { NEWS_CATEGORIES } from "@/utils/domain";
import { cn } from "@/utils/cn";

export function NewsFilter() {
  const filters = useNewsStore((state) => state.filters);
  const setFilters = useNewsStore((state) => state.setFilters);
  const fetchNews = useNewsStore((state) => state.fetchNews);
  const status = useNewsStore((state) => state.status);

  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="grid flex-1 grid-cols-1 gap-3 sm:max-w-md sm:grid-cols-2">
        <SelectField
          label="Danh mục"
          value={filters.category ?? ""}
          onChange={(event) => setFilters({ category: event.target.value || undefined })}
        >
          <option value="">Tất cả</option>
          {NEWS_CATEGORIES.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </SelectField>

        <SelectField
          label="Cảm xúc"
          value={filters.sentiment ?? ""}
          onChange={(event) => setFilters({ sentiment: event.target.value || undefined })}
        >
          <option value="">Tất cả</option>
          <option value="positive">Tích cực</option>
          <option value="neutral">Trung lập</option>
          <option value="negative">Tiêu cực</option>
        </SelectField>
      </div>

      <button
        type="button"
        className={cn(
          "btn-secondary mt-auto px-3 py-2 text-xs",
          status === "loading" && "cursor-wait opacity-60",
        )}
        onClick={() => void fetchNews()}
        disabled={status === "loading"}
      >
        <IconRefresh className={cn("h-4 w-4", status === "loading" && "animate-spin")} />
        Làm mới
      </button>
    </div>
  );
}
