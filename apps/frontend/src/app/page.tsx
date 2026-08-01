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

  useEffect(() => {
    if (token) {
      router.replace("/news");
    }
  }, [token, router]);

  return (
    <div className="min-h-screen bg-ink-50">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-black text-white">
              F
            </span>
            <span className="text-base font-bold text-ink-900">
              FinSim<span className="text-brand-600">AI</span>
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
          <p className="mx-auto inline-block rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 ring-1 ring-inset ring-brand-200">
            Môi trường mô phỏng · Thời gian nén 1 phút = N ngày
          </p>
          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
            Luyện giao dịch không cần{" "}
            <span className="text-brand-600">mất tiền thật</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-ink-600">
            Đọc tin tức, phân tích doanh nghiệp, đặt lệnh và học hỏi từ AI Mentor
            phản biện theo phương pháp Socratic — tất cả trong một môi trường
            mô phỏng an toàn.
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
                className="card group p-6 transition-shadow hover:shadow-md"
              >
                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-semibold text-ink-900 group-hover:text-brand-700">
                  {feature.title}
                </h3>
                <p className="mt-1 text-sm text-ink-500">{feature.description}</p>
              </Link>
            );
          })}
        </section>
      </main>

      <footer className="border-t border-ink-200 bg-white py-6 text-center text-xs text-ink-400">
        FinSimAI © 2026 — Môi trường mô phỏng, không phải lời khuyên đầu tư thật.
      </footer>
    </div>
  );
}
