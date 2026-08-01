/**
 * OrderTable — lịch sử lệnh: trạng thái, loại, giá, khối lượng, lệnh đã khớp.
 */
"use client";

import { Badge, type BadgeVariant } from "@/components/common/Badge";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { Skeleton } from "@/components/common/Skeleton";
import { formatDateTime, formatNumber, formatQuantity, parseDecimal } from "@/utils/format";
import type { CompanyResponse, OrderResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";

const STATUS_VARIANT: Record<OrderResponse["status"], BadgeVariant> = {
  pending: "warning",
  filled: "success",
  partially_filled: "info",
  cancelled: "neutral",
  rejected: "danger",
};

const STATUS_LABEL: Record<OrderResponse["status"], string> = {
  pending: "Chờ khớp",
  filled: "Đã khớp",
  partially_filled: "Khớp một phần",
  cancelled: "Đã hủy",
  rejected: "Từ chối",
};

const TYPE_LABEL: Record<OrderResponse["type"], string> = {
  market: "Thị trường",
  limit: "Giới hạn",
};

export interface OrderTableProps {
  orders: OrderResponse[];
  companies: CompanyResponse[];
  status: AsyncStatus;
  error: string | null;
  onRetry: () => void;
}

export function OrderTable({ orders, companies, status, error, onRetry }: OrderTableProps) {
  const symbolOf = (companyId: string): string =>
    companies.find((company) => company.id === companyId)?.symbol ?? companyId;

  return (
    <Card>
      <CardHeader
        title="Lịch sử lệnh"
        description={`${orders.length} lệnh gần nhất`}
        action={
          <button
            type="button"
            className="text-xs font-medium text-brand-600 hover:underline disabled:cursor-wait disabled:opacity-50"
            onClick={onRetry}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Đang tải..." : "Làm mới"}
          </button>
        }
      />
      <CardBody className="px-0 py-0">
        {status === "loading" ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
          </div>
        ) : status === "error" ? (
          <p className="p-4 text-sm text-red-600">
            {error ?? "Không tải được lịch sử lệnh."}{" "}
            <button type="button" className="font-semibold underline" onClick={onRetry}>
              Thử lại
            </button>
          </p>
        ) : orders.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-ink-500">
            Chưa có lệnh nào. Đặt lệnh đầu tiên của bạn ở panel bên cạnh.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-200 text-xs uppercase tracking-wide text-ink-400">
                  <th className="px-4 py-2 font-semibold">Mã</th>
                  <th className="px-4 py-2 font-semibold">Hướng</th>
                  <th className="px-4 py-2 font-semibold">Loại</th>
                  <th className="px-4 py-2 text-right font-semibold">Giá</th>
                  <th className="px-4 py-2 text-right font-semibold">Khối lượng</th>
                  <th className="px-4 py-2 text-right font-semibold">Đã khớp</th>
                  <th className="px-4 py-2 font-semibold">Trạng thái</th>
                  <th className="px-4 py-2 text-right font-semibold">Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id} className="border-b border-ink-100 last:border-0">
                    <td className="px-4 py-3 font-bold text-ink-900">
                      {symbolOf(order.company_id)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          order.side === "buy" ? "font-semibold text-emerald-600" : "font-semibold text-red-600"
                        }
                      >
                        {order.side === "buy" ? "Mua" : "Bán"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ink-700">{TYPE_LABEL[order.type]}</td>
                    <td className="px-4 py-3 text-right text-ink-700">
                      {order.price !== null ? formatNumber(parseDecimal(order.price)) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-ink-700">
                      {formatQuantity(parseDecimal(order.quantity))}
                    </td>
                    <td className="px-4 py-3 text-right text-ink-700">
                      {formatQuantity(parseDecimal(order.filled_quantity))}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[order.status]}>
                        {STATUS_LABEL[order.status]}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-ink-500">
                      {formatDateTime(order.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
