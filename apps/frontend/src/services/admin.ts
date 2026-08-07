/**
 * Admin service — `/api/v1/admin` (chỉ admin; FR-2, FR-3).
 */
import type {
  AdminContestListResponse,
  AdminContestResponse,
  AdminContestStatusUpdate,
  AdminRoleUpdate,
  AdminStatusUpdate,
  AdminUserListResponse,
  AdminUserResponse,
  CompanyListResponse,
  NewsListResponse,
  SocialPostListResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

export interface AdminUserQuery extends ListQuery {
  role?: string;
  search?: string;
}

/** GET /admin/users → toàn bộ user (filter role/search, phân trang). */
export function listUsers(query: AdminUserQuery = {}): Promise<AdminUserListResponse> {
  return apiClient.get<AdminUserListResponse>("/api/v1/admin/users", query);
}

/** PATCH /admin/users/{id}/role → cấp/thu hồi role (user/host/admin). */
export function updateUserRole(
  userId: string,
  body: AdminRoleUpdate,
): Promise<AdminUserResponse> {
  return apiClient.patch<AdminUserResponse>(`/api/v1/admin/users/${userId}/role`, body);
}

/** PATCH /admin/users/{id}/status → khoá/mở khoá user. */
export function updateUserStatus(
  userId: string,
  body: AdminStatusUpdate,
): Promise<AdminUserResponse> {
  return apiClient.patch<AdminUserResponse>(`/api/v1/admin/users/${userId}/status`, body);
}

export interface AdminContestQuery extends ListQuery {
  status?: string;
}

/** GET /admin/contests → mọi contest + số member. */
export function listAllContests(
  query: AdminContestQuery = {},
): Promise<AdminContestListResponse> {
  return apiClient.get<AdminContestListResponse>("/api/v1/admin/contests", query);
}

/** PATCH /admin/contests/{id}/status → chuyển draft/active/ended. */
export function updateContestStatus(
  contestId: string,
  body: AdminContestStatusUpdate,
): Promise<AdminContestResponse> {
  return apiClient.patch<AdminContestResponse>(
    `/api/v1/admin/contests/${contestId}/status`,
    body,
  );
}

/** GET /admin/companies → view toàn cục công ty (lọc contest_id nếu muốn). */
export function listAllCompanies(
  query: ListQuery & { contest_id?: string } = {},
): Promise<CompanyListResponse> {
  return apiClient.get<CompanyListResponse>("/api/v1/admin/companies", query);
}

/** GET /admin/news → view toàn cục tin tức. */
export function listAllNews(
  query: ListQuery & { contest_id?: string } = {},
): Promise<NewsListResponse> {
  return apiClient.get<NewsListResponse>("/api/v1/admin/news", query);
}

/** GET /admin/social-posts → view toàn cục bài đăng xã hội. */
export function listAllSocialPosts(
  query: ListQuery & { contest_id?: string } = {},
): Promise<SocialPostListResponse> {
  return apiClient.get<SocialPostListResponse>("/api/v1/admin/social-posts", query);
}
