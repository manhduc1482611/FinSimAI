/**
 * Format số liệu tài chính cho toàn Frontend.
 *
 * Lưu ý wire format: FastAPI serialize ``Decimal`` thành **string** — mọi giá trị
 * tiền/lượng cổ phiếu từ API đều cần đi qua ``parseDecimal`` trước khi tính toán.
 */

const VND_FORMATTER = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

const NUMBER_FORMATTER = new Intl.NumberFormat("vi-VN", {
  maximumFractionDigits: 2,
});

/** Chuyển Decimal-dạng-string từ API thành số an toàn. */
export function parseDecimal(
  value: string | null | undefined,
  fallback = 0,
): number {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** Format tiền VND đầy đủ, ví dụ: 1.000.000 ₫ */
export function formatVND(value: number): string {
  return VND_FORMATTER.format(value);
}

/**
 * Format tiền VND rút gọn theo đơn vị nghìn / triệu / tỷ.
 * ví dụ: 1,24 Tỷ ₫ · 850 Triệu ₫ · 2,5 Nghìn ₫
 */
export function formatCompactVND(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000_000_000) {
    return `${sign}${formatNumber(abs / 1_000_000_000_000)} Nghìn tỷ ₫`;
  }
  if (abs >= 1_000_000_000) {
    return `${sign}${formatNumber(abs / 1_000_000_000)} Tỷ ₫`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${formatNumber(abs / 1_000_000)} Triệu ₫`;
  }
  if (abs >= 1_000) {
    return `${sign}${formatNumber(abs / 1_000)} Nghìn ₫`;
  }
  return `${sign}${formatNumber(abs)} ₫`;
}

/** Format số thường với tối đa 2 chữ số thập phân, ví dụ: 156,80 */
export function formatNumber(value: number, fractionDigits = 2): string {
  return new Intl.NumberFormat("vi-VN", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

/** Format giá cổ phiếu với tối đa 2 chữ số thập phân, ví dụ: 156,80 */
export function formatPrice(value: number): string {
  return NUMBER_FORMATTER.format(value);
}

/** Format phần trăm, ví dụ: 2,35% · +2,35% · -1,20% */
export function formatPercent(value: number, signed = false): string {
  const sign = signed && value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, 2)}%`;
}

/** Format số lượng cổ phiếu (tối đa 4 chữ số thập phân), ví dụ: 1.000,0000 */
export function formatQuantity(value: number): string {
  return new Intl.NumberFormat("vi-VN", {
    maximumFractionDigits: 4,
  }).format(value);
}

/** Thời gian tương đối, ví dụ: "2 phút trước" · "3 giờ trước" · "hôm qua" */
export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) {
    return iso;
  }
  const diffSeconds = Math.floor((Date.now() - then) / 1000);
  if (diffSeconds < 0) {
    return "vừa xong";
  }
  if (diffSeconds < 60) {
    return `${diffSeconds} giây trước`;
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} phút trước`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} giờ trước`;
  }
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) {
    return "hôm qua";
  }
  return `${diffDays} ngày trước`;
}

/** Format ngày giờ đầy đủ, ví dụ: "01/08/2026 14:30" */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** Nhãn ngày mô phỏng, ví dụ: "Ngày mô phỏng 42" */
export function formatSimDay(simDay: number): string {
  return `Ngày mô phỏng ${simDay}`;
}
