/**
 * ProductShowcase — mockup "sản phẩm": một cửa sổ ứng dụng thu nhỏ.
 * Cấu trúc: chrome bar → ticker toàn thị trường (khối lướt ngang liên tục)
 * → lưới KPI + sổ lệnh/lệnh khớp + CTA. Dựng bằng chính các token của app.
 */
"use client";

import Link from "next/link";

import {
  IconCandle,
  IconRisk,
  IconTrendUp,
  IconWallet,
} from "@/components/common/Icon";

interface TickerItem {
  symbol: string;
  price: number;
  pct: number;
  up: boolean;
}

const TICKERS: TickerItem[] = [
  { symbol: "FPT", price: 71.4, pct: 2.1, up: true },
  { symbol: "VNM", price: 68.2, pct: -0.8, up: false },
  { symbol: "ACB", price: 32.5, pct: 1.4, up: true },
  { symbol: "TCB", price: 34.1, pct: 0.6, up: true },
  { symbol: "MBB", price: 24.3, pct: -1.2, up: false },
  { symbol: "HPG", price: 27.8, pct: 3.4, up: true },
  { symbol: "VIC", price: 48.9, pct: 0.2, up: true },
  { symbol: "VPB", price: 19.6, pct: -2.0, up: false },
  { symbol: "SSI", price: 46.3, pct: 1.1, up: true },
  { symbol: "GAS", price: 112.5, pct: -0.5, up: false },
  { symbol: "BVH", price: 55.7, pct: 0.9, up: true },
  { symbol: "SHB", price: 11.2, pct: 2.6, up: true },
];

const KPIS = [
  { label: "NAV", value: "245.7tr", sub: "Tổng giá trị", icon: IconWallet, tone: "text-slip" },
  { label: "TIỀN MẶT", value: "92.4tr", sub: "Sẵn sàng", icon: IconWallet, tone: "text-slip" },
  { label: "TỐC ĐỘ", value: "+6.8%", sub: "PNL", icon: IconTrendUp, tone: "text-mkt-up" },
  { label: "RỦI RO", value: "34/100", sub: "Thấp", icon: IconRisk, tone: "text-slip" },
  { label: "GIAO DỊCH", value: "27", sub: "Lệnh hôm nay", icon: IconCandle, tone: "text-slip" },
  { label: "ĐIỂM KỶ LUẬT", value: "92", sub: "Tuần", icon: IconRisk, tone: "text-slip" },
];

const ORDER_BOOK: Array<{ price: string; vol: string; buy: boolean }> = [
  { price: "107.6", vol: "2.4k", buy: false },
  { price: "107.2", vol: "3.1k", buy: false },
  { price: "107.0", vol: "1.8k", buy: false },
  { price: "106.8", vol: "4.2k", buy: true },
  { price: "106.6", vol: "2.9k", buy: true },
  { price: "106.4", vol: "3.6k", buy: true },
];

