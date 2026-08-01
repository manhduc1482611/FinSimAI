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
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL;

const TOKEN_STORAGE_KEY = "finsim.access_token";

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
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export function buildQueryString<T extends object>(params: T | undefined): string {
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

class ApiClient {
  readonly baseUrl: string;
  private accessToken: string | null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
    this.accessToken = null;
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
    writeStoredToken(token);
  }

  private get token(): string | null {
    if (this.accessToken !== null) {
      return this.accessToken;
    }
    this.accessToken = readStoredToken();
    return this.accessToken;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    const token = this.token;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });

    if (!response.ok) {
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
        // Response không phải JSON — dùng status text.
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
export const apiClient = new ApiClient(API_BASE_URL);

/** URL base WebSocket suy ra từ env hoặc từ API base (http → ws, https → wss). */
export function getWsBaseUrl(): string {
  const wsEnv = process.env.NEXT_PUBLIC_WS_URL;
  if (wsEnv) {
    return wsEnv.endsWith("/") ? wsEnv.slice(0, -1) : wsEnv;
  }
  if (API_BASE_URL.startsWith("https://")) {
    return API_BASE_URL.replace(/^https:\/\//, "wss://");
  }
  if (API_BASE_URL.startsWith("http://")) {
    return API_BASE_URL.replace(/^http:\/\//, "ws://");
  }
  return API_BASE_URL;
}
