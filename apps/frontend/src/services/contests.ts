/**
 * Contests service — `/api/v1/contests` (host tạo/quản lý, user browse/join).
 */
import type {
  CompanyListResponse,
  ContestCreateRequest,
  ContestJoinResponse,
  ContestListResponse,
  ContestResponse,
  ContestUpdateRequest,
  NewsListResponse,
  SocialPostListResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

/** POST /contests → tạo contest từ vài lựa chọn (FR-4). */
export function createContest(body: ContestCreateRequest): Promise<ContestResponse> {
  return apiClient.post<ContestResponse>("/api/v1/contests", body);
}

/** GET /contests → danh sách contest (active + của chính host nếu là host). */
export function listContests(query: ListQuery = {}): Promise<ContestListResponse> {
  return apiClient.get<ContestListResponse>("/api/v1/contests", query);
}

/** GET /contests/{slug} → chi tiết contest + config đã parse. */
export function getContest(slug: string): Promise<ContestResponse> {
  return apiClient.get<ContestResponse>(`/api/v1/contests/${slug}`);
}

/** PATCH /contests/{slug} → cập nhật contest (host sở hữu hoặc admin). */
export function updateContest(
  slug: string,
  body: ContestUpdateRequest,
): Promise<ContestResponse> {
  return apiClient.patch<ContestResponse>(`/api/v1/contests/${slug}`, body);
}

/** DELETE /contests/{slug} → xoá mềm (status='ended'), chỉ host sở hữu. */
export function deleteContest(slug: string): Promise<ContestResponse> {
  return apiClient.delete<ContestResponse>(`/api/v1/contests/${slug}`);
}

/** POST /contests/{slug}/activate → chạy pipeline tự sinh rồi chuyển active. */
export function activateContest(slug: string): Promise<ContestResponse> {
  return apiClient.post<ContestResponse>(`/api/v1/contests/${slug}/activate`);
}

/** POST /contests/{slug}/join → user tham gia contest (cần contest active). */
export function joinContest(slug: string): Promise<ContestJoinResponse> {
  return apiClient.post<ContestJoinResponse>(`/api/v1/contests/${slug}/join`);
}

/** GET /contests/{slug}/companies → công ty của contest (đã join hoặc host). */
export function listContestCompanies(
  slug: string,
  query: ListQuery = {},
): Promise<CompanyListResponse> {
  return apiClient.get<CompanyListResponse>(`/api/v1/contests/${slug}/companies`, query);
}

/** GET /contests/{slug}/news → tin tức của contest. */
export function listContestNews(
  slug: string,
  query: ListQuery = {},
): Promise<NewsListResponse> {
  return apiClient.get<NewsListResponse>(`/api/v1/contests/${slug}/news`, query);
}

/** GET /contests/{slug}/social-posts → bài đăng xã hội của contest. */
export function listContestSocialPosts(
  slug: string,
  query: ListQuery = {},
): Promise<SocialPostListResponse> {
  return apiClient.get<SocialPostListResponse>(`/api/v1/contests/${slug}/social-posts`, query);
}
