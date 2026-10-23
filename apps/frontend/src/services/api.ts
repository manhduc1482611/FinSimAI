/**
 * API Client base — fetch wrapper với type-safety 100% (không dùng `any`).
 *
 * - Tự gắn `Authorization: Bearer <token>` khi có token.
 * - Chuẩn hoá mọi lỗi thành `ApiClientError` (status + detail), kể cả lỗi
 *   validation của FastAPI (`detail` là mảng) và lỗi mạng.
 * - Base URL từ `NEXT_PUBLIC_API_URL` (mặc định http://localhost:8000).
 */
import type {
  ApiError,
  JsonValue,
} from "@finsim/shared-types/generated/api-types";

import type { RequestError } from "@/types/api";

const DEFAULT_API_URL = "http://localhost:8000";

export type BackendTarget = "render" | "appscript";

export interface FailoverEventDetail {
  from: BackendTarget;
  to: BackendTarget;
  reason: string;
}

/**
 * Demo mode (KHÔNG cần backend) — chỉ bật khi khai báo tường minh:
 * - NEXT_PUBLIC_DEMO_MODE=true        : dùng Google Apps Script làm backend.
 * - NEXT_PUBLIC_SS_API_URL (BẮT BUỘC) : URL web app của Apps Script (doGet/doPost).
 */
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

export function getSsApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_SS_API_URL?.trim().replace(/\/+$/, "") ?? "";
}

export function getRenderApiBaseUrl(): string {
  const apiUrlFromEnv = process.env.NEXT_PUBLIC_API_URL;
  if (apiUrlFromEnv) {
    return apiUrlFromEnv.trim().replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host && host !== "localhost" && host !== "127.0.0.1") {
      return `${window.location.protocol}//${host}:8000`;
    }
  }
  return DEFAULT_API_URL;
}

/**
 * Kiểm tra xem chế độ Hybrid Failover (Render <-> Apps Script) có được kích hoạt không.
 * Tự động bật khi cả 2 URL đều được cấu hình (hoặc bật bằng NEXT_PUBLIC_FAILOVER_ENABLED=true).
 */
export function isFailoverEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_FAILOVER_ENABLED === "false") {
    return false;
  }
  const hasRender = Boolean(getRenderApiBaseUrl());
  const hasAppScript = Boolean(getSsApiBaseUrl());
  return (
    process.env.NEXT_PUBLIC_FAILOVER_ENABLED === "true" ||
    (hasRender && hasAppScript && !isDemoMode())
  );
}

export function getPreferredBackend(): BackendTarget {
  return process.env.NEXT_PUBLIC_PRIMARY_BACKEND === "appscript"
    ? "appscript"
    : "render";
}

/**
 * Base URL của API — ưu tiên `NEXT_PUBLIC_API_URL` (Render).
 */
export function getApiBaseUrl(): string {
  if (isDemoMode()) {
    return getSsApiBaseUrl();
  }
  return getRenderApiBaseUrl();
}

const TOKEN_STORAGE_KEY = "finsim.access_token";
const REFRESH_TOKEN_STORAGE_KEY = "finsim.refresh_token";

export function readStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // localStorage không khả dụng (private mode) — phiên chỉ sống trong RAM.
  }
}

export function readStoredRefreshToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredRefreshToken(token: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (token) {
      window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // localStorage không khả dụng (private mode) — phiên chỉ sống trong RAM.
  }
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Chuẩn hoá detail lỗi của FastAPI.
 * - `detail: string` → giữ nguyên.
 * - `detail: array` (validation error) → nối thông báo các lỗi.
 */
export function normalizeErrorDetail(detail: JsonValue | undefined): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts: string[] = [];
    for (const item of detail) {
      if (typeof item === "object" && item !== null && !Array.isArray(item)) {
        const msg = item.msg;
        if (typeof msg === "string") {
          parts.push(msg);
        }
      }
    }
    return parts.length > 0 ? parts.join(" · ") : "Yêu cầu không hợp lệ";
  }
  if (typeof detail === "object" && detail !== null) {
    const obj = detail as Record<string, JsonValue>;
    if (typeof obj.message === "string") {
      return obj.message;
    }
    if (typeof obj.reason === "string") {
      return obj.reason;
    }
    return JSON.stringify(detail);
  }
  return "Đã xảy ra lỗi không xác định";
}

