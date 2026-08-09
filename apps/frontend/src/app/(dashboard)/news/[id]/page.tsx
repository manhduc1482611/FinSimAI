/** Chi tiết một tin tức — layout bài báo chính thức + tin liên quan. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { Spinner } from "@/components/common/Spinner";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconTrendDown, IconTrendUp } from "@/components/common/Icon";
import { useKnowledge } from "@/hooks/useKnowledge";
import { getNews, listNews } from "@/services/news";
import type { NewsResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

import { formatDateTime } from "@/utils/format";
import { newsCategoryLabel, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";

export default function NewsDetailPage({ params }: { params: { id: string } }) {
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [related, setRelated] = useState<NewsResponse[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const { matches, match } = useKnowledge();

  const load = async () => {
    setStatus("loading");
    setError(null);
    try {
      const data = await getNews(params.id);
      setNews(data);
      setStatus("success");
      void match(`${data.title} ${data.summary ?? ""}`);

      try {
        const response = await listNews({ limit: 12 });
        const others = response.items.filter((item) => item.id !== data.id);
        const sameCategory = others.filter((item) => item.category === data.category);
        const sameCompany = others.filter(
          (item) =>
            item.company_id !== null && item.company_id === data.company_id,
        );
        const seen = new Set<string>();
        setRelated(
          [...sameCompany, ...sameCategory, ...others]
            .filter((item) => {
              if (seen.has(item.id)) {
                return false;
              }
              seen.add(item.id);
              return true;
            })
            .slice(0, 4),
        );
      } catch {
        // Tin liên quan là phụ — không cần chặn trang chính.
      }
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Không tải được tin tức");
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  if (status === "loading" && news === null) {
    return (
      <div className="flex justify-center py-20">
        <Spinner size="lg" />
      </div>
    );
  }

  if (status === "error" || news === null) {
    return <ErrorPanel error={error} onRetry={() => void load()} />;
  }

  const positive = news.impact_score >= 5;

  return (
    <div className="mx-auto max-w-4xl">
      <nav className="mb-4 text-sm text-ink-500 dark:text-granite-400">
        <Link href="/news" className="hover:text-brand-600 dark:hover:text-brand-400">
          ← Tin tức
        </Link>
      </nav>

      <article>
        <header className="mb-6">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="rounded-sm bg-brand-500 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-granite-950">
              {newsCategoryLabel(news.category)}
            </span>
            <Badge variant={sentimentVariant(news.sentiment)}>
              {sentimentLabel(news.sentiment)}
            </Badge>
            {news.is_ai_generated && <Badge variant="info">AI tạo</Badge>}
          </div>

          <h1 className="text-2xl font-bold leading-snug text-ink-900 sm:text-3xl dark:text-slip">
            {news.title}
          </h1>

          {news.summary !== null && (
            <p className="mt-4 border-l-2 border-brand-500 pl-4 text-base font-medium leading-relaxed text-ink-700 dark:text-slip">
              {news.summary}
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-ink-500 dark:text-granite-400">
            <span className="font-semibold text-ink-700 dark:text-slip">{news.source}</span>
            <span>·</span>
            <time dateTime={news.simulated_at}>{formatDateTime(news.simulated_at)}</time>
            <span className="flex items-center gap-1">
              Tác động:
              <span
                className={cn(
                  "flex items-center gap-1 font-semibold",
                  positive ? "text-mkt-up dark:text-mkt-up-400" : "text-mkt-down dark:text-mkt-down-400",
                )}
              >
                {positive ? <IconTrendUp className="h-4 w-4" /> : <IconTrendDown className="h-4 w-4" />}
                {news.impact_score.toFixed(1)} / 10
              </span>
            </span>
          </div>
        </header>

        <div className="space-y-4 border-t border-line pt-6 whitespace-pre-line text-sm leading-relaxed text-ink-800 dark:border-granite-800 dark:text-slip">
          <p className="text-base leading-relaxed text-ink-900 first-letter:text-3xl first-letter:font-bold first-letter:text-brand-600 dark:text-slip dark:first-letter:text-brand-400">
            {news.content}
          </p>
        </div>
      </article>

      {related.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 border-b border-line pb-2 text-sm font-bold uppercase tracking-wide text-ink-900 dark:border-granite-800 dark:text-slip">
            Tin liên quan
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {related.map((item) => (
              <Link
                key={item.id}
                href={`/news/${item.id}`}
                className="card group flex flex-col p-4 transition-shadow hover:shadow-md"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <Badge variant="neutral">{newsCategoryLabel(item.category)}</Badge>
                  <span className="text-xs text-ink-400">{formatDateTime(item.simulated_at)}</span>
                </div>
                <h3 className="line-clamp-2 text-sm font-semibold text-ink-900 group-hover:text-brand-700 dark:text-slip dark:group-hover:text-brand-400">
                  {item.title}
                </h3>
                {item.summary !== null && (
                  <p className="mt-1 line-clamp-2 text-xs text-ink-500 dark:text-granite-400">{item.summary}</p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {matches.length > 0 && (
        <Card className="mt-8">
          <CardHeader title="Kiến thức liên quan" description="Học nhanh các khái niệm gặp trong bài" />
          <CardBody className="space-y-3">
            {matches.map((item) => (
              <div key={item.id} className="rounded-lg border border-line p-3 dark:border-granite-800">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-ink-900 dark:text-slip">{item.concept}</p>
                  <Badge variant="info">Độ khó {item.difficulty}</Badge>
                </div>
                <p className="mt-1 text-sm text-ink-600 dark:text-granite-300">{item.definition}</p>
              </div>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
