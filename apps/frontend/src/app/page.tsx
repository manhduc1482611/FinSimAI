/**
 * Landing page — trang chủ. Nếu đã đăng nhập → chuyển thẳng vào `/news`.
 * Cấu trúc: header gọn → hero (headline ngắt dòng chủ động + USP thời gian nén)
 * → mockup sản phẩm → hành trình 5 bước → footer.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  IconBook,
  IconBuilding,
  IconMentor,
  IconNews,
  IconChevronRight,
  IconTrade,
} from "@/components/common/Icon";
import ProductShowcase from "@/components/landing/ProductShowcase";
import { useAuthStore } from "@/store/useAuthStore";
import { homePathForRole } from "@/utils/roles";

const JOURNEY = [
  {
    no: "01",
    icon: IconNews,
    title: "Quan sát",
    description: "Đọc tin tức mô phỏng sinh từ bối cảnh thị trường thật.",
    href: "/news",
  },
  {
    no: "02",
    icon: IconBuilding,
    title: "Phân tích",
    description: "Soi sức khỏe tài chính, chỉ số và rủi ro của doanh nghiệp.",
    href: "/companies",
  },
  {
    no: "03",
    icon: IconMentor,
    title: "Phản biện",
    description: "AI Mentor Socratic đặt câu hỏi ngược, không mách nước.",
    href: "/trade/mentor",
  },
  {
    no: "04",
    icon: IconTrade,
    title: "Giao dịch",
    description: "Đặt lệnh trong thời gian nén, quản lý NAV và danh mục.",
    href: "/trade",
  },
  {
    no: "05",
    icon: IconBook,
    title: "Học & sửa sai",
    description: "Nhiệm vụ, check-in và rèn kỷ luật ngày qua ngày.",
    href: "/tasks",
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
      <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/80 dark:border-granite-700 dark:bg-granite-900/90 dark:supports-[backdrop-filter]:bg-granite-900/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="Capia" className="h-8 w-auto hover:opacity-80" />
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

      <main className="px-4 sm:px-6">
        <section className="mx-auto max-w-6xl pt-16 text-center sm:pt-20">
          <h1 className="mx-auto text-4xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-5xl lg:text-6xl">
            Luyện giao dịch không cần
            <br className="hidden sm:block" />{" "}
            <span className="text-brand-700 dark:text-brand-300">mất tiền thật</span>
          </h1>

          <div className="mx-auto mt-6 inline-flex items-center gap-2 rounded-full border border-line bg-paper px-4 py-2 dark:border-granite-700 dark:bg-granite-900">
            <span className="board-label text-ink-500 dark:text-granite-400">
              1 PHÚT THẬT
            </span>
            <IconChevronRight className="h-3.5 w-3.5 text-brand-700 dark:text-brand-300" />
            <span className="board-label text-brand-700 dark:text-brand-300">
              NHIỀU NGÀY THỊ TRƯỜNG
            </span>
          </div>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-ink-500 dark:text-granite-300">
            Tin tức, doanh nghiệp, giá cả và tâm lý đám đông đều được AI mô phỏng
            từ bối cảnh thị trường thật. Trải qua cả một nhịp thị trường trong vài
            phút, đọc, quyết định và học từ chính sai lầm của mình — an toàn.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/register" className="btn-primary w-full px-7 py-3 text-base sm:w-auto">
              Bắt đầu mô phỏng
            </Link>
            <Link href="/login" className="btn-ghost w-full px-7 py-3 text-base sm:w-auto">
              Đăng nhập
            </Link>
          </div>

          <ProductShowcase />
        </section>

        <section id="cach-hoat-dong" className="mx-auto max-w-6xl scroll-mt-24 pt-24">
          <h2 className="text-center text-2xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-3xl">
            Cách Capia giúp bạn rèn luyện
          </h2>
          <div className="relative mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <div
              aria-hidden
              className="absolute inset-x-0 top-10 hidden h-px bg-line lg:block dark:bg-granite-800"
            />
            {JOURNEY.map((step) => {
              const Icon = step.icon;
              return (
                <Link
                  key={step.no}
                  href={step.href}
                  className="group relative flex flex-col rounded-xl border border-transparent p-4 transition-colors hover:border-line hover:bg-paper/70 sm:items-start sm:text-left dark:hover:border-granite-700 dark:hover:bg-granite-900/70"
                >
                  <span className="board-label z-10 text-brand-700 dark:text-brand-300">
                    {step.no}
                  </span>
                  <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-700 dark:text-brand-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-3 text-sm font-black text-ink-900 group-hover:text-brand-700 dark:text-slip dark:group-hover:text-brand-300">
                    {step.title}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-ink-500 dark:text-granite-400">
                    {step.description}
                  </p>
                </Link>
              );
            })}
          </div>

          <div className="mt-12 text-center">
            <Link href="/register" className="btn-secondary px-7 py-3 text-base">
              Bước vào sàn — miễn phí
            </Link>
          </div>
        </section>
      </main>

      <footer className="mt-24 border-t border-line bg-paper dark:border-granite-700 dark:bg-granite-900">
        <div className="mx-auto max-w-6xl grid gap-8 px-4 py-12 sm:grid-cols-[1.4fr_repeat(3,1fr)] sm:px-6">
          <div>
            <img src="/logo.png" alt="Capia" className="h-7 w-auto" />
            <p className="mt-2 max-w-xs text-xs leading-relaxed text-ink-500 dark:text-granite-400">
              Môi trường mô phỏng giao dịch với thời gian nén, dữ liệu AI và AI
              Mentor Socratic — nơi bạn rèn kỷ luật trước khi chạm tiền thật.
            </p>
          </div>
          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Khám phá</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/news" className="hover:text-brand-700 dark:hover:text-brand-300">Tin tức</Link>
              </li>
              <li>
                <Link href="/companies" className="hover:text-brand-700 dark:hover:text-brand-300">Doanh nghiệp</Link>
              </li>
              <li>
                <Link href="/social" className="hover:text-brand-700 dark:hover:text-brand-300">Cộng đồng</Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Hành trình</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/trade" className="hover:text-brand-700 dark:hover:text-brand-300">Giao dịch</Link>
              </li>
              <li>
                <Link href="/trade/mentor" className="hover:text-brand-700 dark:hover:text-brand-300">AI Mentor</Link>
              </li>
              <li>
                <Link href="/tasks" className="hover:text-brand-700 dark:hover:text-brand-300">Nhiệm vụ</Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Tài khoản</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/register" className="hover:text-brand-700 dark:hover:text-brand-300">Đăng ký</Link>
              </li>
              <li>
                <Link href="/login" className="hover:text-brand-700 dark:hover:text-brand-300">Đăng nhập</Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-line py-4 text-center text-xs text-ink-400 dark:border-granite-800 dark:text-granite-500">
          Capia © 2026 — Môi trường mô phỏng, không phải lời khuyên đầu tư thật.
        </div>
      </footer>
    </div>
  );
}