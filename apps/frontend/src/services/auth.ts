/**
 * Auth service — giao tiếp với backend `/api/v1/auth` và `/api/v1/users`.
 */
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  WsTicketResponse,
} from "@finsim/shared-types/generated/api-types";

import { apiClient } from "@/services/api";

/** POST /auth/login → nhận access + refresh token. */
export function login(credentials: LoginRequest): Promise<TokenResponse> {
  return apiClient.post<TokenResponse>("/api/v1/auth/login", credentials);
}

/** POST /auth/refresh → xoay vòng cặp token (access cũ hết hạn). */
export function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  return apiClient.post<TokenResponse>("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });
}

/** POST /auth/register → tạo tài khoản mới, trả user đã tạo. */
export function register(body: RegisterRequest): Promise<UserResponse> {
  return apiClient.post<UserResponse>("/api/v1/auth/register", body);
}

/** GET /users/me → thông tin user hiện tại (cần token). */
export function fetchCurrentUser(): Promise<UserResponse> {
  return apiClient.get<UserResponse>("/api/v1/users/me");
}

/** POST /auth/ws-ticket → ticket single-use cho WebSocket handshake. */
export function fetchWsTicket(): Promise<WsTicketResponse> {
  return apiClient.post<WsTicketResponse>("/api/v1/auth/ws-ticket");
}
