import assert from "node:assert/strict";
import { test } from "node:test";

import {
  getPreferredBackend,
  getRenderApiBaseUrl,
  getSsApiBaseUrl,
  isDemoMode,
  isFailoverEnabled,
} from "../src/services/api.ts";

test("Failover detection: kiểm tra cấu hình URL và fallback", () => {
  // Mặc định khi chạy test (chưa set env demo mode)
  assert.equal(isDemoMode(), false);

  // Preferred backend mặc định là render
  assert.equal(getPreferredBackend(), "render");

  // getRenderApiBaseUrl trả về fallback hoặc localhost khi không có env
  const renderUrl = getRenderApiBaseUrl();
  assert.ok(renderUrl.length > 0);
});

test("isFailoverEnabled: logic kích hoạt tự động khi có 2 backend", () => {
  // Khi không có SS_API_URL thì không thể failover sang Apps Script
  const hasAppsScript = Boolean(getSsApiBaseUrl());
  if (!hasAppsScript) {
    assert.equal(isFailoverEnabled(), false);
  }
});
