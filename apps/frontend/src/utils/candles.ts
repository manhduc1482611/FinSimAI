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

/**
 * Sinh chuỗi nến lịch sử mượt mà bám quanh basePrice để biểu đồ có sẵn
 * đường giá và tính toán được các đường kỹ thuật (MA10, MA20) ngay khi vừa mở.
 */
export function generateInitialCandles(
  basePrice: number,
  count = 35,
  bucketSeconds = 10,
  nowSec: number = Math.floor(Date.now() / 1000)
): Candle[] {
  if (basePrice <= 0) return [];
  const candles: Candle[] = [];
  const currentBucket = Math.floor(nowSec / bucketSeconds) * bucketSeconds;

  const prices: number[] = [basePrice];
  let p = basePrice;
  const vol = basePrice * 0.003;

  for (let i = 1; i < count; i++) {
    const drift = (basePrice - p) * 0.06;
    const change = (Math.sin(i * 0.6) * 0.6 + (Math.random() - 0.49)) * vol + drift;
    p = Math.max(basePrice * 0.9, Math.min(basePrice * 1.1, p - change));
    prices.unshift(p);
  }

  for (let i = 0; i < count; i++) {
    const time = currentBucket - (count - 1 - i) * bucketSeconds;
    const open = i === 0 ? prices[0] : prices[i - 1];
    const close = prices[i];
    const spread = Math.abs(open - close);
    const wick = (Math.random() * 0.7 + 0.2) * Math.max(spread, basePrice * 0.001);
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick * 0.8;

    candles.push({
      time,
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(Math.max(0.01, low).toFixed(2)),
      close: Number(close.toFixed(2)),
    });
  }

  return candles;
}

export interface MASeriesPoint {
  time: number;
  value: number;
}

/** Tính đường trung bình động (Moving Average) từ mảng nến. */
export function calculateMA(candles: Candle[], period: number): MASeriesPoint[] {
  const result: MASeriesPoint[] = [];
  if (candles.length < period) return result;

  let sum = 0;
  for (let i = 0; i < candles.length; i++) {
    sum += candles[i].close;
    if (i >= period) {
      sum -= candles[i - period].close;
    }
    if (i >= period - 1) {
      result.push({
        time: candles[i].time,
        value: Number((sum / period).toFixed(2)),
      });
    }
  }
  return result;
}

