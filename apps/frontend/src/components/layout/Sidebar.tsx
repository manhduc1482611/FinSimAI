/**
 * Sidebar — thanh điều hướng chính (bám theo hành trình người dùng).
 * Desktop: cố định trái. Mobile: trượt off-canvas + backdrop.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  IconBuilding,
  IconClose,
  IconMentor,
  IconNews,
  IconSocial,
  IconTrade,
} from "@/components/common/Icon";
import { cn } from "@/utils/cn";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const NAV_GROUPS: Array<{ section: string; items: NavItem[] }> = [
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
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

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
          className="fixed inset-0 z-40 bg-ink-950/50 lg:hidden dark:bg-ink-950/70"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-ink-200 bg-white transition-transform duration-200 dark:border-ink-700 dark:bg-ink-900",
          "lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-ink-200 px-5 dark:border-ink-700">
          <Link href="/" className="flex items-center gap-2" onClick={onClose}>
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-black text-white">
              F
            </span>
            <span className="text-base font-bold text-ink-900 dark:text-ink-100">
              FinSim<span className="text-brand-600">AI</span>
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
          {NAV_GROUPS.map((group) => (
            <div key={group.section} className="mb-5">
              <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400 dark:text-ink-500">
                {group.section}
              </p>
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
                          "group flex items-center gap-3 rounded-lg px-2 py-2 text-sm transition-colors",
                          active
                            ? "bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-400"
                            : "text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-ink-300 dark:hover:bg-ink-800 dark:hover:text-ink-100",
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-5 w-5 shrink-0",
                            active
                              ? "text-brand-600 dark:text-brand-400"
                              : "text-ink-400 group-hover:text-ink-600 dark:text-ink-500 dark:group-hover:text-ink-300",
                          )}
                        />
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{item.label}</span>
                          <span className="block truncate text-xs text-ink-400 dark:text-ink-500">
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

        <div className="border-t border-ink-200 px-5 py-4 dark:border-ink-700">
          <p className="text-xs text-ink-400 dark:text-ink-500">
            Môi trường mô phỏng · <span className="font-medium text-ink-600 dark:text-ink-300">v0.1.0</span>
          </p>
        </div>
      </aside>
    </>
  );
}
