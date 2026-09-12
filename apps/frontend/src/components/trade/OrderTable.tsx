/**
 * OrderTable — lịch sử lệnh với tab lọc theo trạng thái:
 * Tất cả · Chờ khớp · Đã khớp · Đã hủy · Bị từ chối.
 */
"use client";

import { useState } from "react";

import { Badge, type BadgeVariant } from "@/components/common/Badge";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { Skeleton } from "@/components/common/Skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { formatDateTime, formatNumber, formatQuantity, parseDecimal } from "@/utils/format";
import type { CompanyResponse, OrderResponse } from "@finsim/shared-types/generated/api-types";
import type { AsyncStatus } from "@/types/api";
import { cn } from "@/utils/cn";

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

const FILTER_TABS: Array<{ key: OrderResponse["status"] | "all"; label: string }> = [
  { key: "all", label: "Tất cả" },
  { key: "pending", label: "Chờ khớp" },
  { key: "filled", label: "Đã khớp" },
  { key: "cancelled", label: "Đã hủy" },
  { key: "rejected", label: "Từ chối" },
];

export interface OrderTableProps {
  orders: OrderResponse[];
  companies: CompanyResponse[];
  status: AsyncStatus;
  error: string | null;
  onRetry: () => void;
  onCancel: (orderId: string) => void;
}

export function OrderTable({ orders, companies, status, error, onRetry, onCancel }: OrderTableProps) {
  const [filter, setFilter] = useState<OrderResponse["status"] | "all">("all");

  const symbolOf = (companyId: string): string =>
    companies.find((company) => company.id === companyId)?.symbol ?? companyId;

  const canCancel = (order: OrderResponse): boolean =>
    order.status === "pending" || order.status === "partially_filled";

  const filtered =
    filter === "all" ? orders : orders.filter((order) => order.status === filter);

  return (
    <Card>
      <CardHeader
        title="Lịch sử lệnh"
        description={`${orders.length} lệnh · ${filtered.length} hiển thị`}
        action={
          <button
            type="button"
            className="text-xs font-medium text-brand-700 hover:underline disabled:cursor-wait disabled:opacity-50 dark:text-brand-300"
            onClick={onRetry}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Đang tải..." : "Làm mới"}
          </button>
        }
      />
      <CardBody className="px-0 py-0">
        {/* Tabs lọc trạng thái */}
        <div className="flex flex-wrap gap-1 border-b border-line px-4 pt-3 pb-2 dark:border-granite-700">
          {FILTER_TABS.map((tab) => {
            const active = filter === tab.key;
            const count =
              tab.key === "all"
                ? orders.length
                : orders.filter((o) => o.status === tab.key).length;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setFilter(tab.key)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
                  active
                    ? "bg-brand-500 text-granite-950"
                    : "bg-ink-100 text-ink-600 hover:bg-ink-200 dark:bg-granite-800 dark:text-granite-300 dark:hover:bg-granite-700",
                )}
              >
                {tab.label}
                <span className="board-num ml-1 opacity-70">{count}</span>
              </button>
            );
          })}
        </div>

        {status === "loading" ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
          </div>
        ) : status === "error" ? (
          <p className="p-4 text-sm text-mkt-down dark:text-mkt-down-400">
            {error ?? "Không tải được lịch sử lệnh."}{" "}
            <button type="button" className="font-semibold underline" onClick={onRetry}>
              Thử lại
            </button>
          </p>
        ) : orders.length === 0 ? (
          <div className="p-6">
            <EmptyState title="Chưa có lệnh nào" description="Đặt lệnh đầu tiên của bạn ở panel bên cạnh." />
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Không có lệnh phù hợp"
              description={`Không có lệnh nào ở trạng thái "${FILTER_TABS.find((t) => t.key === filter)?.label}".`}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="board-label border-b border-line dark:border-granite-700">
                  <th className="px-4 py-2 font-semibold">Mã</th>
                  <th className="px-4 py-2 font-semibold">Hướng</th>
                  <th className="px-4 py-2 font-semibold">Loại</th>
                  <th className="px-4 py-2 text-right font-semibold">Giá</th>
                  <th className="px-4 py-2 text-right font-semibold">Khối lượng</th>
                  <th className="px-4 py-2 text-right font-semibold">Đã khớp</th>
                  <th className="px-4 py-2 font-semibold">Trạng thái</th>
                  <th className="px-4 py-2 text-right font-semibold">Thời gian</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((order) => (
                  <tr key={order.id} className="border-b border-line last:border-0 dark:border-granite-700">
                    <td className="px-4 py-3 font-black text-ink-900 dark:text-slip">
                      {symbolOf(order.company_id)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          order.side === "buy" ? "font-semibold text-mkt-up dark:text-mkt-up-400" : "font-semibold text-mkt-down dark:text-mkt-down-400"
                        }
                      >
                        {order.side === "buy" ? "Mua" : "Bán"}
                      </span>
                    </td>
                    <td className="board-num px-4 py-3 text-ink-700 dark:text-granite-300">{TYPE_LABEL[order.type]}</td>
                    <td className="board-num px-4 py-3 text-right text-ink-700 dark:text-granite-300">
                      {order.price !== null ? formatNumber(parseDecimal(order.price)) : "—"}
                    </td>
                    <td className="board-num px-4 py-3 text-right text-ink-700 dark:text-granite-300">
                      {formatQuantity(parseDecimal(order.quantity))}
                    </td>
                    <td className="board-num px-4 py-3 text-right text-ink-700 dark:text-granite-300">
                      {formatQuantity(parseDecimal(order.filled_quantity))}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[order.status]}>
                        {STATUS_LABEL[order.status]}
                      </Badge>
                    </td>
                    <td className="board-num px-4 py-3 text-right text-xs text-ink-500 dark:text-granite-400">
                      {formatDateTime(order.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canCancel(order) && (
                        <button
                          type="button"
                          className="text-xs font-medium text-mkt-down hover:underline disabled:cursor-wait disabled:opacity-50 dark:text-mkt-down-400"
                          onClick={() => onCancel(order.id)}
                        >
                          Hủy
                        </button>
                      )}
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
