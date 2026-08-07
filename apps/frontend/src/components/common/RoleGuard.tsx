/**
 * RoleGuard — chặn truy cập route group theo role (FR-9).
 * - Chưa đăng nhập → về `/login`.
 * - Sai role → về trang chủ của role mình.
 * - Đang tải user (hydrate) → hiện spinner, tránh redirect sai.
 */
"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Spinner } from "@/components/common/Spinner";
import { useAuthStore } from "@/store/useAuthStore";
import { homePathForRole, type AppRole } from "@/utils/roles";

export interface RoleGuardProps {
  allow: AppRole[];
  children: ReactNode;
}

export function RoleGuard({ allow, children }: RoleGuardProps) {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const status = useAuthStore((state) => state.status);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    if (status === "loading" || user === null) {
      return;
    }
    if (!allow.includes(user.role as AppRole)) {
      router.replace(homePathForRole(user.role));
    }
  }, [allow, router, status, token, user]);

  const loading = !token || status === "loading" || user === null;
  const denied = !loading && !allow.includes(user.role as AppRole);

  if (loading || denied) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-ink-50 dark:bg-ink-900">
        <Spinner size="lg" />
        <p className="text-sm text-ink-400 dark:text-ink-500">Đang tải...</p>
      </div>
    );
  }

  return <>{children}</>;
}
