/**
 * Auth store — phiên đăng nhập, user hiện tại, token.
 *
 * Token persist trong localStorage (chỉ client); SSR luôn khởi tạo rỗng rồi
 * hydrate trong `AuthProvider` (useEffect) để tránh hydration mismatch.
 */
import { create } from "zustand";

import type {
  LoginRequest,
  RegisterRequest,
  UserResponse,
} from "@finsim/shared-types/generated/api-types";

import { apiClient, readStoredToken, toRequestError } from "@/services/api";
import { fetchCurrentUser, login as apiLogin, register as apiRegister } from "@/services/auth";
import type { AsyncStatus } from "@/types/api";

interface AuthState {
  user: UserResponse | null;
  token: string | null;
  status: AsyncStatus;
  error: string | null;
  /** Nạp token + user đã lưu từ localStorage khi app mount. */
  hydrate: () => void;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (body: RegisterRequest) => Promise<void>;
  fetchMe: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  token: null,
  status: "idle",
  error: null,

  hydrate: () => {
    if (get().token) {
      return;
    }
    const stored = readStoredToken();
    if (stored) {
      apiClient.setAccessToken(stored);
      set({ token: stored });
      void get().fetchMe();
    }
  },

  login: async (credentials) => {
    set({ status: "loading", error: null });
    try {
      const { access_token: accessToken } = await apiLogin(credentials);
      apiClient.setAccessToken(accessToken);
      set({ token: accessToken, status: "success" });
      await get().fetchMe();
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
      throw error;
    }
  },

  register: async (body) => {
    set({ status: "loading", error: null });
    try {
      await apiRegister(body);
      // Đăng ký xong → đăng nhập luôn để bắt đầu phiên.
      await get().login({
        email: body.email,
        password: body.password,
      });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
      throw error;
    }
  },

  fetchMe: async () => {
    const token = get().token;
    if (!token) {
      // Chưa đăng nhập — không phải lỗi, giữ nguyên trạng thái.
      set({ status: "idle" });
      return;
    }
    set({ status: "loading", error: null });
    try {
      const user = await fetchCurrentUser();
      set({ user, status: "success" });
    } catch (error) {
      const { status } = toRequestError(error);
      if (status === 401) {
        // Token hết hạn / không hợp lệ → xoá phiên sạch.
        apiClient.setAccessToken(null);
        set({ user: null, token: null, status: "idle", error: null });
      } else {
        set({ status: "error", error: toRequestError(error).detail });
      }
    }
  },

  logout: () => {
    apiClient.setAccessToken(null);
    set({ user: null, token: null, status: "idle", error: null });
  },
}));
