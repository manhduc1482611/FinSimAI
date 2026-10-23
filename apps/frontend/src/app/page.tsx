/**
 * Landing page — trang chủ dành cho khách ghé thăm (chưa đăng nhập).
 * Nếu đã đăng nhập → tự động chuyển vào dashboard tương ứng theo role.
 *
 * Cấu trúc:
 * 1. Header: Logo, điều hướng nhanh, theme switcher (Dark/Light), nút đăng nhập/đăng ký.
 * 2. Hero: Headline thời gian nén + CTA cấp vốn ảo 100tr + Terminal Mockup tương tác (mã chuẩn TECHA, FINB...).
 * 3. Bảng mã cổ phiếu mô phỏng: Giới thiệu hệ sinh thái 20 mã cổ phiếu giả lập của Capia.
 * 4. AI Mentor Socratic: Minh họa tính năng phản biện tâm lý giao dịch độc quyền.
 * 5. Hành trình 5 bước: Quan sát → Phân tích → Phản biện → Giao dịch → Sửa sai.
 * 6. CTA Cuối trang & Footer đầy đủ.
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
  IconSun,
  IconMoon,
  IconChat,
  IconRisk,
  IconCheck,
  IconWallet,
  IconEye,
} from "@/components/common/Icon";
import { useTheme } from "@/components/common/ThemeProvider";
import ProductShowcase from "@/components/landing/ProductShowcase";
import { useAuthStore } from "@/store/useAuthStore";
import { homePathForRole } from "@/utils/roles";

const SIMULATED_STOCKS_PREVIEW = [
  {
    symbol: "TECHA",
    name: "TechVision Corp",
    sector: "Công nghệ",
    sectorBadge: "Technology",
    price: "156.80",
    change: "+2.4%",
    up: true,
    pe: "24.5",
    desc: "Nền tảng phân tích AI doanh nghiệp và học máy cho tài chính.",
  },
  {
    symbol: "TECHB",
    name: "CloudSync Inc",
    sector: "Công nghệ",
    sectorBadge: "Technology",
    price: "89.40",
    change: "+1.8%",
    up: true,
    pe: "35.1",
    desc: "Hạ tầng đám mây và giải pháp đồng bộ dữ liệu thời gian thực.",
  },
  {
    symbol: "FINA",
    name: "BlueRock Financial",
    sector: "Tài chính",
    sectorBadge: "Financial",
    price: "45.60",
    change: "+1.2%",
    up: true,
    pe: "11.2",
    desc: "Tập đoàn ngân hàng đầu tư và quản lý tài sản lớn.",
  },
  {
    symbol: "FINB",
    name: "NovaPay Holdings",
    sector: "Tài chính",
    sectorBadge: "Financial",
    price: "72.30",
    change: "+3.1%",
    up: true,
    pe: "28.6",
    desc: "Nền tảng thanh toán số và hạ tầng công nghệ tài chính (FinTech).",
  },
  {
    symbol: "HEALA",
    name: "BioGenix Therapeutics",
    sector: "Y tế & Dược",
    sectorBadge: "Healthcare",
    price: "128.90",
    change: "+4.5%",
    up: true,
    pe: "N/A",
    desc: "Công nghệ sinh học đột phá chuyên trị liệu phân tử mRNA.",
  },
  {
    symbol: "ENERGA",
    name: "GreenHydrogen Energy",
    sector: "Năng lượng",
    sectorBadge: "Energy",
    price: "18.75",
    change: "-2.3%",
    up: false,
    pe: "N/A",
    desc: "Sản xuất hydro xanh và phát triển pin nhiên liệu tái tạo.",
  },
  {
    symbol: "CONSMA",
    name: "Premier Brands Group",
    sector: "Tiêu dùng",
    sectorBadge: "Consumer Goods",
    price: "63.50",
    change: "+1.5%",
    up: true,
    pe: "18.3",
    desc: "Tập đoàn hàng tiêu dùng nhanh (FMCG) chuỗi phân phối đa quốc gia.",
  },
  {
    symbol: "INDUSA",
    name: "AeroDynamics Inc",
    sector: "Công nghiệp",
    sectorBadge: "Industrial",
    price: "187.40",
    change: "+2.0%",
    up: true,
    pe: "20.1",
    desc: "Sản xuất linh kiện hàng không vũ trụ và giải pháp tự động hóa.",
  },
];

const JOURNEY = [
  {
    no: "01",
    icon: IconNews,
    title: "Quan sát tin tức",
    description: "Đọc tin tức mô phỏng được AI tạo từ sự kiện kinh tế thật, cảm xúc xã hội và xu hướng thị trường.",
    href: "/news",
  },
  {
    no: "02",
    icon: IconBuilding,
    title: "Phân tích doanh nghiệp",
    description: "Soi báo cáo tài chính, chỉ số P/E, ROE, sức khỏe tài chính của 20 mã cổ phiếu (TECHA, FINB...).",
    href: "/companies",
  },
  {
    no: "03",
    icon: IconMentor,
    title: "Phản biện Socratic",
    description: "AI Mentor hỏi ngược trước mọi lệnh mua/bán, vạch trần bẫy tâm lý FOMO và quản trị rủi ro chặt chẽ.",
    href: "/trade/mentor",
  },
  {
    no: "04",
    icon: IconTrade,
    title: "Bàn giao dịch nén",
    description: "Đặt lệnh Mua/Bán theo biểu đồ nến real-time, trải nghiệm chu kỳ thị trường nhiều tháng chỉ trong 30 phút.",
    href: "/trade",
  },
  {
    no: "05",
    icon: IconBook,
    title: "Rèn điểm kỷ luật",
    description: "Chấm điểm kỷ luật thay vì chỉ đếm lợi nhuận ảo. Hoàn thành nhiệm vụ ngày để xây dựng bản lĩnh nhà đầu tư.",
    href: "/tasks",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    if (token) {
      router.replace(homePathForRole(user?.role));
    }
  }, [token, user, router]);

  return (
    <div className="min-h-screen bg-slip dark:bg-granite-950 transition-colors">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/80 dark:border-granite-800 dark:bg-granite-900/90 dark:supports-[backdrop-filter]:bg-granite-900/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2 group" aria-label="Trang chủ Capia">
              <img src="/logo.png" alt="Capia" className="h-8 w-auto transition-transform group-hover:scale-105" />
            </Link>

            {/* Điều hướng nhanh cho khách vãng lai */}
            <nav className="hidden md:flex items-center gap-6 text-sm font-semibold text-ink-600 dark:text-granite-300">
              <a href="#ma-chung-khoan" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                Mã cổ phiếu
              </a>
              <a href="#ai-mentor" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                AI Mentor
              </a>
              <a href="#cach-hoat-dong" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                Cách hoạt động
              </a>
              <Link href="/trade" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                Bàn giao dịch
              </Link>
              <Link href="/companies" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                Doanh nghiệp
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            {/* Nút bật/tắt giao diện sáng/tối */}
            <button
              type="button"
              onClick={toggleTheme}
              className="btn-ghost p-2 rounded-lg text-ink-600 hover:text-ink-900 dark:text-granite-300 dark:hover:text-slip"
              title={`Chuyển sang giao diện ${theme === "dark" ? "sáng" : "tối"}`}
              aria-label="Đổi giao diện sáng tối"
            >
              {theme === "dark" ? <IconSun className="h-4 w-4" /> : <IconMoon className="h-4 w-4" />}
            </button>

            <Link href="/register" className="btn-primary text-sm shadow-sm">
              Đăng ký miễn phí
            </Link>
          </div>
        </div>
      </header>

      <main className="px-4 sm:px-6">
        {/* Hero Section */}
        <section className="mx-auto max-w-6xl pt-14 text-center sm:pt-20">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-line bg-paper px-4 py-1.5 dark:border-granite-700 dark:bg-granite-900 shadow-sm">
            <span className="board-label text-ink-500 dark:text-granite-400">
              1 PHÚT THẬT
            </span>
            <IconChevronRight className="h-3.5 w-3.5 text-brand-700 dark:text-brand-300" />
            <span className="board-label font-bold text-brand-700 dark:text-brand-300">
              NHIỀU NGÀY THỊ TRƯỜNG
            </span>
          </div>

          <h1 className="mx-auto mt-6 text-4xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-5xl lg:text-6xl max-w-4xl leading-[1.15]">
            Luyện giao dịch chứng khoán
            <br />
            <span className="text-brand-700 dark:text-brand-400">không cần mất tiền thật</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-ink-600 dark:text-granite-300">
            Tin tức, 20 doanh nghiệp mô phỏng (TECHA, FINB, HEALA...), giá cổ phiếu và tâm lý đám đông đều được AI tính toán theo mô hình thị trường khép kín. Trải qua cả một chu kỳ thị trường trong vài phút, đọc tin, quyết định và rèn kỷ luật an toàn tuyệt đối.
          </p>

          {/* CTA Buttons */}
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/news"
              className="btn-secondary w-full px-6 py-3 text-base sm:w-auto flex items-center justify-center gap-2 border-2 border-brand-500/40 hover:border-brand-500 font-bold shadow-sm"
            >
              <IconEye className="h-5 w-5 text-brand-700 dark:text-brand-300" />
              Vào xem web (Không cần đăng nhập)
            </Link>
            <Link href="/register" className="btn-primary w-full px-7 py-3 text-base sm:w-auto shadow-md">
              Bắt đầu mô phỏng (Cấp vốn 100tr)
            </Link>
            <Link href="/login" className="btn-ghost w-full px-6 py-3 text-base sm:w-auto">
              Đăng nhập
            </Link>
          </div>
          <p className="mt-3 text-xs text-ink-500 dark:text-granite-400">
            Khách có thể xem tin tức, doanh nghiệp & mạng xã hội. Biểu đồ nến real-time & AI Mentor yêu cầu đăng nhập.
          </p>

          {/* Trust & Key Features Badges */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-xs font-semibold text-ink-600 dark:text-granite-400">
            <span className="flex items-center gap-1.5 rounded-full border border-line bg-paper/80 px-3.5 py-1.5 dark:border-granite-800 dark:bg-granite-900/80">
              <IconWallet className="h-4 w-4 text-brand-600 dark:text-brand-400" />
              100.000.000 ₫ Vốn ảo khởi tạo
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-line bg-paper/80 px-3.5 py-1.5 dark:border-granite-800 dark:bg-granite-900/80">
              <IconMentor className="h-4 w-4 text-accent" />
              AI Mentor phản biện Socratic
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-line bg-paper/80 px-3.5 py-1.5 dark:border-granite-800 dark:bg-granite-900/80">
              <IconTrade className="h-4 w-4 text-mkt-up" />
              20 mã cổ phiếu giả lập hoàn chỉnh
            </span>
            <span className="flex items-center gap-1.5 rounded-full border border-line bg-paper/80 px-3.5 py-1.5 dark:border-granite-800 dark:bg-granite-900/80">
              <IconRisk className="h-4 w-4 text-brand-600 dark:text-brand-400" />
              Chấm điểm kỷ luật & rủi ro
            </span>
          </div>

          {/* Interactive Showcase Mockup with real tickers */}
          <ProductShowcase />
        </section>

        {/* Section 2: Danh sách các mã cổ phiếu mô phỏng trên Capia */}
        <section id="ma-chung-khoan" className="mx-auto max-w-6xl scroll-mt-24 pt-28">
          <div className="text-center max-w-3xl mx-auto">
            <span className="board-label text-brand-700 dark:text-brand-300">
              HỆ SINH THÁI DOANH NGHIỆP MÔ PHỎNG
            </span>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-3xl lg:text-4xl">
              20 mã cổ phiếu mô phỏng đa ngành
            </h2>
            <p className="mt-3 text-sm sm:text-base text-ink-600 dark:text-granite-300 leading-relaxed">
              Khác với các sàn dùng dữ liệu quá khứ, Capia xây dựng một vũ trụ 20 doanh nghiệp với mã cổ phiếu riêng biệt (TECHA, TECHB, FINA, FINB...), đầy đủ báo cáo tài chính, chỉ số P/E, ROE và tin tức nội bộ do AI sinh liên tục.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {SIMULATED_STOCKS_PREVIEW.map((item) => (
              <div
                key={item.symbol}
                className="group flex flex-col justify-between rounded-xl border border-line bg-paper p-4.5 shadow-sm transition-all hover:border-brand-500 hover:shadow-md dark:border-granite-800 dark:bg-granite-900 dark:hover:border-brand-400"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="board-num text-lg font-black text-ink-900 dark:text-slip group-hover:text-brand-700 dark:group-hover:text-brand-300">
                        {item.symbol}
                      </span>
                      <span className="ml-2 rounded bg-ink-100 px-1.5 py-0.5 text-[10px] font-bold text-ink-600 dark:bg-granite-800 dark:text-granite-300">
                        {item.sector}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="board-num text-sm font-bold text-ink-900 dark:text-slip">
                        {item.price}
                      </div>
                      <div
                        className={`board-num text-xs font-semibold ${
                          item.up ? "text-mkt-up" : "text-mkt-down"
                        }`}
                      >
                        {item.change}
                      </div>
                    </div>
                  </div>

                  <h3 className="mt-2 text-xs font-bold text-ink-700 dark:text-granite-200 truncate">
                    {item.name}
                  </h3>
                  <p className="mt-1 text-xs text-ink-500 dark:text-granite-400 line-clamp-2 leading-relaxed">
                    {item.desc}
                  </p>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-line pt-3 dark:border-granite-800">
                  <span className="text-[11px] font-mono text-ink-400 dark:text-granite-500">
                    P/E: <strong className="text-ink-700 dark:text-granite-300">{item.pe}</strong>
                  </span>
                  <Link
                    href={`/companies`}
                    className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline dark:text-brand-300"
                  >
                    <span>Xem hồ sơ</span>
                    <IconChevronRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            ))}
          </div>

          {/* Lời nhắn cho khách ghé thăm */}
          <div className="mt-8 rounded-2xl border border-brand-500/30 bg-brand-500/10 p-5 text-center sm:flex sm:items-center sm:justify-between sm:text-left">
            <div>
              <h4 className="text-sm font-bold text-ink-900 dark:text-slip">
                Bạn có thể xem dữ liệu toàn bộ 20 doanh nghiệp mà không cần đăng nhập
              </h4>
              <p className="mt-0.5 text-xs text-ink-600 dark:text-granite-300">
                Xem sức khỏe tài chính, biểu đồ nến lịch sử và các sự kiện tin tức tác động đến từng mã.
              </p>
            </div>
            <Link
              href="/companies"
              className="btn-secondary mt-3 sm:mt-0 shrink-0 text-xs py-2 px-4"
            >
              Xem danh sách 20 công ty →
            </Link>
          </div>
        </section>

        {/* Section 3: AI Mentor Socratic */}
        <section id="ai-mentor" className="mx-auto max-w-6xl scroll-mt-24 pt-28">
          <div className="grid gap-8 lg:grid-cols-2 items-center">
            <div>
              <span className="board-label text-accent dark:text-accent-400">
                TÍNH NĂNG ĐẶC BIỆT
              </span>
              <h2 className="mt-2 text-2xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-3xl lg:text-4xl">
                AI Mentor Socratic — Người phản biện giao dịch của bạn
              </h2>
              <p className="mt-4 text-sm sm:text-base leading-relaxed text-ink-600 dark:text-granite-300">
                Hầu hết nhà đầu tư mới thua lỗ không phải vì thiếu thông tin, mà vì tâm lý giao dịch (FOMO, sợ bỏ lỡ cơ hội, gồng lỗ, trả thù thị trường).
              </p>
              <p className="mt-3 text-sm sm:text-base leading-relaxed text-ink-600 dark:text-granite-300">
                Khác với các bot &quot;phím mã&quot; thông thường, AI Mentor của Capia ứng dụng phương pháp vấn đáp Socratic — <strong>đặt câu hỏi ngược</strong> trước khi bạn đặt lệnh để giúp bạn tự nhận diện rủi ro và xây dựng kỷ luật cá nhân.
              </p>

              <div className="mt-6 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent dark:text-accent-400">
                    <IconCheck className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-sm text-ink-700 dark:text-granite-300">
                    Ngăn chặn vào lệnh bốc đồng khi cổ phiếu đang tăng nóng
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent dark:text-accent-400">
                    <IconCheck className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-sm text-ink-700 dark:text-granite-300">
                    Chấm điểm kỷ luật và đo lường độ chịu đựng rủi ro sau mỗi phiên
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent dark:text-accent-400">
                    <IconCheck className="h-3.5 w-3.5" />
                  </div>
                  <span className="text-sm text-ink-700 dark:text-granite-300">
                    Hỏi đáp liên tục gắn liền với bối cảnh cổ phiếu đang xem (TECHA, FINB...)
                  </span>
                </div>
              </div>

              <div className="mt-8 flex items-center gap-3">
                <Link href="/trade/mentor" className="btn-secondary text-sm">
                  <IconChat className="h-4 w-4" />
                  Xem thử AI Mentor
                </Link>
                <Link href="/register" className="btn-primary text-sm">
                  Trải nghiệm đầy đủ
                </Link>
              </div>
            </div>

            {/* Khung mô phỏng hội thoại Socratic */}
            <div className="rounded-2xl border border-line bg-paper p-5 shadow-card dark:border-granite-700 dark:bg-granite-900">
              <div className="flex items-center justify-between border-b border-line pb-3 dark:border-granite-800">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
                    <IconMentor className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-ink-900 dark:text-slip">Capia Socratic Mentor</div>
                    <div className="text-[10px] text-accent dark:text-accent-400 font-mono">CHẾ ĐỘ PHẢN BIỆN LỆNH</div>
                  </div>
                </div>
                <span className="rounded-md border border-mkt-up/30 bg-mkt-up/10 px-2 py-0.5 text-[10px] font-bold text-mkt-up">
                  SẴN SÀNG
                </span>
              </div>

              <div className="mt-4 space-y-3 text-xs leading-relaxed">
                <div className="rounded-xl border border-line bg-slip p-3 dark:border-granite-800 dark:bg-granite-950">
                  <span className="font-bold text-ink-900 dark:text-slip">Bạn (Trader):</span>
                  <p className="mt-1 text-ink-600 dark:text-granite-300">
                    &quot;Mã TECHA vừa ra tin tích cực về hợp đồng AI, tôi muốn dùng 80% số tiền mặt để mua hết giá trần sáng nay!&quot;
                  </p>
                </div>

                <div className="rounded-xl border border-accent/30 bg-accent/10 p-3 text-ink-900 dark:text-slip">
                  <div className="flex items-center gap-1.5 font-bold text-accent dark:text-accent-400">
                    <IconMentor className="h-3.5 w-3.5" />
                    <span>AI Mentor phản biện:</span>
                  </div>
                  <p className="mt-1 text-ink-700 dark:text-granite-200">
                    &quot;Hãy dừng lại 30 giây để cân nhắc: P/E hiện tại của TECHA đã ở mức 24.5 — bạn có nghĩ tin tốt này đã được phản ánh vào đợt tăng giá trước đó không? Nếu tin tức bị đảo chiều bất ngờ, danh mục của bạn có thể chịu mức lỗ bao nhiêu %? Kế hoạch cắt lỗ của bạn ở mức giá nào?&quot;
                  </p>
                </div>

                <div className="rounded-lg border border-line bg-paper p-2.5 dark:border-granite-800 dark:bg-granite-950/60 text-center text-[11px] text-ink-500 dark:text-granite-400">
                  🎯 Giúp bạn nhận ra thiên kiến FOMO và điều chỉnh tỷ trọng lệnh an toàn trước khi bấm Mua.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 4: Hành trình 5 bước */}
        <section id="cach-hoat-dong" className="mx-auto max-w-6xl scroll-mt-24 pt-28">
          <div className="text-center max-w-3xl mx-auto">
            <span className="board-label text-brand-700 dark:text-brand-300">
              PHƯƠNG PHÁP RÈN LUYỆN
            </span>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-3xl lg:text-4xl">
              Cách Capia giúp bạn tôi luyện bản lĩnh
            </h2>
            <p className="mt-3 text-sm sm:text-base text-ink-600 dark:text-granite-300 leading-relaxed">
              Một chu trình khép kín từ lúc nhận tin tức cho đến phân tích, phản biện, thực thi và rút ra bài học kinh nghiệm.
            </p>
          </div>

          <div className="relative mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
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
                  className="group relative flex flex-col rounded-xl border border-transparent bg-paper/60 p-4 transition-all hover:border-line hover:bg-paper hover:shadow-sm sm:items-start sm:text-left dark:bg-granite-900/40 dark:hover:border-granite-700 dark:hover:bg-granite-900"
                >
                  <span className="board-label z-10 text-brand-700 dark:text-brand-300 font-bold">
                    BƯỚC {step.no}
                  </span>
                  <div className="mt-4 flex h-10 w-10 items-center justify-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-700 dark:text-brand-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-3 text-sm font-black text-ink-900 group-hover:text-brand-700 dark:text-slip dark:group-hover:text-brand-300">
                    {step.title}
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm leading-relaxed text-ink-500 dark:text-granite-400">
                    {step.description}
                  </p>
                  <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-brand-700 dark:text-brand-300 opacity-0 group-hover:opacity-100 transition-opacity">
                    Khám phá ngay →
                  </span>
                </Link>
              );
            })}
          </div>
        </section>

        {/* Section 5: CTA Banner cuối trang */}
        <section className="mx-auto max-w-6xl pt-24 pb-12">
          <div className="relative overflow-hidden rounded-3xl border border-brand-500/40 bg-gradient-to-r from-granite-900 via-granite-950 to-granite-900 p-8 text-center text-slip shadow-xl sm:p-12">
            <div
              aria-hidden
              className="absolute -right-20 -top-20 h-60 w-60 rounded-full bg-brand-500/15 blur-3xl pointer-events-none"
            />
            <div
              aria-hidden
              className="absolute -left-20 -bottom-20 h-60 w-60 rounded-full bg-accent/15 blur-3xl pointer-events-none"
            />

            <span className="board-label text-brand-300">KHÔNG RỦI RO TÀI CHÍNH</span>
            <h2 className="mx-auto mt-2 max-w-2xl text-2xl font-black tracking-tight sm:text-3xl lg:text-4xl">
              Sẵn sàng thử sức với 100.000.000 ₫ tiền mô phỏng?
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-granite-300">
              Đăng ký tài khoản chỉ mất 30 giây. Bắt đầu ngay hôm nay để rèn luyện thói quen quản trị rủi ro trước khi bước chân vào thị trường thật.
            </p>

            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/news"
                className="btn-secondary w-full px-7 py-3 text-base sm:w-auto flex items-center justify-center gap-2 border-granite-700 bg-granite-800 text-slip hover:border-brand-400 font-bold"
              >
                <IconEye className="h-4 w-4" />
                Vào xem web (Chế độ khách)
              </Link>
              <Link href="/register" className="btn-primary w-full px-8 py-3 text-base sm:w-auto">
                Tạo tài khoản miễn phí
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-line bg-paper dark:border-granite-800 dark:bg-granite-900">
        <div className="mx-auto max-w-6xl grid gap-8 px-4 py-12 sm:grid-cols-[1.5fr_repeat(3,1fr)] sm:px-6">
          <div>
            <Link href="/" className="inline-block">
              <img src="/logo.png" alt="Capia" className="h-7 w-auto" />
            </Link>
            <p className="mt-3 max-w-xs text-xs leading-relaxed text-ink-500 dark:text-granite-400">
              Môi trường mô phỏng đầu tư chứng khoán với thời gian nén, dữ liệu AI và AI Mentor Socratic — nơi bạn rèn kỷ luật và quản trị vốn trước khi chạm tiền thật.
            </p>
            <div className="mt-4 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-mkt-up" />
              <span className="text-[11px] font-mono text-ink-500 dark:text-granite-400">
                Thị trường ảo đang chạy (20 mã)
              </span>
            </div>
          </div>

          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Khám phá thị trường</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/companies" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Doanh nghiệp (20 mã)
                </Link>
              </li>
              <li>
                <Link href="/news" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Tin tức & Vĩ mô
                </Link>
              </li>
              <li>
                <Link href="/social" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Cộng đồng & Tâm lý
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Bàn giao dịch</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/trade" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Bàn giao dịch trực tiếp
                </Link>
              </li>
              <li>
                <Link href="/trade/mentor" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  AI Mentor phản biện
                </Link>
              </li>
              <li>
                <Link href="/tasks" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Nhiệm vụ & Điểm kỷ luật
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="board-label text-ink-400 dark:text-granite-500">Tài khoản & Bắt đầu</h4>
            <ul className="mt-3 space-y-2 text-sm text-ink-600 dark:text-granite-300">
              <li>
                <Link href="/register" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors font-bold text-brand-700 dark:text-brand-300">
                  Đăng ký (Nhận 100tr)
                </Link>
              </li>
              <li>
                <Link href="/login" className="hover:text-brand-700 dark:hover:text-brand-300 transition-colors">
                  Đăng nhập tài khoản
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-line py-4 text-center text-xs text-ink-400 dark:border-granite-800 dark:text-granite-500">
          Capia © 2026 — Nền tảng mô phỏng đào tạo, không cung cấp lời khuyên đầu tư tài chính thật.
        </div>
      </footer>
    </div>
  );
}
