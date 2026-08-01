/**
 * Trade service — `/api/v1/trades`.
 */
import type {
  OrderRequest,
  OrderResponse,
  PortfolioListResponse,
} from "@finsim/shared-types/generated/api-types";

import type { ListQuery } from "@/services/api";
import { apiClient } from "@/services/api";

export interface OrderQuery extends ListQuery {
  status?: string;
}

/** GET /trades/portfolio → danh mục + tổng NAV/cash. */
export function fetchPortfolio(): Promise<PortfolioListResponse> {
  return apiClient.get<PortfolioListResponse>("/api/v1/trades/portfolio");
}

/** GET /trades/orders → danh sách lệnh đã đặt (theo trạng thái). */
export function listOrders(query: OrderQuery = {}): Promise<OrderResponse[]> {
  return apiClient.get<OrderResponse[]>("/api/v1/trades/orders", query);
}

/** POST /trades/orders → đặt lệnh mới. */
export function createOrder(body: OrderRequest): Promise<OrderResponse> {
  return apiClient.post<OrderResponse>("/api/v1/trades/orders", body);
}
