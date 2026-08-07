/**
 * Giao diện Host — quản lý cuộc thi của mình (FR-9).
 * Chỉ `host`/`admin` vào được; sai role → redirect về trang của role mình.
 */
"use client";

import { RoleGuard } from "@/components/common/RoleGuard";
import { PortalShell } from "@/components/layout/PortalShell";
import { HOST_NAV_GROUPS } from "@/components/layout/portalNav";

export default function HostLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGuard allow={["host", "admin"]}>
      <PortalShell
        groups={HOST_NAV_GROUPS}
        homeHref="/host/contests"
        label="Quản lý cuộc thi"
      >
        {children}
      </PortalShell>
    </RoleGuard>
  );
}
