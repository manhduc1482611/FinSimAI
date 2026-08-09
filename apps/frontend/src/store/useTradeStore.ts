/**
 * Trade store — danh mục (portfolio), lệnh đã đặt và trạng thái đặt lệnh.
 *
 * Các giá trị `total_nav`/`total_cash`/`quantity`/`price` từ backend đều là
 * Decimal dạng **string**; UI tính toán phải parse qua `parseDecimal`.
 */
import { create } from "zustand";

import type {
  OrderRequest,
  OrderResponse,
  PortfolioListResponse,
} from "@finsim/shared-types/generated/api-types";

import { toRequestError } from "@/services/api";
import {
  cancelOrder as apiCancelOrder,
  createOrder as apiCreateOrder,
  fetchPortfolio as apiFetchPortfolio,
  listOrders as apiListOrders,
} from "@/services/trade";
import type { AsyncStatus } from "@/types/api";

interface TradeState {
  portfolio: PortfolioListResponse | null;
  orders: OrderResponse[];
  /** Trạng thái tải danh mục / lệnh. */
  status: AsyncStatus;
  /** Trạng thái đặt lệnh (riêng để UI hiển thị nút chờ). */
  orderStatus: AsyncStatus;
  /** Trạng thái huỷ lệnh (nút Huỷ chờ khi đang gọi API). */
  cancelStatus: AsyncStatus;
  error: string | null;
  lastOrder: OrderResponse | null;
  fetchPortfolio: () => Promise<void>;
  listOrders: () => Promise<void>;
  submitOrder: (body: OrderRequest) => Promise<OrderResponse>;
  cancelOrder: (orderId: string) => Promise<void>;
  reset: () => void;
}

export const useTradeStore = create<TradeState>()((set, get) => ({
  portfolio: null,
  orders: [],
  status: "idle",
  orderStatus: "idle",
  cancelStatus: "idle",
  error: null,
  lastOrder: null,

  fetchPortfolio: async () => {
    set({ status: "loading", error: null });
    try {
      const portfolio = await apiFetchPortfolio();
      set({ portfolio, status: "success" });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
    }
  },

  listOrders: async () => {
    set({ status: "loading", error: null });
    try {
      const orders = await apiListOrders({ limit: 50 });
      set({ orders, status: "success" });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
    }
  },

  submitOrder: async (body) => {
    set({ orderStatus: "loading", error: null });
    try {
      const order = await apiCreateOrder(body);
      set({ orderStatus: "success", lastOrder: order });
      // Sau khi đặt lệnh, làm mới danh mục + danh sách lệnh.
      await Promise.all([get().fetchPortfolio(), get().listOrders()]);
      return order;
    } catch (error) {
      set({ orderStatus: "error", error: toRequestError(error).detail });
      throw error;
    }
  },

  cancelOrder: async (orderId) => {
    set({ cancelStatus: "loading", error: null });
    try {
      await apiCancelOrder(orderId);
      set({ cancelStatus: "success" });
      await Promise.all([get().fetchPortfolio(), get().listOrders()]);
    } catch (error) {
      set({ cancelStatus: "error", error: toRequestError(error).detail });
      throw error;
    }
  },

  reset: () => {
    set({
      portfolio: null,
      orders: [],
      status: "idle",
      orderStatus: "idle",
      cancelStatus: "idle",
      error: null,
      lastOrder: null,
    });
  },
}));
