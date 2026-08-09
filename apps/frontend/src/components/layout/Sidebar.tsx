/**
 * Sidebar — thanh điều hướng chính (bám theo hành trình người dùng).
 * Desktop: cố định trái. Mobile: trượt off-canvas + backdrop.
 * Chất liệu: thanh đồng thau (brass rail) — nhóm điều hướng là biển báo, mục active là vé đồng.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  IconBuilding,
  IconClose,
  IconHome,
  IconMentor,
  IconNews,
  IconSocial,
  IconTrade,
  IconTrophy,
} from "@/components/common/Icon";
import { cn } from "@/utils/cn";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

export interface NavGroup {
  section: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    section: "Tổng quan",
    items: [
      {
        href: "/dashboard",
        label: "Bảng điều khiển",
        description: "Tổng quan & cuộc thi",
        icon: IconHome,
      },
      {
        href: "/tasks",
        label: "Nhiệm vụ",
        description: "Điểm danh & nhận thưởng",
        icon: IconTrophy,
      },
    ],
  },
  {
    section: "Khám phá",
    items: [
      {
        href: "/news",
        label: "Tin tức",
        description: "Cảm xúc thị trường",
        icon: IconNews,
      },
      {
        href: "/companies",
        label: "Doanh nghiệp",
        description: "Phân tích cơ bản",
        icon: IconBuilding,
      },
    ],
  },
  {
    section: "Thực chiến",
    items: [
      {
        href: "/trade",
        label: "Giao dịch",
        description: "Đặt lệnh & danh mục",
        icon: IconTrade,
      },
      {
        href: "/trade/mentor",
        label: "Mentor",
        description: "Hỏi - đáp phản biện",
        icon: IconMentor,
      },
    ],
  },
  {
    section: "Cộng đồng",
    items: [
      {
        href: "/social",
        label: "Xã hội",
        description: "Heatmap & bài viết",
        icon: IconSocial,
      },
    ],
  },
];

export interface SidebarProps {
  open: boolean;
  onClose: () => void;
  /** Nav theo role (mặc định: NAV_GROUPS của người dùng). */
  groups?: NavGroup[];
  /** Trang khi bấm logo (mặc định `/`). */
  homeHref?: string;
}

export function Sidebar({ open, onClose, groups, homeHref }: SidebarProps) {
  const pathname = usePathname();
  const navGroups = groups ?? NAV_GROUPS;
  const logoHref = homeHref ?? "/";

  const isActive = (href: string): boolean => {
    if (href === "/trade") {
      return pathname === "/trade";
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <>
      {/* Backdrop mobile */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-granite-950/60 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-ink-200 bg-[#FFFDF8] transition-transform duration-200 dark:border-granite-800 dark:bg-granite-950",
          "lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-line px-5 dark:border-granite-800">
          <Link href={logoHref} className="group flex items-center gap-2.5" onClick={onClose}>
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-brand-500 text-sm font-black text-granite-950 shadow-board transition-colors group-hover:bg-brand-400">
              F
            </span>
            <span className="leading-tight">
              <span className="block text-base font-black tracking-tight text-ink-900 dark:text-slip">
                FinSim<span className="text-brand-600 dark:text-brand-400">AI</span>
              </span>
              <span className="board-label block">Quầy giao dịch</span>
            </span>
          </Link>
          <button
            type="button"
            className="btn-ghost p-1.5 lg:hidden"
            onClick={onClose}
            aria-label="Đóng menu"
          >
            <IconClose className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.section} className="mb-5">
              <p className="board-label px-2 pb-2">{group.section}</p>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const active = isActive(item.href);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "group flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors",
                          active
                            ? "bg-brand-500 text-granite-950 shadow-board"
                            : "text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-granite-200 dark:hover:bg-granite-800 dark:hover:text-slip",
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-5 w-5 shrink-0",
                            active
                              ? "text-granite-950"
                              : "text-ink-400 group-hover:text-ink-600 dark:text-granite-400 dark:group-hover:text-granite-200",
                          )}
                        />
                        <span className="min-w-0">
                          <span className="block truncate font-semibold">{item.label}</span>
                          <span
                            className={cn(
                              "block truncate text-xs",
                              active
                                ? "text-granite-900/80"
                                : "text-ink-400 dark:text-granite-400",
                            )}
                          >
                            {item.description}
                          </span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-ink-200 px-5 py-4 dark:border-granite-800">
          <p className="board-label">Môi trường mô phỏng · v0.1.0</p>
        </div>
      </aside>
    </>
  );
}
