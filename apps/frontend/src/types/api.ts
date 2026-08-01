/**
 * Type API dùng chung cho toàn Frontend.
 *
 * Toàn bộ kiểu dữ liệu từ Backend được sinh tự động từ Pydantic schemas
 * (scripts/generate_ts_types.py) và tập trung tại @finsim/shared-types.
 * File này chỉ re-export + khai báo thêm các kiểu "phối hợp" thuần Frontend.
 */
export * from "@finsim/shared-types/generated/api-types";

/** Query params phân trang chuẩn cho mọi endpoint list. */
export interface PaginationParams {
  skip?: number;
  limit?: number;
}

/** Trạng thái tải dữ liệu của một màn hình. */
export type AsyncStatus = "idle" | "loading" | "success" | "error";

/** Lỗi chuẩn hoá từ API (bọc detail của FastAPI). */
export interface RequestError {
  status: number;
  detail: string;
}
