/**
 * ProductShowcase — mockup bàn giao dịch Capia thu nhỏ.
 * Cấu trúc: chrome bar → ticker toàn thị trường (mã giả lập chuẩn Capia: TECHA, FINB, HEALA...)
 * → tab chọn mã tương tác → lưới KPI + sổ lệnh/lệnh khớp + CTA trải nghiệm.
 */
"use client";

import Link from "next/link";
import { useState } from "react";

import {
  IconCandle,
  IconRisk,
  IconTrendUp,
  IconWallet,
  IconChevronRight,
} from "@/components/common/Icon";

interface TickerItem {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  pct: number;
  up: boolean;
}

/** Danh sách mã cổ phiếu mô phỏng chuẩn xác từ seed database của Capia */
const TICKERS: TickerItem[] = [
  { symbol: "TECHA", name: "TechVision Corp", sector: "Công nghệ", price: 156.8, pct: 2.4, up: true },
  { symbol: "TECHB", name: "CloudSync Inc", sector: "Công nghệ", price: 89.4, pct: 1.8, up: true },
  { symbol: "TECHC", name: "QuantumByte Labs", sector: "Công nghệ", price: 215.0, pct: -0.9, up: false },
  { symbol: "FINA", name: "BlueRock Financial", sector: "Tài chính", price: 45.6, pct: 1.2, up: true },
  { symbol: "FINB", name: "NovaPay Holdings", sector: "FinTech", price: 72.3, pct: 3.1, up: true },
  { symbol: "FINC", name: "SecureVault Insurance", sector: "Bảo hiểm", price: 34.5, pct: -0.6, up: false },
  { symbol: "HEALA", name: "BioGenix Therapeutics", sector: "Y tế", price: 128.9, pct: 4.5, up: true },
  { symbol: "HEALB", name: "MedCore International", sector: "Y tế", price: 67.2, pct: -1.1, up: false },
  { symbol: "ENERGA", name: "GreenHydrogen Energy", sector: "Năng lượng", price: 18.8, pct: -2.3, up: false },
  { symbol: "ENERGB", name: "Solaris Power Grid", sector: "Năng lượng", price: 41.2, pct: 0.8, up: true },
  { symbol: "CONSMA", name: "Premier Brands Group", sector: "Tiêu dùng", price: 63.5, pct: 1.5, up: true },
  { symbol: "INDUSA", name: "AeroDynamics Inc", sector: "Công nghiệp", price: 187.4, pct: 2.0, up: true },
  { symbol: "INDUSC", name: "LogiChain Solutions", sector: "Hậu cần", price: 78.6, pct: 1.4, up: true },
  { symbol: "COMMB", name: "SocialWave Media", sector: "Truyền thông", price: 110.2, pct: 3.6, up: true },
];

interface StockDetail {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  pct: number;
  up: boolean;
  orderBook: Array<{ price: string; vol: string; buy: boolean }>;
  matchedOrder: { side: "MUA" | "BÁN"; qty: string; price: string };
}

const FEATURED_STOCKS: Record<string, StockDetail> = {
  TECHA: {
    symbol: "TECHA",
    name: "TechVision Corp",
    sector: "Công nghệ AI",
    price: 156.8,
    pct: 2.4,
    up: true,
    orderBook: [
      { price: "157.4", vol: "2.4k", buy: false },
      { price: "157.1", vol: "3.8k", buy: false },
      { price: "156.9", vol: "1.9k", buy: false },
      { price: "156.8", vol: "4.5k", buy: true },
      { price: "156.5", vol: "3.2k", buy: true },
      { price: "156.2", vol: "5.1k", buy: true },
    ],
    matchedOrder: { side: "MUA", qty: "1.000", price: "156.80" },
  },
  FINB: {
    symbol: "FINB",
    name: "NovaPay Holdings",
    sector: "Thanh toán số",
    price: 72.3,
    pct: 3.1,
    up: true,
    orderBook: [
      { price: "72.9", vol: "1.8k", buy: false },
      { price: "72.6", vol: "2.5k", buy: false },
      { price: "72.4", vol: "1.2k", buy: false },
      { price: "72.3", vol: "5.4k", buy: true },
      { price: "72.0", vol: "3.9k", buy: true },
      { price: "71.7", vol: "4.1k", buy: true },
    ],
    matchedOrder: { side: "MUA", qty: "2.000", price: "72.30" },
  },
  HEALA: {
    symbol: "HEALA",
    name: "BioGenix Therapeutics",
    sector: "Công nghệ sinh học",
    price: 128.9,
    pct: 4.5,
    up: true,
    orderBook: [
      { price: "129.5", vol: "1.5k", buy: false },
      { price: "129.2", vol: "2.1k", buy: false },
      { price: "129.0", vol: "1.1k", buy: false },
      { price: "128.9", vol: "3.6k", buy: true },
      { price: "128.5", vol: "2.7k", buy: true },
      { price: "128.0", vol: "4.3k", buy: true },
    ],
    matchedOrder: { side: "MUA", qty: "500", price: "128.90" },
  },
  ENERGA: {
    symbol: "ENERGA",
    name: "GreenHydrogen Energy",
    sector: "Năng lượng xanh",
    price: 18.8,
    pct: -2.3,
    up: false,
    orderBook: [
      { price: "19.2", vol: "8.2k", buy: false },
      { price: "19.0", vol: "6.5k", buy: false },
      { price: "18.9", vol: "4.1k", buy: false },
      { price: "18.8", vol: "9.3k", buy: true },
      { price: "18.6", vol: "7.7k", buy: true },
      { price: "18.4", vol: "11.2k", buy: true },
    ],
    matchedOrder: { side: "BÁN", qty: "3.000", price: "18.80" },
  },
};

