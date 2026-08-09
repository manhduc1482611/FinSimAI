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
      <div className="border-b border-line px-4 py-3 dark:border-granite-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-ink-900 dark:text-slip">Sổ lệnh</h3>
            <p className="board-num text-xs text-ink-500 dark:text-granite-300">{symbol}</p>
          </div>
          <span className="stamp text-[10px]">Mô phỏng</span>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          <div className="board">
            <p className="board-label text-mkt-down-400">Giá mua tốt nhất</p>
            <p className="board-num text-sm font-bold text-mkt-down dark:text-mkt-down-400">
              {bestBid !== null ? formatNumber(bestBid.price, 2) : "—"}
            </p>
          </div>
          <div className="board">
            <p className="board-label text-mkt-up-400">Giá bán tốt nhất</p>
            <p className="board-num text-sm font-bold text-mkt-up dark:text-mkt-up-400">
              {bestAsk !== null ? formatNumber(bestAsk.price, 2) : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="min-h-[16rem] flex-1 px-4 py-3">
        {book === null ? (
          <div className="flex h-full min-h-[14rem] items-center justify-center">
            <p className="text-sm text-ink-400 dark:text-granite-400">
              Chờ giá live để dựng sổ lệnh…
            </p>
          </div>
        ) : (
          <>
            <div className="mb-1 flex items-center justify-between board-label text-ink-400 dark:text-granite-400">
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
                  <span className="absolute inset-0 rounded bg-mkt-up/10" style={{ width: `${depthPercent(level, book.maxCumulative)}%` }} />
                  <span className="board-num relative font-semibold text-mkt-up dark:text-mkt-up-400">
                    {formatNumber(level.price, 2)}
                  </span>
                  <span className="board-num relative text-ink-600 dark:text-granite-300">
                    {formatQuantity(level.cumulative)}
                  </span>
                </div>
              ))}
            </div>

            {/* Mid */}
            <div className="my-1.5 flex items-center justify-between rounded-lg bg-ink-100 px-2 py-1 text-xs dark:bg-granite-800">
              <span className="font-semibold text-ink-600 dark:text-granite-300">Mid</span>
              <span className="board-num font-bold text-ink-900 dark:text-slip">
                {formatNumber(book.mid, 2)}
              </span>
              <span className="board-label text-ink-400 dark:text-granite-400">
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
                  <span className="absolute inset-0 rounded bg-mkt-down/10" style={{ width: `${depthPercent(level, book.maxCumulative)}%` }} />
                  <span className="board-num relative font-semibold text-mkt-down dark:text-mkt-down-400">
                    {formatNumber(level.price, 2)}
                  </span>
                  <span className="board-num relative text-ink-600 dark:text-granite-300">
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
