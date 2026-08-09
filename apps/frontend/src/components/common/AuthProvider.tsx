/**
 * AuthProvider — component client gắn ở Root Layout để hydrate phiên đăng nhập
 * (khôi phục token + user từ localStorage) sau khi mount, và đăng xuất toàn cục
 * khi API trả 401 (phiên hết hạn giữa chừng) → đưa về trang đăng nhập.
 */
"use client";

import { useEffect } from "react";

import { usePathname, useRouter } from "next/navigation";

import { useAuthStore } from "@/store/useAuthStore";

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    useAuthStore.getState().hydrate();
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      const state = useAuthStore.getState();
      if (!state.token) {
        return;
      }
      state.logout();
      if (pathname !== "/login") {
        router.push("/login");
      }
    };
    window.addEventListener("finsim:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("finsim:unauthorized", handleUnauthorized);
  }, [pathname, router]);

  return <>{children}</>;
}
