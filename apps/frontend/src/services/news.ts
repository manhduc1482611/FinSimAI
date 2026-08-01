/**
 * News service — `/api/v1/news`.
 */
import type {
  NewsListResponse,
  NewsResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

export interface NewsQuery extends ListQuery {
  category?: string;
  sentiment?: string;
}

/** GET /news → danh sách tin tức (có thể lọc theo category/sentiment). */
export function listNews(query: NewsQuery = {}): Promise<NewsListResponse> {
  return apiClient.get<NewsListResponse>("/api/v1/news", query);
}

/** GET /news/{id} → chi tiết một tin tức. */
export function getNews(newsId: string): Promise<NewsResponse> {
  return apiClient.get<NewsResponse>(`/api/v1/news/${newsId}`);
}
