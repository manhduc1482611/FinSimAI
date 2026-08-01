/**
 * CompanyFilter — lọc theo ngành + tìm kiếm theo mã/tên; tự reload khi thay đổi.
 */
"use client";

import { useEffect, useState } from "react";

import { IconSearch } from "@/components/common/Icon";
import { SelectField, TextField } from "@/components/common/Field";
import { COMPANY_SECTORS } from "@/utils/domain";

export interface CompanyFilters {
  sector?: string;
  search?: string;
}

export interface CompanyFilterProps {
  value: CompanyFilters;
  onChange: (next: CompanyFilters) => void;
  onApply: () => void;
  loading?: boolean;
}

export function CompanyFilter({ value, onChange, onApply, loading = false }: CompanyFilterProps) {
  const [searchDraft, setSearchDraft] = useState(value.search ?? "");

  useEffect(() => {
    setSearchDraft(value.search ?? "");
  }, [value.search]);

  const submitSearch = () => {
    onChange({ ...value, search: searchDraft.trim() || undefined });
    onApply();
  };

  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end">
      <div className="grid flex-1 grid-cols-1 gap-3 sm:max-w-lg sm:grid-cols-[1fr_220px]">
        <TextField
          label="Tìm kiếm"
          placeholder="Mã hoặc tên công ty..."
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              submitSearch();
            }
          }}
          icon={<IconSearch className="h-4 w-4" />}
        />
        <SelectField
          label="Ngành"
          value={value.sector ?? ""}
          onChange={(event) => {
            onChange({ ...value, sector: event.target.value || undefined });
            onApply();
          }}
        >
          <option value="">Tất cả ngành</option>
          {COMPANY_SECTORS.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </SelectField>
      </div>
      <button
        type="button"
        className="btn-secondary px-3 py-2 text-xs disabled:cursor-wait disabled:opacity-60"
        onClick={submitSearch}
        disabled={loading}
      >
        Tìm kiếm
      </button>
    </div>
  );
}
