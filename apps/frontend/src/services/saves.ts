/**
 * Saves service — `/api/v1/saves` (lưu/đánh dấu tin tức & bài xã hội).
 * Toggle yêu cầu đăng nhập; list trả về item kèm nested news/social.
 */
import type {
  ContentSaveToggleRequest,
  ContentSaveToggleResponse,
  SavedContentListResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

export interface ListSavesQuery extends ListQuery {
  content_type?: "news" | "social";
}

/** POST /saves/toggle — lưu hoặc bỏ lưu một nội dung (cần đăng nhập). */
export function toggleSave(body: ContentSaveToggleRequest): Promise<ContentSaveToggleResponse> {
  return apiClient.post<ContentSaveToggleResponse>("/api/v1/saves/toggle", body);
}

/** GET /saves — danh sách nội dung đã lưu của user hiện tại. */
export function listSaves(query: ListSavesQuery = {}): Promise<SavedContentListResponse> {
  return apiClient.get<SavedContentListResponse>("/api/v1/saves", query);
}