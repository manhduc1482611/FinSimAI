/**
 * Landing page — trang chủ. Nếu đã đăng nhập → chuyển thẳng vào `/news`.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  IconBuilding,
  IconMentor,
  IconNews,
  IconSocial,
  IconTrade,
} from "@/components/common/Icon";
import { useAuthStore } from "@/store/useAuthStore";
import { homePathForRole } from "@/utils/roles";

const FEATURES = [
  {
    icon: IconNews,
    title: "Tin tức & Cảm xúc",
    description: "Theo dõi tin tức mô phỏng kèm sentiment và mức tác động tới thị trường.",
    href: "/news",
  },
  {
    icon: IconBuilding,
    title: "Phân tích doanh nghiệp",
    description: "Sức khỏe tài chính, P/E, ROE, biên lợi nhuận của từng công ty.",
    href: "/companies",
  },
  {
    icon: IconTrade,
    title: "Giao dịch thực chiến",
    description: "Đặt lệnh market/limit, quản lý danh mục và NAV trong thời gian nén.",
    href: "/trade",
  },
  {
    icon: IconMentor,
    title: "AI Mentor Socratic",
    description: "Đặt câu hỏi ngược để bạn tự kiểm chứng quyết định trước khi giao dịch.",
    href: "/trade/mentor",
  },
  {
    icon: IconSocial,
    title: "Cộng đồng & Heatmap",
    description: "Quan sát tâm lý đám đông và sức lan truyền của các bài viết.",
    href: "/social",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    if (token) {
      router.replace(homePathForRole(user?.role));
    }
  }, [token, user, router]);

  return (
    <div className="min-h-screen bg-slip dark:bg-granite-950">
      <header className="border-b border-line bg-[#FFFDF8] dark:border-granite-700 dark:bg-granite-900">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 text-sm font-black text-granite-950 shadow-board">
              F
            </span>
            <span className="text-base font-black text-ink-900 dark:text-slip">
              FinSim<span className="text-brand-700 dark:text-brand-300">AI</span>
            </span>
          </div>
          <nav className="flex items-center gap-3">
            <Link href="/login" className="btn-ghost">
              Đăng nhập
            </Link>
            <Link href="/register" className="btn-primary">
              Đăng ký
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <section className="text-center">
          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-5xl">
            Luyện giao dịch không cần{" "}
            <span className="text-brand-700 dark:text-brand-300">mất tiền thật</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-ink-600 dark:text-granite-300">
            Môi trường mô phỏng với thời gian nén: 1 phút trôi qua là nhiều ngày.
            Đọc tin tức, phân tích doanh nghiệp, đặt lệnh và học hỏi từ AI Mentor
            phản biện theo phương pháp Socratic — tất cả an toàn.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Link href="/register" className="btn-primary px-6 py-3 text-base">
              Bắt đầu luyện tập
            </Link>
            <Link href="/login" className="btn-secondary px-6 py-3 text-base">
              Tôi đã có tài khoản
            </Link>
          </div>
        </section>

        <section className="mt-20 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <Link
                key={feature.title}
                href={feature.href}
                className="card group p-6 transition-shadow hover:shadow-card"
              >
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-700 dark:text-brand-300">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-black text-ink-900 group-hover:text-brand-700 dark:text-slip dark:group-hover:text-brand-300">
                  {feature.title}
                </h3>
                <p className="mt-1 text-sm text-ink-500 dark:text-granite-400">{feature.description}</p>
              </Link>
            );
          })}
        </section>
      </main>

      <footer className="border-t border-line bg-[#FFFDF8] py-6 text-center text-xs text-ink-400 dark:border-granite-700 dark:bg-granite-900 dark:text-granite-400">
        FinSimAI © 2026 — Môi trường mô phỏng, không phải lời khuyên đầu tư thật.
      </footer>
    </div>
  );
}
