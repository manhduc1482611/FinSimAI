/**
 * Saved store — danh sách nội dung ĐÃ LƯU (tin tức + bài xã hội) của user.
 * Dùng làm nguồn cho tab "Đã lưu" trên trang Tin tức / Xã hội và trang /saved.
 * `applyToggle` giúp xoá item ngay khi user bỏ lưu ngay tại danh sách đã lưu.
 */
import { create } from "zustand";

import type { SavedContentItem } from "@finsim/shared-types/generated/api-types";

import { toRequestError } from "@/services/api";
import { listSaves } from "@/services/saves";
import type { AsyncStatus } from "@/types/api";

type SavedType = "news" | "social";

interface SavedState {
  news: SavedContentItem[];
  social: SavedContentItem[];
  newsTotal: number;
  socialTotal: number;
  status: AsyncStatus;
  error: string | null;
  loadNews: () => Promise<void>;
  loadSocial: () => Promise<void>;
  /** Đồng bộ trạng thái khi toggle lưu từ nơi khác (bỏ lưu → xoá khỏi local). */
  applyToggle: (contentType: SavedType, contentId: string, saved: boolean) => void;
  reset: () => void;
}

export const useSavedStore = create<SavedState>()((set) => ({
  news: [],
  social: [],
  newsTotal: 0,
  socialTotal: 0,
  status: "idle",
  error: null,

  loadNews: async () => {
    set({ status: "loading", error: null });
    try {
      const response = await listSaves({ content_type: "news", limit: 200 });
      set({
        news: response.items,
        newsTotal: response.total,
        status: "success",
      });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
    }
  },

  loadSocial: async () => {
    set({ status: "loading", error: null });
    try {
      const response = await listSaves({ content_type: "social", limit: 200 });
      set({
        social: response.items,
        socialTotal: response.total,
        status: "success",
      });
    } catch (error) {
      set({ status: "error", error: toRequestError(error).detail });
    }
  },

  applyToggle: (contentType, contentId, saved) => {
    if (saved) {
      // Lưu mới: item chưa có trong local — các tab sẽ load lại khi mở.
      return;
    }
    if (contentType === "news") {
      set((state) => ({
        news: state.news.filter((item) => item.content_id !== contentId),
        newsTotal: Math.max(0, state.newsTotal - 1),
      }));
    } else {
      set((state) => ({
        social: state.social.filter((item) => item.content_id !== contentId),
        socialTotal: Math.max(0, state.socialTotal - 1),
      }));
    }
  },

  reset: () => {
    set({
      news: [],
      social: [],
      newsTotal: 0,
      socialTotal: 0,
      status: "idle",
      error: null,
    });
  },
}));