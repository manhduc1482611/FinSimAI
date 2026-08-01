/**
 * Companies service — `/api/v1/companies`.
 */
import type {
  CompanyListResponse,
  CompanyResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

export interface CompanyQuery extends ListQuery {
  sector?: string;
  search?: string;
}

/** GET /companies → danh sách doanh nghiệp (lọc theo sector/search). */
export function listCompanies(
  query: CompanyQuery = {},
): Promise<CompanyListResponse> {
  return apiClient.get<CompanyListResponse>("/api/v1/companies", query);
}

/** GET /companies/{id} → chi tiết doanh nghiệp. */
export function getCompany(companyId: string): Promise<CompanyResponse> {
  return apiClient.get<CompanyResponse>(`/api/v1/companies/${companyId}`);
}
