/**
 * Chi phí giao dịch mô phỏng — đồng bộ với backend (core/config.py):
 *   trading_fee_rate = 0.15% giá trị khớp, áp cả MUA và BÁN.
 *   sell_tax_rate    = 0.1% giá trị khớp, chỉ áp chiều BÁN
 *                      (thuế thu nhập từ chuyển nhượng vốn — luật VN).
 */

export const TRADING_FEE_RATE = 0.0015;
export const SELL_TAX_RATE = 0.001;

/** Phí môi giới 0.15% — cả hai chiều. */
export function estimateFee(grossValue: number): number {
  return grossValue * TRADING_FEE_RATE;
}

/** Thuế bán 0.1% — chỉ chiều bán. */
export function estimateSellTax(grossValue: number): number {
  return grossValue * SELL_TAX_RATE;
}
