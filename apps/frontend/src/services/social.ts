/**
 * Social service — gọi API `/api/v1/social` (diễn đàn xã hội mô phỏng).
 *
 * - Đăng bài, like/unlike, bình luận là thao tác có auth (401 nếu chưa đăng nhập).
 * - Đọc feed luôn công khai (backend xác thực tùy chọn để gắn `liked_by_me`).
 */
import { apiClient, buildQueryString, type ListQuery } from "@/services/api";
import type {
  SocialCommentCreate,
  SocialCommentListResponse,
  SocialCommentResponse,
  SocialLikeResponse,
  SocialPostCreate,
  SocialPostListResponse,
  SocialPostResponse,
} from "@finsim/shared-types/generated/api-types";

export interface ListSocialPostsQuery extends ListQuery {
  persona_type?: string | null;
  sentiment?: string | null;
}

export async function listSocialPosts(
  query: ListSocialPostsQuery = {},
): Promise<SocialPostListResponse> {
  const search = buildQueryString({
    persona_type: query.persona_type,
    sentiment: query.sentiment,
    skip: query.skip,
    limit: query.limit,
  });
  return apiClient.get<SocialPostListResponse>(`/api/v1/social${search}`);
}

export function getSocialPost(postId: string): Promise<SocialPostResponse> {
  return apiClient.get<SocialPostResponse>(`/api/v1/social/${postId}`);
}

/** POST /social — đăng bài mới (cần đăng nhập). */
export function createSocialPost(body: SocialPostCreate): Promise<SocialPostResponse> {
  return apiClient.post<SocialPostResponse>("/api/v1/social", body);
}

/** POST /social/{id}/like — bật/tắt like (cần đăng nhập). */
export function toggleSocialLike(postId: string): Promise<SocialLikeResponse> {
  return apiClient.post<SocialLikeResponse>(`/api/v1/social/${postId}/like`);
}

/** GET /social/{id}/comments — danh sách bình luận (mặc định mới nhất). */
export function listSocialComments(
  postId: string,
  query: ListQuery = {},
): Promise<SocialCommentListResponse> {
  return apiClient.get<SocialCommentListResponse>(
    `/api/v1/social/${postId}/comments`,
    query,
  );
}

/** POST /social/{id}/comments — thêm bình luận (cần đăng nhập). */
export function createSocialComment(
  postId: string,
  body: SocialCommentCreate,
): Promise<SocialCommentResponse> {
  return apiClient.post<SocialCommentResponse>(
    `/api/v1/social/${postId}/comments`,
    body,
  );
}
