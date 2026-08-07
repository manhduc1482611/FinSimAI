/**
 * Giao diện Admin — quản trị toàn hệ thống (FR-9, FR-10).
 * Chỉ `admin` vào được; admin không cần truy cập sàn giao dịch.
 */
"use client";

import { RoleGuard } from "@/components/common/RoleGuard";
import { PortalShell } from "@/components/layout/PortalShell";
import { ADMIN_NAV_GROUPS } from "@/components/layout/portalNav";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard allow={["admin"]}>
      <PortalShell
        groups={ADMIN_NAV_GROUPS}
        homeHref="/admin/users"
        label="Quản trị hệ thống"
      >
        {children}
      </PortalShell>
    </RoleGuard>
  );
}
