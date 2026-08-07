/**
 * Admin · Nội dung — view toàn cục công ty / tin tức / bài đăng (FR-2).
 * Không bị lọc theo contest.
 */
"use client";

import { useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { PageHeader } from "@/components/common/PageHeader";
import { Spinner } from "@/components/common/Spinner";
import { useAsync } from "@/hooks/useAsync";
import {
  listAllCompanies,
  listAllNews,
  listAllSocialPosts,
} from "@/services/admin";
import { cn } from "@/utils/cn";
import { formatDateTime, formatPrice, parseDecimal } from "@/utils/format";

type Tab = "companies" | "news" | "social";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "companies", label: "Công ty" },
  { id: "news", label: "Tin tức" },
  { id: "social", label: "Bài đăng" },
];

export default function AdminContentPage() {
  const [tab, setTab] = useState<Tab>("companies");

  const companies = useAsync(() => listAllCompanies({ limit: 100 }), []);
  const news = useAsync(() => listAllNews({ limit: 100 }), []);
  const social = useAsync(() => listAllSocialPosts({ limit: 100 }), []);

  const active =
    tab === "companies"
      ? companies
      : tab === "news"
        ? news
        : social;

  return (
    <div>
      <PageHeader
        title="Nội dung"
        description="Dữ liệu toàn cục của mọi cuộc thi — không lọc theo contest."
      />

      <div className="mb-4 flex gap-1 border-b border-ink-200 dark:border-ink-700">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cn(
              "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
              tab === item.id
                ? "border-brand-600 text-brand-700 dark:text-brand-400"
                : "border-transparent text-ink-500 hover:text-ink-700 dark:hover:text-ink-200",
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {active.error !== null && <ErrorPanel error={active.error} />}

      {active.loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!active.loading &&
        active.error === null &&
        active.data !== null &&
        (active.data.items.length === 0 ? (
          <EmptyState title={`Chưa có dữ liệu ở mục này`} />
        ) : (
          <Card>
            <CardBody className="p-0">
              <div className="overflow-x-auto">
                {tab === "companies" && companies.data !== null && (
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-400 dark:border-ink-700">
                        <th className="px-4 py-3 font-semibold">Symbol</th>
                        <th className="px-4 py-3 font-semibold">Tên</th>
                        <th className="px-4 py-3 font-semibold">Ngành</th>
                        <th className="px-4 py-3 font-semibold">Giá</th>
                        <th className="px-4 py-3 font-semibold">Sức khỏe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100 dark:divide-ink-700/60">
                      {companies.data.items.map((company) => (
                        <tr key={company.id}>
                          <td className="px-4 py-3 font-semibold text-ink-900">
                            {company.symbol}
                          </td>
                          <td className="px-4 py-3 text-ink-700 dark:text-ink-200">
                            {company.name}
                          </td>
                          <td className="px-4 py-3 text-xs text-ink-500">{company.sector}</td>
                          <td className="px-4 py-3 text-ink-700 dark:text-ink-200">
                            {formatPrice(parseDecimal(company.current_price))}
                          </td>
                          <td className="px-4 py-3 text-ink-700 dark:text-ink-200">
                            {company.health_score}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {tab === "news" && news.data !== null && (
                  <ul className="divide-y divide-ink-100 dark:divide-ink-700/60">
                    {news.data.items.map((item) => (
                      <li key={item.id} className="flex items-center justify-between gap-4 px-4 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
                            {item.title}
                          </p>
                          <p className="text-xs text-ink-400">
                            {item.category} · {formatDateTime(item.simulated_at)}
                          </p>
                        </div>
                        <Badge variant={item.sentiment === "positive" ? "success" : item.sentiment === "negative" ? "danger" : "neutral"}>
                          {item.sentiment}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}

                {tab === "social" && social.data !== null && (
                  <ul className="divide-y divide-ink-100 dark:divide-ink-700/60">
                    {social.data.items.map((post) => (
                      <li key={post.id} className="px-4 py-3">
                        <div className="flex items-center justify-between gap-4">
                          <p className="text-xs font-semibold text-ink-500">
                            {post.author_name} · {post.persona_type}
                          </p>
                          <span className="text-xs text-ink-400">
                            {formatDateTime(post.simulated_at)}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-ink-700 dark:text-ink-200">
                          {post.content}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </CardBody>
          </Card>
        ))}
    </div>
  );
}
