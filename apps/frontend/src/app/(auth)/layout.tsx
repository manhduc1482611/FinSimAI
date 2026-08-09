/** Auth layout — khung trung tâm cho trang Đăng nhập / Đăng ký. */
import Link from "next/link";

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col bg-slip dark:bg-granite-950">
      <header className="flex h-16 items-center border-b border-line bg-[#FFFDF8] px-6 dark:border-granite-700 dark:bg-granite-900">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 text-sm font-black text-granite-950 shadow-board">
            F
          </span>
          <span className="text-base font-black text-ink-900 dark:text-slip">
            FinSim<span className="text-brand-700 dark:text-brand-300">AI</span>
          </span>
        </Link>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">{children}</div>
      </main>
      <footer className="py-6 text-center text-xs text-ink-400 dark:text-granite-400">
        Môi trường mô phỏng — không phải lời khuyên đầu tư thật.
      </footer>
    </div>
  );
}
