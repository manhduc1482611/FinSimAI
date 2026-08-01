/**
 * Header — thanh trên cùng của dashboard.
 * Hiển thị: menu mobile + tiêu đề trang | NAV · Cash · Điểm rủi ro | UserMenu.
 */
"use client";

import { usePathname } from "next/navigation";

import { IconMenu, IconMoon, IconSun } from "@/components/common/Icon";
import { useTheme } from "@/components/common/ThemeProvider";
import { UserMenu } from "@/components/layout/UserMenu";
import { useAuthStore } from "@/store/useAuthStore";
import { useTradeStore } from "@/store/useTradeStore";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

export interface HeaderProps {
  onOpenSidebar: () => void;
}

const PAGE_TITLES: Array<{ pattern: string; title: string }> = [
  { pattern: "/news", title: "Tin tức & Cảm xúc thị trường" },
  { pattern: "/companies", title: "Doanh nghiệp" },
  { pattern: "/trade/mentor", title: "Mentor Socratic" },
  { pattern: "/trade", title: "Bàn giao dịch" },
  { pattern: "/social", title: "Cộng đồng & Heatmap" },
];

function getPageTitle(pathname: string): string {
  const match = PAGE_TITLES.find(
    (entry) => pathname === entry.pattern || pathname.startsWith(`${entry.pattern}/`),
  );
  return match?.title ?? "FinSimAI";
}

function RiskBadge({ score }: { score: number }) {
  const tone =
    score < 30
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/30"
      : score < 60
        ? "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/30"
        : "bg-red-50 text-red-700 ring-red-200 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/30";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
        tone,
      )}
      title="Điểm rủi ro (0-100)"
    >
      Rủi ro {score}
    </span>
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
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-ink-200 bg-white/90 px-4 backdrop-blur dark:border-ink-700 dark:bg-ink-900/90 sm:px-6">
      <button
        type="button"
        className="btn-ghost p-2 lg:hidden"
        onClick={onOpenSidebar}
        aria-label="Mở menu"
      >
        <IconMenu className="h-5 w-5" />
      </button>

      <div className="min-w-0 flex-1">
        <h2 className="truncate text-sm font-semibold text-ink-900 dark:text-ink-100 sm:text-base">
          {getPageTitle(pathname)}
        </h2>
        {!token && (
          <p className="hidden text-xs text-amber-600 dark:text-amber-400 sm:block">
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

        <div className="hidden items-center gap-2 md:flex">
          <div className="rounded-lg bg-ink-50 px-3 py-1.5 text-right dark:bg-ink-800/80">
            <p className="text-[10px] uppercase tracking-wide text-ink-400 dark:text-ink-500">NAV</p>
            <p className="text-sm font-bold text-ink-900 dark:text-ink-100">
              {nav !== null ? formatCompactVND(nav) : "—"}
            </p>
          </div>
          <div className="rounded-lg bg-ink-50 px-3 py-1.5 text-right dark:bg-ink-800/80">
            <p className="text-[10px] uppercase tracking-wide text-ink-400 dark:text-ink-500">Cash</p>
            <p className="text-sm font-bold text-ink-900 dark:text-ink-100">
              {cash !== null ? formatCompactVND(cash) : "—"}
            </p>
          </div>
          {risk !== null && <RiskBadge score={risk} />}
        </div>

        <UserMenu />
      </div>
    </header>
  );
}
