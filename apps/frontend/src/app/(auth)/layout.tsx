/** Auth layout — khung trung tâm cho trang Đăng nhập / Đăng ký. */
import Link from "next/link";

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col bg-ink-50">
      <header className="flex h-16 items-center border-b border-ink-200 bg-white px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-black text-white">
            F
          </span>
          <span className="text-base font-bold text-ink-900">
            FinSim<span className="text-brand-600">AI</span>
          </span>
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">{children}</div>
      </main>
      <footer className="py-6 text-center text-xs text-ink-400">
        Môi trường mô phỏng — không phải lời khuyên đầu tư thật.
      </footer>
    </div>
  );
}
