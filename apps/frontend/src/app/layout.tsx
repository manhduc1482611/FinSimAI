import type { Metadata } from "next";

import { AuthProvider } from "@/components/common/AuthProvider";
import { ThemeProvider } from "@/components/common/ThemeProvider";
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
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
