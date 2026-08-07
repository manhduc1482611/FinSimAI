/**
 * PortalShell — khung giao diện riêng cho host/admin: Sidebar theo role +
 * header gọn (tiêu đề + theme + UserMenu) + vùng nội dung.
 */
"use client";

import { useState } from "react";

import { IconMenu, IconMoon, IconSun } from "@/components/common/Icon";
import { useTheme } from "@/components/common/ThemeProvider";
import { Sidebar, type NavGroup } from "@/components/layout/Sidebar";
import { UserMenu } from "@/components/layout/UserMenu";

export interface PortalShellProps {
  /** Nav hiển thị trong sidebar (theo role). */
  groups: NavGroup[];
  /** Trang khi bấm logo. */
  homeHref: string;
  /** Nhãn trạng thái cố định trên header. */
  label: string;
  children: React.ReactNode;
}

export function PortalShell({ groups, homeHref, label, children }: PortalShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen bg-ink-50 dark:bg-ink-900">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        groups={groups}
        homeHref={homeHref}
      />
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-ink-200 bg-white/90 px-4 backdrop-blur dark:border-ink-700 dark:bg-ink-900/90 sm:px-6">
          <button
            type="button"
            className="btn-ghost p-2 lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Mở menu"
          >
            <IconMenu className="h-5 w-5" />
          </button>

          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold text-ink-900 dark:text-ink-100 sm:text-base">
              {label}
            </h2>
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
            <UserMenu />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