const KPIS = [
  { label: "NAV", value: "114.5tr", sub: "Vốn ban đầu 100tr", icon: IconWallet, tone: "text-slip" },
  { label: "TIỀN MẶT", value: "62.4tr", sub: "Khả dụng đặt lệnh", icon: IconWallet, tone: "text-slip" },
  { label: "TỐC ĐỘ", value: "+14.5%", sub: "Lợi nhuận PNL", icon: IconTrendUp, tone: "text-mkt-up" },
  { label: "RỦI RO", value: "28/100", sub: "Mức an toàn", icon: IconRisk, tone: "text-slip" },
  { label: "GIAO DỊCH", value: "18 lệnh", sub: "Khớp trong ngày", icon: IconCandle, tone: "text-slip" },
  { label: "ĐIỂM KỶ LUẬT", value: "92/100", sub: "Quản trị rủi ro tốt", icon: IconRisk, tone: "text-slip" },
];

export default function ProductShowcase() {
  const [activeSymbol, setActiveSymbol] = useState<string>("TECHA");
  const currentStock = FEATURED_STOCKS[activeSymbol] ?? FEATURED_STOCKS.TECHA;

  return (
    <div className="relative mx-auto mt-14 max-w-5xl text-left select-none">
      {/* Background glow */}
      <div
        aria-hidden
        className="absolute inset-x-0 -top-8 -bottom-8 rounded-[3rem] bg-brand-500/10 blur-3xl pointer-events-none"
      />

      <div className="relative overflow-hidden rounded-2xl border border-granite-700 bg-granite-900 shadow-card">
        {/* Chrome bar */}
        <div className="flex items-center justify-between border-b border-granite-700 px-4 py-2.5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-granite-500" />
            <span className="h-2.5 w-2.5 rounded-full bg-granite-600" />
            <span className="h-2.5 w-2.5 rounded-full bg-granite-600" />
          </div>
          <span className="board-label text-granite-400">capia.app/trade · terminal</span>
          <span className="flex items-center gap-1.5 rounded-md border border-mkt-up/30 bg-mkt-up/10 px-2 py-0.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-mkt-up" />
            <span className="board-label text-mkt-up">LIVE SIM</span>
          </span>
        </div>

        {/* Ticker toàn thị trường — khối lướt ngang liên tục với mã chuẩn Capia */}
        <div className="flex items-center justify-between border-b border-granite-700 bg-granite-800/60 px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="board-label text-granite-400">THỊ TRƯỜNG MÔ PHỎNG</span>
            <span className="text-[10px] text-granite-500 hidden sm:inline">(Nhấp mã để xem nhanh)</span>
          </div>
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-mkt-up" />
            <span className="board-label text-mkt-up">PHIÊN ĐANG MỞ</span>
          </span>
        </div>

        {/* Marquee ticker */}
        <div className="group relative overflow-hidden py-3 bg-granite-950/60">
          <div className="animate-marquee flex w-max will-change-transform group-hover:[animation-play-state:paused] motion-reduce:animate-none">
            {[0, 1].map((copy) => (
              <div key={copy} className="flex gap-3 pr-3" aria-hidden={copy === 1}>
                {TICKERS.map((tk) => (
                  <button
                    type="button"
                    key={`${tk.symbol}-${copy}`}
                    onClick={() => {
                      if (FEATURED_STOCKS[tk.symbol]) {
                        setActiveSymbol(tk.symbol);
                      }
                    }}
                    className={`flex shrink-0 items-center gap-2.5 rounded-xl border px-3.5 py-2 transition-all cursor-pointer ${
                      activeSymbol === tk.symbol
                        ? "border-brand-500 bg-brand-500/10 shadow-sm"
                        : "border-granite-700/80 bg-granite-900/90 hover:border-granite-500"
                    }`}
                    title={`${tk.symbol} · ${tk.name} (${tk.sector})`}
                  >
                    <span className="board-num text-sm font-black text-slip">{tk.symbol}</span>
                    <span className={`board-num text-xs font-semibold ${tk.up ? "text-mkt-up" : "text-mkt-down"}`}>
                      {tk.price.toFixed(1)}
                    </span>
                    <span
                      className={`board-num rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        tk.up ? "bg-mkt-up/10 text-mkt-up" : "bg-mkt-down/10 text-mkt-down"
                      }`}
                    >
                      {tk.up ? "+" : ""}
                      {tk.pct}%
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Tab chọn cổ phiếu tiêu biểu */}
        <div className="flex flex-wrap items-center gap-2 border-b border-granite-700 bg-granite-800/40 px-4 py-2">
          <span className="board-label text-granite-400 mr-1">MÃ TIÊU BIỂU:</span>
          {Object.keys(FEATURED_STOCKS).map((sym) => {
            const stock = FEATURED_STOCKS[sym];
            const isActive = activeSymbol === sym;
            return (
              <button
                key={sym}
                type="button"
                onClick={() => setActiveSymbol(sym)}
                className={`flex items-center gap-2 rounded-lg px-2.5 py-1 text-xs font-bold transition-colors ${
                  isActive
                    ? "bg-brand-500 text-granite-950"
                    : "border border-granite-700 bg-granite-900 text-granite-300 hover:border-granite-500 hover:text-slip"
                }`}
              >
                <span>{stock.symbol}</span>
                <span className={`text-[10px] opacity-80 ${isActive ? "text-granite-900" : "text-granite-400"}`}>
                  {stock.sector}
                </span>
              </button>
            );
          })}
        </div>

        {/* Nội dung Terminal: KPI và Sổ lệnh */}
        <div className="grid gap-4 p-4 sm:p-6 lg:grid-cols-2">
          {/* Cột trái: Lưới KPI tài khoản người dùng */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="board-label text-granite-400">DANH MỤC THỬ NGHIỆM</span>
              <span className="text-[10px] text-brand-300 font-mono">VỐN CẤP: 100.000.000 ₫</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
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
                    <div className={`board-num mt-2 text-base font-bold ${kpi.tone}`}>{kpi.value}</div>
                    <div className="mt-0.5 text-[10px] text-granite-400">{kpi.sub}</div>
                  </div>
                );
              })}
            </div>

            {/* Lợi ích nổi bật cho khách ghé thăm */}
            <div className="mt-3 rounded-xl border border-granite-700/80 bg-granite-950/70 p-3">
              <div className="flex items-center gap-2 text-xs font-bold text-slip">
                <span className="h-2 w-2 rounded-full bg-brand-400" />
                <span>Không cần nạp tiền — AI Mentor đồng hành từng lệnh</span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-granite-400">
                Toàn bộ dữ liệu giá {currentStock.symbol}, báo cáo tài chính và tin tức đều được tính toán theo mô hình kinh tế toán học khép kín.
              </p>
            </div>
          </div>

          {/* Cột phải: Sổ lệnh & Lệnh khớp của mã đang chọn */}
          <div className="flex flex-col justify-between">
            <div className="rounded-xl border border-granite-700 bg-granite-800/60 p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="board-label text-granite-400">SỔ LỆNH KHỚP GIÁ</span>
                  <span className="font-mono text-xs font-black text-slip">{currentStock.symbol}</span>
                </div>
                <span className="text-[11px] text-granite-400 truncate max-w-[150px]">
                  {currentStock.name}
                </span>
              </div>

              <div className="mt-2 space-y-1">
                {currentStock.orderBook.map((row) => (
                  <div
                    key={`${row.price}-${row.vol}-${row.buy}`}
                    className="grid grid-cols-[1fr_auto] rounded-md px-2.5 py-1 text-xs"
                    style={{
                      background: row.buy
                        ? "color-mix(in srgb, #1CAE56 12%, transparent)"
                        : "color-mix(in srgb, #E23636 12%, transparent)",
                    }}
                  >
                    <span className={`board-num font-bold ${row.buy ? "text-mkt-up" : "text-mkt-down"}`}>
                      {row.price}
                    </span>
                    <span className="board-num text-granite-300">{row.vol} cp</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Thông báo lệnh khớp gần nhất */}
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-brand-500/40 bg-brand-500/15 p-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500 text-granite-950">
                <IconCandle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-black text-slip">
                  Lệnh {currentStock.matchedOrder.side} {currentStock.matchedOrder.qty} {currentStock.symbol} · Giá {currentStock.matchedOrder.price}
                </div>
                <div className="board-label text-mkt-up">KHỚP THÀNH CÔNG (T+2 ẢO)</div>
              </div>
              <IconWallet className="h-5 w-5 text-granite-400" />
            </div>

            {/* Nút hành động */}
            <div className="mt-3 flex flex-col sm:flex-row items-center gap-2.5">
              <Link
                href="/trade"
                className="btn-secondary w-full justify-center text-xs py-2.5 sm:w-1/2"
              >
                <span>Xem bàn giao dịch</span>
                <IconChevronRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                href="/register"
                className="btn-primary w-full justify-center text-xs py-2.5 sm:w-1/2"
              >
                Nhận 100tr trải nghiệm
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
