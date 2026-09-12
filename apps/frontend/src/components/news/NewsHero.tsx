/**
 * NewsHero — tin chính đầu trang báo: danh mục, tiêu đề lớn, sapo, tác động + nút lưu.
 */
import Link from "next/link";

import { Badge } from "@/components/common/Badge";
import { BookmarkButton } from "@/components/common/BookmarkButton";
import { IconTrendDown, IconTrendUp } from "@/components/common/Icon";
import type { NewsResponse } from "@finsim/shared-types/generated/api-types";

import { formatImpact, formatRelativeTime, sanitizeTemplateVars } from "@/utils/format";
import { newsCategoryLabel, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";

export function NewsHero({ news }: { news: NewsResponse }) {
  const impactNum = Number(news.impact_score);
  const safeImpact = Number.isFinite(impactNum) && impactNum <= 100 ? impactNum : 0;
  const positive = safeImpact >= 5;
  const safeTitle = sanitizeTemplateVars(news.title);

  return (
    <article className="card overflow-hidden transition-shadow hover:shadow-md">
      <div className="p-5 sm:p-6">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-sm bg-brand-500 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-granite-950">
              {newsCategoryLabel(news.category)}
            </span>
            <Badge variant={sentimentVariant(news.sentiment)}>
              {sentimentLabel(news.sentiment)}
            </Badge>
            <span className="text-xs text-ink-400">{formatRelativeTime(news.simulated_at)}</span>
          </div>
          <BookmarkButton
            contentId={news.id}
            contentType="news"
            saved={news.is_saved ?? false}
            className="rounded-full p-1.5 hover:bg-brand-500/10"
          />
        </div>

        <Link href={`/news/${news.id}`} className="group block">
          <h2 className="text-xl font-bold leading-snug text-ink-900 transition-colors group-hover:text-brand-700 sm:text-2xl dark:text-slip dark:group-hover:text-brand-400">
            {safeTitle}
          </h2>

          {news.summary !== null && (
            <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-ink-600 dark:text-granite-300">
              {sanitizeTemplateVars(news.summary)}
            </p>
          )}
        </Link>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line pt-3 text-xs text-ink-400 dark:border-granite-800">
          <span className="font-medium text-ink-500 dark:text-granite-300">{news.source}</span>
          <span
            className={cn(
              "flex items-center gap-1 font-semibold",
              positive ? "text-mkt-up dark:text-mkt-up-400" : "text-mkt-down dark:text-mkt-down-400",
            )}
          >
            {positive ? <IconTrendUp className="h-3.5 w-3.5" /> : <IconTrendDown className="h-3.5 w-3.5" />}
            Tác động {formatImpact(safeImpact)}/10
          </span>
          {news.is_ai_generated && <Badge variant="info">AI tạo</Badge>}
        </div>
      </div>
    </article>
  );
}