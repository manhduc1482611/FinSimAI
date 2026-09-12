/** Layout chung cho khu vực dashboard (sau đăng nhập). */
import { AppShell } from "@/components/layout/AppShell";
import { FloatingMentor } from "@/components/mentor/FloatingMentor";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell>
      {children}
      <FloatingMentor />
    </AppShell>
  );
}
