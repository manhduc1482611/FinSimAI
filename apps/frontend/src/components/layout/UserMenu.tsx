/**
 * UserMenu — menu tài khoản (avatar + tên + dropdown). Đóng khi click ra ngoài.
 */
"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { IconChevronDown, IconLogout, IconUser } from "@/components/common/Icon";
import { useAuthStore } from "@/store/useAuthStore";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

export function UserMenu() {
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const logout = useAuthStore((state) => state.logout);

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current !== null &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user || !token) {
    return (
      <Link href="/login" className="btn-primary px-3 py-1.5 text-xs">
        Đăng nhập
      </Link>
    );
  }

  const displayName = user.display_name ?? user.username;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg p-1.5 transition-colors hover:bg-ink-100 dark:hover:bg-granite-800"
      >
        {user.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={user.avatar_url}
            alt={displayName}
            className="h-8 w-8 rounded-full object-cover"
          />
        ) : (
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 text-granite-950">
            <IconUser className="h-4 w-4" />
          </span>
        )}
        <span className="hidden text-left sm:block">
          <span className="block max-w-[10rem] truncate text-sm font-medium text-ink-900 dark:text-slip">
            {displayName}
          </span>
          <span className="block font-mono text-xs text-ink-500 dark:text-granite-300">
            {formatCompactVND(parseDecimal(user.cash_balance))}
          </span>
        </span>
        <IconChevronDown
          className={cn("h-4 w-4 text-ink-400 transition-transform dark:text-granite-300", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-64 overflow-hidden rounded-xl border border-ink-200 bg-[#FFFDF8] shadow-card dark:border-granite-700 dark:bg-granite-900"
        >
          <div className="border-b border-line bg-slip px-4 py-3 dark:border-granite-700 dark:bg-granite-950">
            <p className="text-sm font-semibold text-ink-900 dark:text-slip">{displayName}</p>
            <p className="truncate text-xs text-ink-500 dark:text-granite-300">@{user.username}</p>
            <p className="mt-1 text-xs text-ink-600 dark:text-granite-300">
              {user.email}
            </p>
          </div>
          <div className="p-2">
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-mkt-down transition-colors hover:bg-mkt-down/10 dark:text-mkt-down-400 dark:hover:bg-mkt-down-400/10"
              onClick={() => {
                setOpen(false);
                logout();
              }}
            >
              <IconLogout className="h-4 w-4" />
              Đăng xuất
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
