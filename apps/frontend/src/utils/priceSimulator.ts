/**
 * Công cụ mô phỏng giá cổ phiếu phía client.
 *
 * Dùng làm **fallback** khi backend chưa có feed realtime / chưa đăng nhập:
 * đảm bảo màn hình Giao dịch luôn có "thị trường đang sống" — biểu đồ nến có
 * dữ liệu, sổ lệnh dựng được, giá nhấp nháy mỗi vài giây.
 *
 * Giá được sinh theo mô hình random-walk quanh giá gốc (basePrice) với độ biến
 * động kiểm soát, deterministic theo symbol để nhiều lần mở cùng mã cho kết quả
 * nhất quán ở các phiên đầu.
 */

export interface SimulatedPricePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Băm chuỗi → số trong [0,1) (nguồn ngẫu nhiên định danh). */
function hashStr(input: string): number {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index++) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967296;
}

/** Binomial-ish step ngẫu nhiên trong [-1, 1]. */
function pseudoRandom(seed: number): number {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453123;
  return x - Math.floor(x) - 0.5;
}

/**
 * Sinh chuỗi giá lịch sử (nến OHLC) cho một symbol.
 */
export function generateHistoricalPrices(
  symbol: string,
  basePrice: number,
  days: number = 90,
  volatility: number = 0.02,
): SimulatedPricePoint[] {
  if (!Number.isFinite(basePrice) || basePrice <= 0) {
    basePrice = 100;
  }
  const seedBase = hashStr(symbol) * 100000;
  const points: SimulatedPricePoint[] = [];
  let price = basePrice * (1 - 0.15);
  const start = Math.floor((Date.now() - days * 24 * 3600 * 1000) / 1000);

  for (let index = 0; index < days; index++) {
    const drift = pseudoRandom(seedBase + index) * volatility;
    const open = Math.max(1, price);
    const close = Math.max(1, price * (1 + drift));
    const wick = Math.abs(pseudoRandom(seedBase + index + 999)) * volatility * price * 0.6;
    const high = Math.max(open, close) + wick;
    const low = Math.min(open, close) - wick;
    points.push({
      time: start + index * 24 * 3600,
      open: round2(open),
      high: round2(high),
      low: round2(low),
      close: round2(close),
    });
    price = close;
  }

  // Điều chỉnh để cây nến cuối đóng quanh basePrice.
  const last = points[points.length - 1];
  const scale = basePrice / last.close;
  return points.map((p) => ({
    ...p,
    open: round2(p.open * scale),
    high: round2(p.high * scale),
    low: round2(p.low * scale),
    close: round2(p.close * scale),
  }));
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Sinh một tick giá mới (bước random-walk nhỏ) từ giá hiện tại. */
export function nextSimulatedPrice(
  symbol: string,
  currentPrice: number,
  stepCount: number,
  volatility: number = 0.001,
): number {
  const rnd = pseudoRandom(hashStr(symbol) * 1000 + stepCount * 7.13);
  const stepPct = rnd * volatility;
  const next = currentPrice * (1 + stepPct);
  return Math.max(1, round2(next));
}

/** Tính phần trăm thay đổi so với giá đóng phiên trước (prevClose). */
export function computeChange(price: number, prevClose: number): {
  change: number;
  changePct: number;
} {
  if (!Number.isFinite(prevClose) || prevClose <= 0) {
    return { change: 0, changePct: 0 };
  }
  const change = round2(price - prevClose);
  const changePct = round2((change / prevClose) * 100);
  return { change, changePct };
}
