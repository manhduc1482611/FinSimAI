/**
 * Trang đích của một cuộc thi — bản web thu nhỏ theo theme config (FR-5).
 * Nội dung chỉ hiển thị khi user đã join (hoặc host/admin).
 */
"use client";

import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { IconGrid } from "@/components/common/Icon";
import { Spinner } from "@/components/common/Spinner";
import { ContestStatusBadge } from "@/components/contests/ContestStatusBadge";
import { useAsync } from "@/hooks/useAsync";
import { toRequestError } from "@/services/api";
import {
  getContest,
  joinContest,
  listContestCompanies,
  listContestNews,
  listContestSocialPosts,
} from "@/services/contests";
import { useAuthStore } from "@/store/useAuthStore";
import { cn } from "@/utils/cn";
import { difficultyLabel, templateLabel } from "@/utils/contest";
import {
  formatCompactVND,
  formatDateTime,
  formatPrice,
  parseDecimal,
} from "@/utils/format";

type Tab = "companies" | "news" | "social";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "companies", label: "Công ty" },
  { id: "news", label: "Tin tức" },
  { id: "social", label: "Xã hội" },
];

export default function ContestLandingPage() {
  const params = useParams();
  const slug = typeof params.slug === "string" ? params.slug : "";

  const currentUser = useAuthStore((state) => state.user);
  const [tab, setTab] = useState<Tab>("companies");

  const contest = useAsync(() => getContest(slug), [slug]);
  const companies = useAsync(() => listContestCompanies(slug, { limit: 100 }), [slug]);
  const news = useAsync(() => listContestNews(slug, { limit: 100 }), [slug]);
  const social = useAsync(() => listContestSocialPosts(slug, { limit: 100 }), [slug]);

  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);

  const handleJoin = async () => {
    setJoinError(null);
    setJoining(true);
    try {
      await joinContest(slug);
      window.location.reload();
    } catch (err) {
      setJoinError(toRequestError(err).detail);
      setJoining(false);
    }
  };

  if (contest.loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (contest.error !== null || contest.data === null) {
    return <ErrorPanel error={contest.error ?? "Không tìm thấy cuộc thi"} />;
  }

  const c = contest.data;
  const config = c.config;
  const accent = config.theme?.primary_color || "#0ea5e9";
  const rules = config.rules;
  const isManager =
    currentUser !== null &&
    (currentUser.role === "admin" || (currentUser.role === "host" && c.owner_id === currentUser.id));
  const notJoined = companies.error !== null;

  return (
    <div>
      {/* Hero theo theme config */}
      <div
        className="rounded-xl border border-line bg-[#FFFDF8] p-6 dark:border-granite-700 dark:bg-granite-800"
        style={{ borderTop: `4px solid ${accent}` }}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-ink-900 dark:text-slip">{c.name}</h1>
              <ContestStatusBadge status={c.status} />
            </div>
            {c.description !== null && c.description !== "" && (
              <p className="mt-2 max-w-2xl text-sm text-ink-500 dark:text-granite-400">
                {c.description}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="info">{templateLabel(config.template)}</Badge>
            <Badge variant="neutral">{difficultyLabel(config.difficulty)}</Badge>
            <Badge variant="neutral">{config.company_count} công ty</Badge>
            <Badge variant="neutral">{c.member_count} thành viên</Badge>
          </div>
        </div>

        {rules !== undefined && (
          <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-line pt-4 dark:border-granite-700 sm:grid-cols-4">
            <div>
              <dt className="board-label">Vốn khởi đầu</dt>
              <dd className="board-num mt-1 text-sm font-semibold text-ink-900 dark:text-slip">
                {formatCompactVND(parseDecimal(rules.start_cash))}
              </dd>
            </div>
            <div>
              <dt className="board-label">Cooldown</dt>
              <dd className="board-num mt-1 text-sm font-semibold text-ink-900 dark:text-slip">
                {rules.cooldown_seconds ?? 0} giây
              </dd>
            </div>
            <div>
              <dt className="board-label">Đòn bẩy giá</dt>
              <dd className="board-num mt-1 text-sm font-semibold text-ink-900 dark:text-slip">
                ×{rules.volatility_multiplier ?? 1}
              </dd>
            </div>
            <div>
              <dt className="board-label">Bán khống</dt>
              <dd className="board-num mt-1 text-sm font-semibold text-ink-900 dark:text-slip">
                {rules.allow_short ? "Cho phép" : "Không cho phép"}
              </dd>
            </div>
          </dl>
        )}
      </div>

      {/* Chưa join → mời join */}
      {notJoined && !isManager && c.status === "active" && (
        <Card className="mt-6">
          <CardBody className="flex flex-col items-center justify-between gap-3 sm:flex-row">
            <div>
              <p className="text-sm font-semibold text-ink-900 dark:text-slip">
                Tham gia cuộc thi để xem nội dung
              </p>
              <p className="text-xs text-ink-500">
                Sau khi tham gia, bạn sẽ thấy công ty, tin tức và bài viết của riêng contest này.
              </p>
            </div>
            <Button loading={joining} onClick={handleJoin}>
              Tham gia ngay
            </Button>
          </CardBody>
          {joinError !== null && <div className="px-4 pb-4"><ErrorPanel error={joinError} /></div>}
        </Card>
      )}

      {!notJoined && (
        <div className="mt-6">
          <div className="mb-4 flex gap-1 border-b border-line dark:border-granite-700">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={cn(
                  "border-b-2 px-4 py-2 text-sm font-medium transition-colors",
                  tab === item.id
                    ? "border-brand-600 text-brand-700 dark:text-brand-400"
                    : "border-transparent text-ink-500 hover:text-ink-700 dark:hover:text-granite-200",
                )}
                style={tab === item.id ? { borderColor: accent } : undefined}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "companies" &&
            (companies.loading ? (
              <Spinner />
            ) : companies.error !== null ? (
              <ErrorPanel error={companies.error} />
            ) : (companies.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="Chưa có công ty" icon={<IconGrid className="h-6 w-6" />} />
            ) : (
              <Card>
                <CardBody className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="board-label border-b border-line dark:border-granite-700">
                          <th className="px-4 py-3 font-semibold">Symbol</th>
                          <th className="px-4 py-3 font-semibold">Tên</th>
                          <th className="px-4 py-3 font-semibold">Ngành</th>
                          <th className="px-4 py-3 font-semibold">Giá hiện tại</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line dark:divide-granite-800">
                        {companies.data?.items.map((company) => (
                          <tr key={company.id}>
                            <td className="board-num px-4 py-3 font-semibold text-ink-900 dark:text-slip">{company.symbol}</td>
                            <td className="px-4 py-3 text-ink-700 dark:text-slip">{company.name}</td>
                            <td className="px-4 py-3 text-xs text-ink-500">{company.sector}</td>
                            <td className="board-num px-4 py-3 text-ink-700 dark:text-slip">
                              {formatPrice(parseDecimal(company.current_price))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardBody>
              </Card>
            ))}

          {tab === "news" &&
            (news.loading ? (
              <Spinner />
            ) : news.error !== null ? (
              <ErrorPanel error={news.error} />
            ) : (news.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="Chưa có tin tức" />
            ) : (
              <Card>
                <CardBody className="p-0">
                  <ul className="divide-y divide-line dark:divide-granite-800">
                    {news.data?.items.map((item) => (
                      <li key={item.id} className="px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-medium text-ink-900 dark:text-slip">
                            {item.title}
                          </p>
                          <span className="shrink-0 text-xs text-ink-400">
                            {formatDateTime(item.simulated_at)}
                          </span>
                        </div>
                        {item.summary !== null && (
                          <p className="mt-1 line-clamp-2 text-sm text-ink-500">{item.summary}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            ))}

          {tab === "social" &&
            (social.loading ? (
              <Spinner />
            ) : social.error !== null ? (
              <ErrorPanel error={social.error} />
            ) : (social.data?.items.length ?? 0) === 0 ? (
              <EmptyState title="Chưa có bài đăng" />
            ) : (
              <Card>
                <CardBody className="p-0">
                  <ul className="divide-y divide-line dark:divide-granite-800">
                    {social.data?.items.map((post) => (
                      <li key={post.id} className="px-4 py-3">
                        <p className="text-xs font-semibold text-ink-500">
                          {post.author_name} · {post.persona_type}
                        </p>
                        <p className="mt-1 text-sm text-ink-700 dark:text-slip">{post.content}</p>
                      </li>
                    ))}
                  </ul>
                </CardBody>
              </Card>
            ))}
        </div>
      )}
    </div>
  );
}
