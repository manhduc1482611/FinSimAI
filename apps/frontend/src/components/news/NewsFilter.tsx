/**
 * NewsFilter — ô tìm kiếm debounce + bộ lọc danh mục + sentiment; đổi giá trị → tải lại danh sách.
 */
"use client";

import { useEffect, useState } from "react";

import { IconRefresh, IconSearch } from "@/components/common/Icon";
import { SelectField, TextField } from "@/components/common/Field";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useNewsStore } from "@/store/useNewsStore";
import { NEWS_CATEGORIES } from "@/utils/domain";
import { cn } from "@/utils/cn";

export function NewsFilter() {
  const filters = useNewsStore((state) => state.filters);
  const setFilters = useNewsStore((state) => state.setFilters);
  const fetchNews = useNewsStore((state) => state.fetchNews);
  const status = useNewsStore((state) => state.status);
  const [searchInput, setSearchInput] = useState(filters.q ?? "");
  const debouncedQ = useDebouncedValue(searchInput);

  // Đồng bộ debounce → store (chỉ khi giá trị thay đổi).
  useEffect(() => {
    if (debouncedQ !== (filters.q ?? "")) {
      setFilters({ q: debouncedQ || undefined });
    }
  }, [debouncedQ, filters.q, setFilters]);

  return (
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <TextField
          label="Tìm tin"
          placeholder="Tiêu đề, nội dung…"
          icon={<IconSearch className="h-4 w-4" />}
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          size="sm"
          className="sm:max-w-xs"
        />
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
    </div>
  );
}