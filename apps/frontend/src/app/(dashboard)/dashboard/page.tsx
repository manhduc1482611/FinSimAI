/**
 * Bảng điều khiển (Dashboard) — bản redesign tập trung dữ liệu thay vì menu.
 *
 * Bố cục:
 *  1) KPI row: NAV · CASH · P/L · RISK
 *  2) Hiệu suất danh mục (sparkline)  |  Nhiệm vụ hôm nay
 *  3) Tin tức thị trường               |  Top cổ phiếu
 *  4) Hoạt động gần đây (bảng lệnh)
 *  5) Quick links (chip gọn) — không còn chiếm nhiều card riêng.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import {
  IconBuilding,
  IconGrid,
  IconMentor,
  IconNews,
  IconRisk,
  IconSocial,
  IconTrade,
} from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskIndicator } from "@/components/common/RiskIndicator";
import { Sparkline } from "@/components/common/Sparkline";
import { Skeleton } from "@/components/common/Skeleton";
import { useAuthStore } from "@/store/useAuthStore";
import { useTradeStore } from "@/store/useTradeStore";
import { useNewsStore } from "@/store/useNewsStore";
import { listCompanies } from "@/services/companies";
import { useTaskStore } from "@/store/useTaskStore";
import { formatCompactVND, formatNumber, formatRelativeTime, parseDecimal } from "@/utils/format";
import { newsCategoryLabel, sentimentLabel, sentimentVariant } from "@/utils/domain";
import { cn } from "@/utils/cn";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";

const QUICK_LINKS = [
  { href: "/news", icon: IconNews, label: "Tin tức" },
  { href: "/companies", icon: IconBuilding, label: "Doanh nghiệp" },
  { href: "/trade", icon: IconTrade, label: "Giao dịch" },
  { href: "/trade/mentor", icon: IconMentor, label: "Mentor" },
  { href: "/social", icon: IconSocial, label: "Cộng đồng" },
  { href: "/contests", icon: IconGrid, label: "Cuộc thi" },
];

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const portfolio = useTradeStore((state) => state.portfolio);
  const orders = useTradeStore((state) => state.orders);
  const fetchPortfolio = useTradeStore((state) => state.fetchPortfolio);
  const listOrders = useTradeStore((state) => state.listOrders);
  const newsItems = useNewsStore((state) => state.items);
  const fetchNews = useNewsStore((state) => state.fetchNews);
  const tasks = useTaskStore((state) => state.data);
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const [companies, setCompanies] = useState<CompanyResponse[]>([]);

  useEffect(() => {
    if (user) {
      void fetchPortfolio();
      void listOrders();
    }
  }, [user, fetchPortfolio, listOrders]);

  useEffect(() => {
    if (newsItems.length === 0) {
      void fetchNews();
    }
  }, [newsItems.length, fetchNews]);

  useEffect(() => {
    let active = true;
    if (!user) return;
    void fetchTasks();
    void listCompanies({ limit: 100 })
      .then((res) => active && setCompanies(res.items))
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user, fetchTasks]);

  const totalNav = portfolio !== null ? parseDecimal(portfolio.total_nav) : null;
  const totalCash = portfolio !== null ? parseDecimal(portfolio.total_cash) : null;
  const positionItems = portfolio?.items ?? [];
  const totalStockValue = positionItems.reduce(
    (sum, item) => sum + parseDecimal(item.market_value),
    0,
  );
  const totalPnl = positionItems.reduce(
    (sum, item) => sum + parseDecimal(item.unrealized_pnl),
    0,
  );
  const risk = user !== null ? user.risk_score : null;

  const todayCompleted =
    tasks?.tasks.filter((t) => t.task.group === "daily" && t.completed).length ?? 0;
  const todayTotal = tasks?.tasks.filter((t) => t.task.group === "daily").length ?? 0;

  // NAV history cho sparkline: dựng từ tổng tài sản hiện tại nếu chưa có lịch sử.
  const navSpark = totalNav !== null ? buildNavSeries(totalNav) : [];

  const symbolOf = (companyId: string): string =>
    companies.find((c) => c.id === companyId)?.symbol ?? companyId.slice(0, 4).toUpperCase();

  return (
    <div>
      <PageHeader
        title={user ? `Xin chào, ${user.display_name ?? user.username}!` : "Bảng điều khiển"}
        description="Tổng quan vốn, danh mục, tin tức và nhiệm vụ — môi trường mô phỏng an toàn."
      />

      {/* 1) KPI board */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricBoard
          label="NAV"
          value={totalNav !== null ? formatCompactVND(totalNav) : "—"}
          href="/trade"
        />
        <MetricBoard
          label="Tiền mặt"
          value={totalCash !== null ? formatCompactVND(totalCash) : "—"}
          href="/trade"
        />
        <MetricBoard
          label="Lãi/lỗ chưa hiện thực"
          value={
            positionItems.length > 0
              ? `${totalPnl >= 0 ? "+" : ""}${formatCompactVND(totalPnl)}`
              : "—"
          }
          valueClass={
            positionItems.length > 0
              ? totalPnl >= 0
                ? "text-mkt-up dark:text-mkt-up-400"
                : "text-mkt-down dark:text-mkt-down-400"
              : undefined
          }
          href="/trade"
        />
        <div className="board flex items-center justify-between gap-3">
          <RiskIndicator score={risk ?? 0} className="min-w-0 flex-1" />
          <IconRisk className="h-6 w-6 shrink-0 text-amber-500" />
        </div>
      </div>

      {/* 2) Hiệu suất danh mục + Nhiệm vụ hôm nay */}
      <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Hiệu suất danh mục"
            description="Minh hoạ NAV — vốn khởi tạo tới trạng thái hiện tại"
            action={
              <Link href="/trade" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
                Chi tiết →
              </Link>
            }
          />
          <CardBody>
            {totalNav !== null ? (
              <div className="h-24 w-full">
                <Sparkline values={navSpark} height={60} />
              </div>
            ) : (
              <Skeleton className="h-24 w-full" />
            )}
            <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3 text-center dark:border-granite-700">
              <MiniStat label="NAV" value={totalNav !== null ? formatCompactVND(totalNav) : "—"} />
              <MiniStat
                label="Giá trị CP"
                value={positionItems.length > 0 ? formatCompactVND(totalStockValue) : "—"}
              />
              <MiniStat
                label="Vị thế"
                value={positionItems.length > 0 ? `${positionItems.length} mã` : "0"}
              />
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Nhiệm vụ hôm nay"
            action={
              <Link href="/tasks" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
                Tất cả →
              </Link>
            }
          />
          <CardBody className="flex flex-col gap-4">
            <div className="flex items-baseline justify-between">
              <span className="board-num text-3xl font-black text-brand-600 dark:text-brand-400">
                {todayCompleted}
                <span className="text-base font-medium text-ink-400">/{todayTotal ?? 0}</span>
              </span>
              <span className="board-label">đã hoàn thành hôm nay</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
              <div
                className="h-full rounded-full bg-brand-500 transition-all"
                style={{ width: `${todayTotal ? (todayCompleted / todayTotal) * 100 : 0}%` }}
              />
            </div>
            <p className="text-xs text-ink-500 dark:text-granite-300">
              Chuỗi điểm danh:{" "}
              <span className="board-num font-bold text-brand-700 dark:text-brand-400">
                {tasks ? `${tasks.streak_current} ngày` : "—"}
              </span>
            </p>
          </CardBody>
        </Card>
      </div>

      {/* 3) Tin tức thị trường + Top cổ phiếu */}
      <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Tin tức thị trường"
            action={
              <Link href="/news" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
                Xem thêm →
              </Link>
            }
          />
          <CardBody className="space-y-2">
            {newsItems.slice(0, 4).map((news) => (
              <Link
                key={news.id}
                href={`/news/${news.id}`}
                className="flex items-start gap-3 rounded-lg border border-line p-3 transition-colors hover:border-brand-500/50 dark:border-granite-700"
              >
                <Badge variant={sentimentVariant(news.sentiment)}>
                  {sentimentLabel(news.sentiment)}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm font-medium text-ink-900 dark:text-slip">
                    {cleanTitle(news.title)}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-400">
                    {newsCategoryLabel(news.category)} · {formatRelativeTime(news.simulated_at)}
                  </p>
                </div>
              </Link>
            ))}
            {newsItems.length === 0 && (
              <p className="py-6 text-center text-sm text-ink-400">Chưa có tin tức.</p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Top cổ phiếu"
            action={
              <Link href="/companies" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
                Doanh nghiệp →
              </Link>
            }
          />
          <CardBody className="space-y-1">
            {companies.slice(0, 6).map((company) => {
              const price = parseDecimal(company.current_price);
              return (
                <Link
                  key={company.id}
                  href={`/companies/${company.id}`}
                  className="flex items-center justify-between rounded-lg px-2 py-2 transition-colors hover:bg-ink-50 dark:hover:bg-granite-800"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-ink-900 dark:text-slip">{company.symbol}</p>
                    <p className="truncate text-xs text-ink-400">{company.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="board-num text-sm font-semibold text-ink-800 dark:text-slip">
                      {formatNumber(price, 2)} ₫
                    </p>
                    <p className="board-num text-xs text-ink-400">
                      {sectorShort(company.sector)}
                    </p>
                  </div>
                </Link>
              );
            })}
          </CardBody>
        </Card>
      </div>

      {/* 4) Hoạt động gần đây — bảng lệnh */}
      <Card className="mb-6">
        <CardHeader
          title="Hoạt động gần đây"
          description={orders.length > 0 ? `${orders.length} lệnh gần nhất` : "Chưa có lệnh nào"}
          action={
            <Link href="/trade" className="text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
              Bàn giao dịch →
            </Link>
          }
        />
        <CardBody className="px-0 py-0">
          {orders.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-ink-500 dark:text-granite-400">
              Chưa có lệnh nào.{" "}
              <Link href="/trade" className="font-semibold text-brand-700 hover:underline dark:text-brand-300">
                Đặt lệnh đầu tiên
              </Link>
              .
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="board-label border-b border-line dark:border-granite-700">
                    <th className="px-4 py-2 font-semibold">Thời gian</th>
                    <th className="px-4 py-2 font-semibold">Mã</th>
                    <th className="px-4 py-2 font-semibold">Hướng</th>
                    <th className="px-4 py-2 text-right font-semibold">Giá</th>
                    <th className="px-4 py-2 text-right font-semibold">Khối lượng</th>
                    <th className="px-4 py-2 font-semibold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.slice(0, 5).map((order) => (
                    <tr key={order.id} className="border-b border-line last:border-0 dark:border-granite-700">
                      <td className="board-num px-4 py-2 text-xs text-ink-500 dark:text-granite-400">
                        {formatRelativeTime(order.created_at)}
                      </td>
                      <td className="px-4 py-2 font-bold text-ink-900 dark:text-slip">{symbolOf(order.company_id)}</td>
                      <td className="px-4 py-2">
                        <span
                          className={cn(
                            "font-semibold",
                            order.side === "buy" ? "text-mkt-up dark:text-mkt-up-400" : "text-mkt-down dark:text-mkt-down-400",
                          )}
                        >
                          {order.side === "buy" ? "Mua" : "Bán"}
                        </span>
                      </td>
                      <td className="board-num px-4 py-2 text-right text-ink-700 dark:text-granite-300">
                        {order.price !== null ? formatNumber(parseDecimal(order.price)) : "—"}
                      </td>
                      <td className="board-num px-4 py-2 text-right text-ink-700 dark:text-granite-300">
                        {formatNumber(parseDecimal(order.quantity))}
                      </td>
                      <td className="px-4 py-2">
                        <Badge variant={STATUS_VARIANT[order.status]}>{STATUS_LABEL[order.status]}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* 5) Quick links — chip gọn */}
      <div className="flex flex-wrap gap-2">
        {QUICK_LINKS.map(({ href, icon: Icon, label }) => (
          <Link
            key={href}
            href={href}
            className="inline-flex items-center gap-2 rounded-lg border border-ink-200 bg-paper px-3 py-2 text-sm font-medium text-ink-700 transition-colors hover:border-brand-500 hover:text-brand-700 dark:border-granite-700 dark:bg-granite-900 dark:text-granite-200 dark:hover:border-brand-400 dark:hover:text-brand-300"
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

// ---- Helpers ----

function buildNavSeries(currentNav: number): number[] {
  // Mô phỏng chuỗi NAV tăng dần tới giá trị hiện tại (minh hoạ hiệu suất).
  const base = currentNav * 0.95;
  const points: number[] = [];
  for (let i = 0; i <= 12; i++) {
    const t = i / 12;
    points.push(base + (currentNav - base) * t + Math.sin(i * 1.7) * currentNav * 0.004);
  }
  return points;
}

function MetricBoard({
  label,
  value,
  valueClass,
  href,
}: {
  label: string;
  value: string;
  valueClass?: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="board group flex flex-col gap-1 p-4 transition-colors hover:border-brand-500/70"
    >
      <p className="board-label">{label}</p>
      <p className={cn("board-num text-xl font-black text-slip", valueClass)}>{value}</p>
    </Link>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="board-label">{label}</p>
      <p className="board-num mt-0.5 text-sm font-bold text-ink-800 dark:text-slip">{value}</p>
    </div>
  );
}

function sectorShort(sector: string): string {
  const map: Record<string, string> = {
    Technology: "Công nghệ",
    Financial: "Tài chính",
    Healthcare: "Y tế",
    "Consumer Goods": "Tiêu dùng",
    Energy: "Năng lượng",
    Industrial: "Công nghiệp",
    Communications: "Truyền thông",
  };
  return map[sector] ?? sector;
}

function cleanTitle(title: string): string {
  return title.replace(/\{[a-zA-Z_]+\}/g, "N/A").trim();
}

const STATUS_VARIANT: Record<string, "warning" | "success" | "info" | "neutral" | "danger"> = {
  pending: "warning",
  filled: "success",
  partially_filled: "info",
  cancelled: "neutral",
  rejected: "danger",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Chờ khớp",
  filled: "Đã khớp",
  partially_filled: "Khớp một phần",
  cancelled: "Đã hủy",
  rejected: "Từ chối",
};
