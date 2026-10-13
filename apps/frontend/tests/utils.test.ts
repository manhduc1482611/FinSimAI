/**
 * Unit test cho các hàm thuần của Frontend — chạy bằng test runner có sẵn của
 * Node (`node:test`), KHÔNG cần thêm dependency (vitest/jest). Node >= 22.6 tự
 * bóc type khỏi file `.ts` nên chạy trực tiếp.
 *
 * Chạy:  node --test tests/            (từ apps/frontend)
 *        npm run test:unit
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  difficultyLabel,
  statusLabel,
  templateLabel,
} from "../src/utils/contest.ts";
import {
  formatCompactVND,
  formatImpact,
  formatPercent,
  formatQuantity,
  formatSimDay,
  formatVND,
  formatViral,
  isValidDisplayValue,
  parseDecimal,
  sanitizeTemplateVars,
} from "../src/utils/format.ts";
import { ROLE_HOME, homePathForRole } from "../src/utils/roles.ts";
import {
  SELL_TAX_RATE,
  TRADING_FEE_RATE,
  estimateFee,
  estimateSellTax,
} from "../src/utils/trading.ts";

// ── format.ts ────────────────────────────────────────────────────────────────
test("parseDecimal: chuỗi hợp lệ, rỗng và fallback", () => {
  assert.equal(parseDecimal("123.5"), 123.5);
  assert.equal(parseDecimal(""), 0);
  assert.equal(parseDecimal(null), 0);
  assert.equal(parseDecimal(undefined), 0);
  assert.equal(parseDecimal("không-phải-số", 7), 7);
});

test("formatVND: có nhóm nghìn", () => {
  assert.match(formatVND(1_000_000), /1\.000\.000/);
});

test("formatCompactVND: đơn vị Triệu / Tỷ", () => {
  assert.match(formatCompactVND(1_500_000), /Triệu/);
  assert.match(formatCompactVND(2_000_000_000), /Tỷ/);
  assert.match(formatCompactVND(5_000), /Nghìn/);
});

test("formatPercent: dấu âm/dương và hậu tố %", () => {
  assert.equal(formatPercent(2.35), "2,35%");
  assert.equal(formatPercent(2.35, true), "+2,35%");
  assert.equal(formatPercent(-2.35, true), "-2,35%");
});

test("formatQuantity: tối đa 4 chữ số thập phân", () => {
  assert.equal(formatQuantity(1000), "1.000");
  assert.equal(formatQuantity(1.5), "1,5");
});

test("formatSimDay: nhãn ngày mô phỏng", () => {
  assert.equal(formatSimDay(42), "Ngày mô phỏng 42");
});

test("formatImpact: clamp giá trị bất thường về 0.0", () => {
  assert.equal(formatImpact(50), "50.0");
  assert.equal(formatImpact(1000), "0.0");
  assert.equal(formatImpact(-1), "0.0");
  assert.equal(formatImpact(Number.NaN), "0.0");
  assert.equal(formatImpact(null), "0.0");
});

test("formatViral: clamp giá trị lớn", () => {
  assert.equal(formatViral(250), "250");
  assert.equal(formatViral(2000), "0");
  assert.equal(formatViral(-5), "0");
});

test("sanitizeTemplateVars: thay {var} bằng N/A", () => {
  assert.equal(sanitizeTemplateVars("Chào {name}"), "Chào N/A");
  assert.equal(sanitizeTemplateVars(""), "");
  assert.equal(sanitizeTemplateVars(null), "");
});

test("isValidDisplayValue: biên min/max", () => {
  assert.equal(isValidDisplayValue(5), true);
  assert.equal(isValidDisplayValue(20_000), false);
  assert.equal(isValidDisplayValue(5, 10, 20), false);
  assert.equal(isValidDisplayValue(Number.NaN), false);
});

// ── trading.ts (đồng bộ với core/config.py) ──────────────────────────────────
test("phí/thuế khớp hằng số backend", () => {
  assert.equal(TRADING_FEE_RATE, 0.0015);
  assert.equal(SELL_TAX_RATE, 0.001);
  assert.equal(estimateFee(1_000_000), 1500);
  assert.equal(estimateSellTax(1_000_000), 1000);
});

// ── roles.ts ─────────────────────────────────────────────────────────────────
test("homePathForRole: theo role, mặc định dashboard", () => {
  assert.equal(homePathForRole("admin"), ROLE_HOME.admin);
  assert.equal(homePathForRole("host"), ROLE_HOME.host);
  assert.equal(homePathForRole("user"), ROLE_HOME.user);
  assert.equal(homePathForRole("lạ"), "/dashboard");
  assert.equal(homePathForRole(null), "/dashboard");
});

// ── contest.ts ───────────────────────────────────────────────────────────────
test("nhãn contest: dịch và fallback", () => {
  assert.equal(templateLabel("classic"), "Cổ điển");
  assert.equal(templateLabel(null), "Cổ điển");
  assert.equal(difficultyLabel("hard"), "Khó");
  assert.equal(statusLabel("ended"), "Đã kết thúc");
  assert.equal(statusLabel(undefined), "—");
});
