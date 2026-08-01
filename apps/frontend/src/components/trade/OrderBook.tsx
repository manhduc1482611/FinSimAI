/**
 * OrderBook — sổ lệnh hai chiều (bids/asks) quanh giá giao dịch gần nhất.
 *
 * Backend chưa có nguồn dữ liệu depth — book được dựng **mô phỏng** quanh giá live
 * từ WS (deterministic theo symbol + giá, cập nhật khi giá đổi) để thị hoá cấu
 * trúc thanh khoản quanh lệnh của người dùng. Nhãn "Mô phỏng" hiển thị rõ để
 * không nhầm với dữ liệu thật.
 */
"use client";

import { useMemo } from "react";

import { Card } from "@/components/common/Card";
import { formatNumber, formatQuantity } from "@/utils/format";

export interface DepthLevel {
  price: number;
  size: number;
  /** Tổng khối lượng tích luỹ từ đỉnh book (mức sát giá nhất) tới mức này. */
  cumulative: number;
}

export interface DepthBook {
  bids: DepthLevel[];
  asks: DepthLevel[];
  mid: number;
  step: number;
  maxCumulative: number;
}

export interface OrderBookProps {
  symbol: string;
  /** Giá giao dịch gần nhất (từ WS price_tick / price_snapshot). */
  price: number | null;
  /** Số mức giá mỗi bên (mặc định 10). */
  levels?: number;
}

/** Băm chuỗi thành số trong [0, 1) — dùng làm nguồn ngẫu nhiên xác định. */
function hashSeed(input: string): number {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index++) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967296;
}

/** Bước giá theo độ lớn của giá (≈0.1%–0.25%). */
export function priceStep(price: number): number {
  const step = price * 0.002;
  if (step < 0.01) {
    return 0.01;
  }
  return Math.round(step * 100) / 100;
}

/** Dựng depth book mô phỏng deterministic quanh giá mid. */
export function buildDepthBook(symbol: string, price: number, levels: number): DepthBook {
  const step = priceStep(price);

  const buildSide = (direction: 1 | -1): DepthLevel[] => {
    let cumulative = 0;
    const result: DepthLevel[] = [];
    for (let index = 0; index < levels; index++) {
      const levelPrice = Math.round((price + direction * step * (index + 1)) * 100) / 100;
      const random = hashSeed(`${symbol}:${direction}:${index}:${Math.round(price * 100)}`);
      const baseSize = 500 + Math.floor(random * 20_000);
      const size = Math.round(baseSize * (0.5 + index * 0.18));
      cumulative += size;
      result.push({ price: levelPrice, size, cumulative });
    }
    return result;
  };

  const bids = buildSide(-1).reverse();
  const asks = buildSide(1);
  const maxCumulative = Math.max(bids[bids.length - 1].cumulative, asks[asks.length - 1].cumulative);

  return { bids, asks, mid: price, step, maxCumulative };
}

/** Khối lượng tích luỹ từng mức (0-100) để vẽ depth bar. */
function depthPercent(level: DepthLevel, max: number): number {
  if (max <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, (level.cumulative / max) * 100));
}

export function OrderBook({ symbol, price, levels = 10 }: OrderBookProps) {
  const book = useMemo<DepthBook | null>(() => {
    if (price === null) {
      return null;
    }
    return buildDepthBook(symbol, price, levels);
  }, [symbol, price, levels]);

  const bestBid = book?.bids[book.bids.length - 1] ?? null;
  const bestAsk = book?.asks[0] ?? null;
  const spread =
    bestBid !== null && bestAsk !== null
      ? Math.round((bestAsk.price - bestBid.price) * 100) / 100
      : null;

  return (
    <Card className="flex h-full flex-col">
      <div className="border-b border-ink-200 px-4 py-3 dark:border-ink-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ink-900 dark:text-ink-100">Sổ lệnh</h3>
            <p className="text-xs text-ink-500 dark:text-ink-400">{symbol}</p>
          </div>
          <span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-500 dark:bg-ink-700 dark:text-ink-300">
            Mô phỏng
          </span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-red-50 px-3 py-1.5 dark:bg-red-500/10">
            <p className="text-[10px] uppercase tracking-wide text-red-500">Giá mua tốt nhất</p>
            <p className="font-bold tabular-nums text-red-600 dark:text-red-400">
              {bestBid !== null ? formatNumber(bestBid.price, 2) : "—"}
            </p>
          </div>
          <div className="rounded-lg bg-emerald-50 px-3 py-1.5 dark:bg-emerald-500/10">
            <p className="text-[10px] uppercase tracking-wide text-emerald-600 dark:text-emerald-500">Giá bán tốt nhất</p>
            <p className="font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
              {bestAsk !== null ? formatNumber(bestAsk.price, 2) : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="min-h-[16rem] flex-1 px-4 py-3">
        {book === null ? (
          <div className="flex h-full min-h-[14rem] items-center justify-center">
            <p className="text-sm text-ink-400 dark:text-ink-500">
              Chờ giá live để dựng sổ lệnh…
            </p>
          </div>
        ) : (
          <>
            <div className="mb-1 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-ink-400 dark:text-ink-500">
              <span>Giá</span>
              <span>KL (lũy kế)</span>
            </div>

            {/* Asks — từ mức giá xa tới sát giá nhất (trên) */}
            <div className="space-y-0.5">
              {book.asks.map((level) => (
                <div
                  key={`ask-${level.price}`}
                  className="relative flex items-center justify-between rounded px-2 py-1 text-xs"
                >
                  <span className="absolute inset-0 rounded bg-emerald-500/10" style={{ width: `${depthPercent(level, book.maxCumulative)}%` }} />
                  <span className="relative font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                    {formatNumber(level.price, 2)}
                  </span>
                  <span className="relative text-ink-600 dark:text-ink-300">
                    {formatQuantity(level.cumulative)}
                  </span>
                </div>
              ))}
            </div>

            {/* Mid */}
            <div className="my-1.5 flex items-center justify-between rounded-lg bg-ink-100 px-2 py-1 text-xs dark:bg-ink-700">
              <span className="font-semibold text-ink-600 dark:text-ink-300">Mid</span>
              <span className="font-bold tabular-nums text-ink-900 dark:text-ink-100">
                {formatNumber(book.mid, 2)}
              </span>
              <span className="text-ink-400 dark:text-ink-500">
                {spread !== null ? `Spread ${formatNumber(spread, 2)}` : ""}
              </span>
            </div>

            {/* Bids — từ mức sát giá nhất xuống xa (dưới mid) */}
            <div className="space-y-0.5">
              {[...book.bids].reverse().map((level) => (
                <div
                  key={`bid-${level.price}`}
                  className="relative flex items-center justify-between rounded px-2 py-1 text-xs"
                >
                  <span className="absolute inset-0 rounded bg-red-500/10" style={{ width: `${depthPercent(level, book.maxCumulative)}%` }} />
                  <span className="relative font-semibold tabular-nums text-red-600 dark:text-red-400">
                    {formatNumber(level.price, 2)}
                  </span>
                  <span className="relative text-ink-600 dark:text-ink-300">
                    {formatQuantity(level.cumulative)}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
