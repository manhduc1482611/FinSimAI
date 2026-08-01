/**
 * NewsSidebar — cột phụ trang báo: tin đáng chú ý nhất + điều hướng chuyên mục.
 */
"use client";

import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import { useNewsStore } from "@/store/useNewsStore";
import { NEWS_CATEGORIES, newsCategoryLabel } from "@/utils/domain";
import { cn } from "@/utils/cn";
import type { NewsResponse } from "@finsim/shared-types/generated/api-types";

export function NewsSidebar({ items }: { items: NewsResponse[] }) {
  const filters = useNewsStore((state) => state.filters);
  const setFilters = useNewsStore((state) => state.setFilters);
  const total = useNewsStore((state) => state.total);

  const notable = [...items]
    .sort((a, b) => b.impact_score - a.impact_score)
    .slice(0, 5);

  return (
    <div className="space-y-5 lg:sticky lg:top-24">
      <section className="rounded-xl border border-ink-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
        <h2 className="mb-3 border-b border-ink-100 pb-2 text-sm font-bold uppercase tracking-wide text-ink-900 dark:border-ink-800 dark:text-ink-100">
          Tin đáng chú ý
        </h2>
        <ol className="space-y-3">
          {notable.map((news) => (
            <li key={news.id}>
              <Link
                href={`/news/${news.id}`}
                className="group block text-sm text-ink-800 transition-colors hover:text-brand-700 dark:text-ink-200 dark:hover:text-brand-400"
              >
                <span className="line-clamp-2 font-medium group-hover:underline">{news.title}</span>
                <span className="mt-1 flex items-center gap-1.5 text-xs text-ink-400">
                  <Badge variant="neutral">{newsCategoryLabel(news.category)}</Badge>
                  <span>{news.source}</span>
                  <span
                    className={cn(
                      "font-semibold",
                      news.impact_score >= 5 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
                    )}
                  >
                    {news.impact_score.toFixed(1)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
          {notable.length === 0 && <li className="text-sm text-ink-400">Chưa có tin nổi bật.</li>}
        </ol>
      </section>

      <section className="rounded-xl border border-ink-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
        <h2 className="mb-3 border-b border-ink-100 pb-2 text-sm font-bold uppercase tracking-wide text-ink-900 dark:border-ink-800 dark:text-ink-100">
          Chuyên mục
        </h2>
        <ul className="space-y-1">
          <li>
            <button
              type="button"
              onClick={() => setFilters({ category: undefined })}
              className={cn(
                "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-ink-50 dark:hover:bg-ink-800",
                filters.category === undefined
                  ? "font-semibold text-brand-700 dark:text-brand-400"
                  : "text-ink-600 dark:text-ink-300",
              )}
            >
              <span>Tất cả</span>
              <span className="text-xs text-ink-400">{total}</span>
            </button>
          </li>
          {NEWS_CATEGORIES.map((entry) => (
            <li key={entry.value}>
              <button
                type="button"
                onClick={() => setFilters({ category: entry.value })}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-ink-50 dark:hover:bg-ink-800",
                  filters.category === entry.value
                    ? "font-semibold text-brand-700 dark:text-brand-400"
                    : "text-ink-600 dark:text-ink-300",
                )}
              >
                <span>{entry.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
