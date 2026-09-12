/**
 * Header — thanh trên cùng của dashboard (mặt quầy).
 * Hiển thị: menu mobile + tiêu đề trang · board NAV/Cash/Rủi ro · UserMenu.
 */
"use client";

import { usePathname } from "next/navigation";

import { IconMenu, IconMoon, IconSun } from "@/components/common/Icon";
import { useTheme } from "@/components/common/ThemeProvider";
import { UserMenu } from "@/components/layout/UserMenu";
import { QuestPopover } from "@/components/rewards/QuestPopover";
import { useAuthStore } from "@/store/useAuthStore";
import { useTradeStore } from "@/store/useTradeStore";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

export interface HeaderProps {
  onOpenSidebar: () => void;
}

const PAGE_TITLES: Array<{ pattern: string; title: string }> = [
  { pattern: "/dashboard", title: "Bảng điều khiển" },
  { pattern: "/contests", title: "Cuộc thi" },
  { pattern: "/news", title: "Tin tức & Cảm xúc thị trường" },
  { pattern: "/saved", title: "Đã lưu" },
  { pattern: "/companies", title: "Doanh nghiệp" },
  { pattern: "/trade/mentor", title: "Mentor Socratic" },
  { pattern: "/trade", title: "Bàn giao dịch" },
  { pattern: "/tasks", title: "Nhiệm vụ & Thưởng" },
  { pattern: "/social", title: "Cộng đồng & Heatmap" },
];

function getPageTitle(pathname: string): string {
  const match = PAGE_TITLES.find(
    (entry) => pathname === entry.pattern || pathname.startsWith(`${entry.pattern}/`),
  );
  return match?.title ?? "Capia";
}

/** Hiển thị đầy đủ giá trị VND (có dấu phân tách nghìn) cho tooltip. */
function formatFullVND(value: number): string {
  return `${value.toLocaleString("vi-VN")} ₫`;
}

function RiskBadge({ score }: { score: number }) {
  const level = score < 30 ? "Thấp" : score < 60 ? "Trung bình" : "Cao";
  const tone =
    score < 30
      ? "border-mkt-up/50 text-mkt-up"
      : score < 60
        ? "border-amber-400/50 text-amber-400"
        : "border-mkt-down/60 text-mkt-down-400";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border-2 px-2 py-1 font-mono text-xs font-bold tracking-board",
        tone,
      )}
      title={`Điểm rủi ro: ${score}/100 — ${level}`}
    >
      RỦI RO {score}/100
    </span>
  );
}

function CounterMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="board text-right" aria-label={`${label}: ${value}`}>
      <p className="board-label">{label}</p>
      <p className="board-num text-sm font-bold text-slip">{value}</p>
    </div>
  );
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const portfolio = useTradeStore((state) => state.portfolio);
  const { theme, toggleTheme } = useTheme();

  const nav =
    portfolio !== null
      ? parseDecimal(portfolio.total_nav)
      : user !== null
        ? parseDecimal(user.cash_balance)
        : null;
  const cash =
    portfolio !== null
      ? parseDecimal(portfolio.total_cash)
      : user !== null
        ? parseDecimal(user.cash_balance)
        : null;
  const risk = user !== null ? user.risk_score : null;

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-paper/90 px-4 backdrop-blur dark:border-granite-800 dark:bg-granite-950/85 sm:px-6">
      <button
        type="button"
        className="btn-ghost p-2 lg:hidden"
        onClick={onOpenSidebar}
        aria-label="Mở menu"
      >
        <IconMenu className="h-5 w-5" />
      </button>

      <div className="min-w-0 flex-1">
        <h2 className="truncate text-sm font-bold tracking-tight text-ink-900 dark:text-slip sm:text-base">
          {getPageTitle(pathname)}
        </h2>
        {!token && (
          <p className="hidden text-xs text-amber-700 dark:text-amber-400 sm:block">
            Chế độ xem thử — đăng nhập để có dữ liệu thật
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối"}
          title={theme === "dark" ? "Chế độ sáng" : "Chế độ tối"}
          className="btn-ghost p-2"
        >
          {theme === "dark" ? (
            <IconSun className="h-5 w-5" />
          ) : (
            <IconMoon className="h-5 w-5" />
          )}
        </button>

        <div className="group relative hidden items-center gap-2 md:flex">
          <CounterMetric label="NAV" value={nav !== null ? formatCompactVND(nav) : "—"} />
          <CounterMetric label="Cash" value={cash !== null ? formatCompactVND(cash) : "—"} />
          {risk !== null && <RiskBadge score={risk} />}

          {(nav !== null || cash !== null || risk !== null) && (
            <div className="pointer-events-none absolute top-full right-0 mt-2 hidden w-56 rounded-lg border border-line bg-paper p-3 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 dark:border-granite-700 dark:bg-granite-900">
              <div className="space-y-1.5 text-xs">
                <p className="board-label mb-1">Tổng quan tài chính</p>
                <p className="flex justify-between">
                  <span className="text-ink-500 dark:text-granite-400">NAV</span>
                  <span className="board-num font-semibold text-ink-900 dark:text-slip">
                    {nav !== null ? formatFullVND(nav) : "—"}
                  </span>
                </p>
                <p className="flex justify-between">
                  <span className="text-ink-500 dark:text-granite-400">Tiền mặt</span>
                  <span className="board-num font-semibold text-ink-900 dark:text-slip">
                    {cash !== null ? formatFullVND(cash) : "—"}
                  </span>
                </p>
                {risk !== null && (
                  <p className="flex justify-between">
                    <span className="text-ink-500 dark:text-granite-400">Rủi ro</span>
                    <span className="board-num font-semibold text-ink-900 dark:text-slip">
                      {risk}/100 — {risk < 30 ? "Thấp" : risk < 60 ? "Trung bình" : "Cao"}
                    </span>
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        <QuestPopover />
        <UserMenu />
      </div>
    </header>
  );
}
