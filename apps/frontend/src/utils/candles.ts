/**
 * Xử lý dữ liệu nến (candlestick) từ luồng giá WebSocket.
 *
 * Backend không có dữ liệu OHLC lịch sử — chỉ có `price_tick` / `price_snapshot`
 * (mỗi tick mang price/open/high/low/prev_close của phiên hiện tại). Candle được
 * dựng lại bằng cách gom tick theo **cửa sổ thời gian thực** (bucketSeconds):
 * tick đầu của cửa sổ mở candle, các tick sau cập nhật high/low/close.
 */

import type { PriceTick } from "@/types/websocket";

/** Tick kèm mốc thời gian thực lúc nhận (dùng để chia cửa sổ nến). */
export interface TimedPriceTick {
  tick: PriceTick;
  receivedAt: number;
}

/** Một cây nến (time = unix second, ứng với start của cửa sổ). */
export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Dựng mảng candle từ danh sách tick đã đánh dấu thời gian nhận. */
export function buildCandles(ticks: TimedPriceTick[], bucketSeconds: number): Candle[] {
  const candles: Candle[] = [];
  for (const { tick, receivedAt } of ticks) {
    const price = tick.price;
    const time = Math.floor(receivedAt / bucketSeconds) * bucketSeconds;
    const last = candles[candles.length - 1];
    if (last !== undefined && last.time === time) {
      last.high = Math.max(last.high, price);
      last.low = Math.min(last.low, price);
      last.close = price;
    } else {
      candles.push({ time, open: price, high: price, low: price, close: price });
    }
  }
  return candles;
}
