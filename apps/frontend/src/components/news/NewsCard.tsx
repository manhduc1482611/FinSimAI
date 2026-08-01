/**
 * NewsCard — thẻ tin tức trong danh sách: sentiment, tác động, nguồn, thời gian.
 */
import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import { IconTrendDown, IconTrendUp } from "@/components/common/Icon";
import type { NewsResponse } from "@finsim/shared-types/generated/api-types";

import { formatRelativeTime } from "@/utils/format";
import { newsCategoryLabel, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";

export function NewsCard({ news }: { news: NewsResponse }) {
  const positive = news.impact_score >= 5;

  return (
    <Link
      href={`/news/${news.id}`}
      className="card group flex flex-col p-4 transition-shadow hover:shadow-md"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <Badge variant={sentimentVariant(news.sentiment)}>
          {sentimentLabel(news.sentiment)}
        </Badge>
        <span className="text-xs text-ink-400">{formatRelativeTime(news.simulated_at)}</span>
      </div>

      <h3 className="line-clamp-2 text-sm font-semibold text-ink-900 group-hover:text-brand-700">
        {news.title}
      </h3>
      {news.summary !== null && (
        <p className="mt-1 line-clamp-2 text-xs text-ink-500">{news.summary}</p>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-ink-100 pt-3">
        <span className="truncate text-xs text-ink-400">
          {newsCategoryLabel(news.category)} · {news.source}
        </span>
        <span
          className={cn(
            "flex shrink-0 items-center gap-1 text-xs font-semibold",
            positive ? "text-emerald-600" : "text-red-600",
          )}
          title={`Mức tác động ${news.impact_score}/10`}
        >
          {positive ? (
            <IconTrendUp className="h-3.5 w-3.5" />
          ) : (
            <IconTrendDown className="h-3.5 w-3.5" />
          )}
          {news.impact_score.toFixed(1)}
        </span>
      </div>
    </Link>
  );
}