/** Chuyển bất kỳ lỗi nào thành `RequestError` để UI hiển thị. */
export function toRequestError(error: unknown): RequestError {
  if (error instanceof ApiClientError) {
    return { status: error.status, detail: error.detail };
  }
  if (error instanceof Error) {
    return { status: 0, detail: error.message };
  }
  return { status: 0, detail: "Lỗi không xác định" };
}

/** Query params chuẩn cho mọi endpoint list (mặc định của backend). */
export interface ListQuery {
  skip?: number;
  limit?: number;
}

/** Shape bất kỳ cho query string; giá trị null/undefined bị bỏ qua. */
export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>;

export function buildQueryString<T extends object>(
  params: T | undefined,
): string {
  if (!params) {
    return "";
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) {
      continue;
    }
    search.set(key, String(value));
  }
  const raw = search.toString();
  return raw ? `?${raw}` : "";
}

class FailoverEligibleError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "FailoverEligibleError";
    this.status = status;
  }
}

class ApiClient {
  public readonly resolveBaseUrl: () => string;
  private accessToken: string | null;
  private refreshToken: string | null;
  /** Promise refresh đang chạy dở — nhiều request 401 cùng lúc chỉ gọi 1 lần. */
  private refreshing: Promise<string | null> | null = null;

  /** Circuit breaker state cho từng backend */
  private brokenUntil: Record<BackendTarget, number> = {
    render: 0,
    appscript: 0,
  };
  private breakerCooldownMs = 30000;

  constructor(resolveBaseUrl: () => string) {
    this.resolveBaseUrl = resolveBaseUrl;
    this.accessToken = null;
    this.refreshToken = null;
  }

  getCurrentBackend(): BackendTarget {
    if (isDemoMode()) return "appscript";
    if (!isFailoverEnabled()) return "render";

    const preferred = getPreferredBackend();
    const alternate: BackendTarget = preferred === "render" ? "appscript" : "render";
    const now = Date.now();

    if (this.brokenUntil[preferred] > now) {
      if (this.brokenUntil[alternate] <= now) {
        return alternate;
      }
    }
    return preferred;
  }

