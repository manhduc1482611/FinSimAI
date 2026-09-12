/**
 * NewsCard — thẻ tin tức trong danh sách: sentiment, tác động, nguồn, thời gian + nút lưu.
 */
import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import { BookmarkButton } from "@/components/common/BookmarkButton";
import { IconTrendDown, IconTrendUp } from "@/components/common/Icon";
import type { NewsResponse } from "@finsim/shared-types/generated/api-types";

import { formatImpact, formatRelativeTime, sanitizeTemplateVars } from "@/utils/format";
import { newsCategoryLabel, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";

export interface NewsCardProps {
  news: NewsResponse;
  /** Khi bỏ lưu ngay tại danh sách "Đã lưu" → xoá item khỏi parent. */
  onRemove?: (newsId: string) => void;
}

export function NewsCard({ news, onRemove }: NewsCardProps) {
  const impactNum = Number(news.impact_score);
  const safeImpact = Number.isFinite(impactNum) && impactNum <= 100 ? impactNum : 0;
  const positive = safeImpact >= 5;
  const safeTitle = sanitizeTemplateVars(news.title);

  return (
    <article className="card group flex flex-col p-4 transition-shadow hover:shadow-md">
      <div className="mb-2 flex items-center justify-between gap-2">
        <Badge variant={sentimentVariant(news.sentiment)}>
          {sentimentLabel(news.sentiment)}
        </Badge>
        <div className="flex items-center gap-1">
          <span className="text-xs text-ink-400">{formatRelativeTime(news.simulated_at)}</span>
          <BookmarkButton
            contentId={news.id}
            contentType="news"
            saved={news.is_saved ?? false}
            onRemove={onRemove}
            className="p-1"
          />
        </div>
      </div>

      <Link
        href={`/news/${news.id}`}
        className="group flex min-w-0 flex-1 flex-col"
      >
        <h3 className="line-clamp-2 text-sm font-semibold text-ink-900 group-hover:text-brand-700 dark:text-slip">
          {safeTitle}
        </h3>
        {news.summary !== null && (
          <p className="mt-1 line-clamp-2 text-xs text-ink-500">{sanitizeTemplateVars(news.summary)}</p>
        )}
      </Link>

      <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
        <span className="truncate text-xs text-ink-400">
          {newsCategoryLabel(news.category)} · {news.source}
        </span>
        <span
          className={cn(
            "flex shrink-0 items-center gap-1 text-xs font-semibold",
            positive ? "text-mkt-up" : "text-mkt-down",
          )}
          title={`Mức tác động ${safeImpact}/10`}
        >
          {positive ? (
            <IconTrendUp className="h-3.5 w-3.5" />
          ) : (
            <IconTrendDown className="h-3.5 w-3.5" />
          )}
          {formatImpact(safeImpact)}
        </span>
      </div>
    </article>
  );
}