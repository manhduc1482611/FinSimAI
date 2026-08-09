import type { Metadata } from "next";

import { AuthProvider } from "@/components/common/AuthProvider";
import { ThemeProvider } from "@/components/common/ThemeProvider";
import { ToastHost } from "@/components/common/ToastHost";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "FinSimAI — Mô phỏng thị trường chứng khoán & AI Mentor",
    template: "%s · FinSimAI",
  },
  description:
    "Nền tảng luyện tập đầu tư chứng khoán trong môi trường mô phỏng thời gian nén, với AI Mentor phản biện theo phương pháp Socratic.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        {/* impeccable:world quay-giao-dich
        THESIS: FinSimAI is a transaction counter — the app is the branch, and every action is a giao dịch to be filled, stamped, and counted. It refuses the generic light fintech panel and the neon crypto terminal both at once.
        OWN-WORLD: warm granite ground, paper slips as content, brass gold as the only brand accent, mono numerals on inset rate boards, VN green/red market lights, queue tickets and confirmation stamps.
        STORY: the visitor queues up, reads the market on the boards, fills a slip to trade, gets questioned by the teller before a risky order, and walks away with a stamped receipt.
        FIRST VIEWPORT: brass rail on the left with ticket nav; above, a counter display of NAV / Cash / Rủi ro in mono on boards; center, queue tickets of today's discipline state and department slips leading into Đọc báo first.
        FORM: candidate 6 of the grounded list — Quầy giao dịch (bank transaction counter); seed key 4ce2d1de.
        FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
        */}
        <ThemeProvider>
          <AuthProvider>
            {children}
            <ToastHost />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