  tripCircuitBreaker(target: BackendTarget, reason: string): void {
    this.brokenUntil[target] = Date.now() + this.breakerCooldownMs;
    const alternate: BackendTarget = target === "render" ? "appscript" : "render";
    console.warn(
      `[FinSim Failover] Backend "${target}" quá tải hoặc gián đoạn (${reason}). Tự động chuyển tải sang "${alternate}" (cooldown 30s).`,
    );
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent<FailoverEventDetail>("finsim:backend-switched", {
          detail: { from: target, to: alternate, reason },
        }),
      );
    }
  }

  resetCircuitBreaker(target: BackendTarget): void {
    this.brokenUntil[target] = 0;
  }

  private extractUserIdFromToken(): string | null {
    const token = this.token;
    if (!token) return null;
    try {
      const parts = token.split(".");
      if (parts.length === 3) {
        const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
        if (typeof window !== "undefined" && typeof window.atob === "function") {
          const json = decodeURIComponent(
            window
              .atob(base64)
              .split("")
              .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
              .join(""),
          );
          const payload = JSON.parse(json);
          return payload.sub ?? payload.id ?? null;
        } else if (typeof Buffer !== "undefined") {
          const json = Buffer.from(base64, "base64").toString("utf-8");
          const payload = JSON.parse(json);
          return payload.sub ?? payload.id ?? null;
        }
      }
    } catch {
      // ignore
    }
    return null;
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
    writeStoredToken(token);
  }

  setRefreshToken(token: string | null): void {
    this.refreshToken = token;
    writeStoredRefreshToken(token);
  }

  setTokens(accessToken: string | null, refreshToken: string | null): void {
    this.setAccessToken(accessToken);
    this.setRefreshToken(refreshToken);
  }

  clearTokens(): void {
    this.accessToken = null;
    this.refreshToken = null;
    writeStoredToken(null);
    writeStoredRefreshToken(null);
  }

  private get token(): string | null {
    if (this.accessToken !== null) {
      return this.accessToken;
    }
    this.accessToken = readStoredToken();
    return this.accessToken;
  }

  private get storedRefreshToken(): string | null {
    if (this.refreshToken !== null) {
      return this.refreshToken;
    }
    this.refreshToken = readStoredRefreshToken();
    return this.refreshToken;
  }

  /** Gọi /auth/refresh một lần (dùng chung cho mọi request 401 đang chờ). */
  private async tryRefresh(): Promise<string | null> {
    const refreshToken = this.storedRefreshToken;
    if (!refreshToken) {
      return null;
    }
    if (!this.refreshing) {
      this.refreshing = (async () => {
        try {
          const response = await fetch(
            `${getRenderApiBaseUrl()}/api/v1/auth/refresh`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: refreshToken }),
            },
          );
          if (!response.ok) {
            return null;
          }
          const data = (await response.json()) as {
            access_token?: string;
            refresh_token?: string;
          };
          if (!data.access_token) {
            return null;
          }
          this.setTokens(data.access_token, data.refresh_token ?? refreshToken);
          return data.access_token;
        } catch {
          return null;
        } finally {
          this.refreshing = null;
        }
      })();
    }
    return this.refreshing;
  }

  /** Thực hiện request đến Google Apps Script (REST dạng Web App). */
  private async fetchFromAppScript<T>(
    path: string,
    init: RequestInit,
    timeoutMs = 12000,
  ): Promise<T> {
    const base = getSsApiBaseUrl();
    if (!base) {
      throw new ApiClientError(
        0,
        "Chưa cấu hình URL Google Apps Script (NEXT_PUBLIC_SS_API_URL).",
      );
    }
    const body = init.body;
    const originalMethod = init.method ?? "GET";
    let targetPath = path;
    let method = originalMethod;
    if (method !== "GET" && method !== "POST") {
      targetPath = `${path}${path.includes("?") ? "&" : "?"}method=${method}`;
      method = "POST";
    }

    const userId = this.extractUserIdFromToken();
    if (userId && !targetPath.includes("demo_user=")) {
      targetPath = `${targetPath}${targetPath.includes("?") ? "&" : "?"}demo_user=${encodeURIComponent(userId)}`;
    }

    const headers: Record<string, string> = {};
    if (method !== "GET" && body !== undefined) {
      headers["Content-Type"] = "text/plain;charset=UTF-8";
    }

    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    try {
      const response = await fetch(
        `${base}?path=${encodeURIComponent(targetPath)}`,
        {
          ...init,
          method,
          headers,
          body: method !== "GET" ? body : undefined,
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        let errorDetail = response.statusText || `HTTP ${response.status}`;
        try {
          const apiError = (await response.json()) as ApiError;
          if (apiError?.detail) {
            errorDetail = normalizeErrorDetail(apiError.detail);
          }
        } catch {
          // ignore
        }
        if (response.status === 429 || response.status >= 500) {
          throw new FailoverEligibleError(response.status, errorDetail);
        }
        throw new ApiClientError(response.status, errorDetail);
      }

      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof ApiClientError || err instanceof FailoverEligibleError) {
        throw err;
      }
      const isAbort = controller.signal.aborted;
      const msg = isAbort
        ? `Apps Script hết thời gian phản hồi (${timeoutMs / 1000}s)`
        : err instanceof Error
          ? err.message
          : "Lỗi kết nối Apps Script";
      throw new FailoverEligibleError(0, msg);
    } finally {
      clearTimeout(timer);
    }
  }

  /** Thực hiện request đến Backend Gateway trên Render (FastAPI). */
  private async fetchFromRender<T>(
    path: string,
    init: RequestInit,
    allowRetry: boolean,
    timeoutMs = 7000,
  ): Promise<T> {
    const base = getRenderApiBaseUrl();
    const headers = new Headers(init.headers);
    const token = this.token;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const controller = new AbortController();
    const timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    try {
      const response = await fetch(`${base}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        if (
          response.status === 429 ||
          response.status === 502 ||
          response.status === 503 ||
          response.status === 504
        ) {
          throw new FailoverEligibleError(
            response.status,
            `Render phản hồi quá tải/lỗi cổng (HTTP ${response.status})`,
          );
        }

        if (
          response.status === 401 &&
          token !== null &&
          !path.includes("/auth/login")
        ) {
          if (path.includes("/auth/refresh")) {
            this.clearTokens();
            this.emitUnauthorized();
          } else if (allowRetry && (await this.tryRefresh())) {
            return this.fetchFromRender<T>(path, init, false, timeoutMs);
          } else {
            this.clearTokens();
            this.emitUnauthorized();
          }
        }

        let apiError: ApiError | null = null;
        try {
          const body = (await response.json()) as ApiError;
          if (typeof body.detail === "string") {
            apiError = body;
          } else {
            apiError = {
              detail: normalizeErrorDetail(body.detail),
            };
          }
        } catch {
          // Response không phải JSON
        }
        throw new ApiClientError(
          response.status,
          (apiError?.detail ?? response.statusText) || `HTTP ${response.status}`,
        );
      }

      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof ApiClientError || err instanceof FailoverEligibleError) {
        throw err;
      }
      const isAbort = controller.signal.aborted;
      const msg = isAbort
        ? `Render phản hồi quá lâu (${timeoutMs / 1000}s - có thể server đang cold start)`
        : err instanceof Error
          ? err.message
          : "Lỗi kết nối mạng đến Render";
      throw new FailoverEligibleError(0, msg);
    } finally {
      clearTimeout(timer);
    }
  }

  async request<T>(
    path: string,
    init: RequestInit = {},
    allowRetry = true,
  ): Promise<T> {
    if (isDemoMode() || (!isFailoverEnabled() && !getRenderApiBaseUrl())) {
      return this.fetchFromAppScript<T>(path, init);
    }
    if (!isFailoverEnabled()) {
      return this.fetchFromRender<T>(path, init, allowRetry);
    }

    const activeTarget = this.getCurrentBackend();
    const backupTarget: BackendTarget =
      activeTarget === "render" ? "appscript" : "render";

    try {
      const result =
        activeTarget === "render"
          ? await this.fetchFromRender<T>(path, init, allowRetry)
          : await this.fetchFromAppScript<T>(path, init);

      this.resetCircuitBreaker(activeTarget);
      return result;
    } catch (err: unknown) {
      if (err instanceof FailoverEligibleError) {
        this.tripCircuitBreaker(activeTarget, err.message);
        try {
          const backupResult =
            backupTarget === "render"
              ? await this.fetchFromRender<T>(path, init, allowRetry)
              : await this.fetchFromAppScript<T>(path, init);
          return backupResult;
        } catch (backupErr: unknown) {
          if (backupErr instanceof ApiClientError) {
            throw backupErr;
          }
          throw new ApiClientError(
            err.status,
            `${err.message}. Dự phòng (${backupTarget}) cũng thất bại: ${
              backupErr instanceof Error ? backupErr.message : String(backupErr)
            }`,
          );
        }
      }
      throw err;
    }
  }

  private emitUnauthorized(): void {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("finsim:unauthorized"));
    }
  }

  get<T>(path: string, params?: ListQuery): Promise<T> {
    return this.request<T>(`${path}${buildQueryString(params)}`, {
      method: "GET",
    });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body ?? {}),
    });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}

/** Singleton dùng chung toàn app. */
export const apiClient = new ApiClient(getApiBaseUrl);

/** URL base WebSocket — ưu tiên `NEXT_PUBLIC_WS_URL`, còn lại suy từ API base. */
export function getWsBaseUrl(): string {
  const wsEnv = process.env.NEXT_PUBLIC_WS_URL;
  if (wsEnv) {
    return wsEnv.endsWith("/") ? wsEnv.slice(0, -1) : wsEnv;
  }
  return getApiBaseUrl().replace(/^http/, "ws");
}
