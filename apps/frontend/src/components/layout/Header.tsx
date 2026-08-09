/**
 * Header — thanh trên cùng của dashboard (mặt quầy).
 * Hiển thị: menu mobile + tiêu đề trang · board NAV/Cash/Rủi ro · UserMenu.
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
  { pattern: "/dashboard", title: "Bảng điều khiển" },
  { pattern: "/contests", title: "Cuộc thi" },
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
      title="Điểm rủi ro (0-100)"
    >
      RỦI RO {score}
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
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-[#FFFDF8]/90 px-4 backdrop-blur dark:border-granite-800 dark:bg-granite-950/85 sm:px-6">
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

        <div className="hidden items-center gap-2 md:flex">
          <CounterMetric label="NAV" value={nav !== null ? formatCompactVND(nav) : "—"} />
          <CounterMetric label="Cash" value={cash !== null ? formatCompactVND(cash) : "—"} />
          {risk !== null && <RiskBadge score={risk} />}
        </div>

        <UserMenu />
      </div>
    </header>
  );
}
