/**
 * AuthProvider — component client gắn ở Root Layout để hydrate phiên đăng nhập
 * (khôi phục token + user từ localStorage) sau khi mount.
 */
"use client";

import { useEffect } from "react";

import { useAuthStore } from "@/store/useAuthStore";

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  useEffect(() => {
    useAuthStore.getState().hydrate();
  }, []);

  return <>{children}</>;
}