export default function ProductShowcase() {
  return (
    <div className="pointer-events-none relative mx-auto mt-16 max-w-5xl select-none">
      <div
        aria-hidden
        className="absolute inset-x-0 -top-8 -bottom-8 rounded-[3rem] bg-brand-500/10 blur-3xl"
      />
      <div className="relative overflow-hidden rounded-2xl border border-granite-700 bg-granite-900 shadow-card">
        <div className="flex items-center justify-between border-b border-granite-700 px-4 py-2.5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-granite-500" />
            <span className="h-2.5 w-2.5 rounded-full bg-granite-600" />
            <span className="h-2.5 w-2.5 rounded-full bg-granite-600" />
          </div>
          <span className="board-label text-granite-400">capia.app/trade</span>
          <span className="flex items-center gap-1.5 rounded-md border border-mkt-up/30 bg-mkt-up/10 px-2 py-0.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-mkt-up" />
            <span className="board-label text-mkt-up">LIVE</span>
          </span>
        </div>

        {/* Ticker toàn thị trường — khối lướt ngang liên tục */}
        <div className="flex items-center justify-between border-b border-granite-700 bg-granite-800/60 px-4 py-2">
          <span className="board-label text-granite-400">THỊ TRƯỜNG</span>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-mkt-up" />
            <span className="board-label text-mkt-up">ĐANG MỞ</span>
          </span>
        </div>
        <div className="group relative overflow-hidden py-3">
          <div className="animate-marquee flex w-max will-change-transform group-hover:[animation-play-state:paused] motion-reduce:animate-none">
            {[0, 1].map((copy) => (
              <div key={copy} className="flex gap-3 pr-3" aria-hidden={copy === 1}>
                {TICKERS.map((tk) => (
                  <div
                    key={tk.symbol}
                    className="flex shrink-0 items-center gap-3 rounded-xl border border-granite-700 bg-granite-900/80 px-4 py-2.5"
                    title={`${tk.symbol} · ${tk.up ? "tăng" : "giảm"} ${tk.pct}%`}
                  >
                    <span className="board-num text-base font-black text-slip">{tk.symbol}</span>
                    <span className={`board-num text-sm ${tk.up ? "text-mkt-up" : "text-mkt-down"}`}>
                      {tk.price.toFixed(1)}
                    </span>
                    <span
                      className={`board-num rounded-md px-1.5 py-0.5 text-[10px] ${
                        tk.up ? "bg-mkt-up/10 text-mkt-up" : "bg-mkt-down/10 text-mkt-down"
                      }`}
                    >
                      {tk.up ? "+" : ""}
                      {tk.pct}%
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 border-t border-granite-700 p-4 sm:p-6 lg:grid-cols-2">
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-3">
            {KPIS.map((kpi) => {
              const Icon = kpi.icon;
              return (
                <div
                  key={kpi.label}
                  className="flex flex-col justify-between rounded-xl border border-granite-700 bg-granite-800/60 p-3"
                >
                  <div className="flex items-center gap-1.5">
                    <Icon className="h-3.5 w-3.5 text-granite-400" />
                    <span className="board-label text-granite-400">{kpi.label}</span>
                  </div>
                  <div className={`board-num mt-2 text-base ${kpi.tone}`}>{kpi.value}</div>
                  <div className="mt-0.5 text-[10px] text-granite-400">{kpi.sub}</div>
                </div>
              );
            })}
          </div>

          <div className="flex flex-col">
            <div className="rounded-xl border border-granite-700 bg-granite-800/60 p-3">
              <div className="board-label text-granite-400">SỔ LỆNH GAS</div>
              <div className="mt-2 space-y-1">
                {ORDER_BOOK.map((row) => (
                  <div
                    key={`${row.price}-${row.vol}`}
                    className="grid grid-cols-[1fr_auto] rounded-md px-2 py-1 text-xs"
                    style={{
                      background: row.buy
                        ? "color-mix(in srgb, #1CAE56 12%, transparent)"
                        : "color-mix(in srgb, #E23636 12%, transparent)",
                    }}
                  >
                    <span className={`board-num ${row.buy ? "text-mkt-up" : "text-mkt-down"}`}>
                      {row.price}
                    </span>
                    <span className="board-num text-granite-300">{row.vol}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-3 flex items-center gap-3 rounded-xl border border-brand-500/40 bg-brand-500/15 p-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500 text-granite-950">
                <IconCandle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-black text-slip">Lệnh MUA 1.000 TCB</div>
                <div className="board-label text-mkt-up">ĐÃ KHỚP</div>
              </div>
              <IconWallet className="h-5 w-5 text-granite-400" />
            </div>

            <Link
              href="/register"
              onClick={(e) => e.stopPropagation()}
              className="btn-primary pointer-events-auto mt-3 w-full justify-center"
            >
              Bắt đầu mô phỏng
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}