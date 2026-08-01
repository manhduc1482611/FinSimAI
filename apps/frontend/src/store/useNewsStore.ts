/**
 * News store — danh sách tin tức, bộ lọc và trạng thái tải.
 */
import { create } from "zustand";

import type { NewsResponse } from "@finsim/shared-types/generated/api-types";

import { toRequestError } from "@/services/api";
import { listNews as apiListNews } from "@/services/news";
import type { AsyncStatus } from "@/types/api";

export interface NewsFilters {
  category?: string;
  sentiment?: string;
  skip: number;
  limit: number;
}

interface NewsState {
  items: NewsResponse[];
  total: number;
  status: AsyncStatus;
  error: string | null;
  filters: NewsFilters;
  setFilters: (patch: Partial<NewsFilters>) => void;
  fetchNews: () => Promise<void>;
  reset: () => void;
}

export const useNewsStore = create<NewsState>()((set, get) => ({
  items: [],
  total: 0,
  status: "idle",
  error: null,
  filters: { skip: 0, limit: 20 },

  setFilters: (patch) => {
    // Đổi bộ lọc → quay về trang đầu.
    set({ filters: { ...get().filters, ...patch, skip: 0 } });
    void get().fetchNews();
  },

  fetchNews: async () => {
    set({ status: "loading", error: null });
    try {
      const { filters } = get();
      const response = await apiListNews(filters);
      set({ items: response.items, total: response.total, status: "success" });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
    }
  },

  reset: () => {
    set({
      items: [],
      total: 0,
      status: "idle",
      error: null,
      filters: { skip: 0, limit: 20 },
    });
  },
}));

