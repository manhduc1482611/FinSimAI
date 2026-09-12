/**
 * OrderConfirmModal — bước xác nhận trước khi đặt lệnh.
 * Hiển thị tóm tắt: mã, hướng, loại lệnh, giá, khối lượng, chi phí/tổng.
 */
"use client";

import { useEffect } from "react";

import { Button } from "@/components/common/Button";
import { IconClose } from "@/components/common/Icon";
import { formatNumber, formatQuantity } from "@/utils/format";
import { cn } from "@/utils/cn";

export interface OrderConfirmData {
  symbol: string;
  companyName: string;
  side: "buy" | "sell";
  type: "market" | "limit";
  price: number | null;
  quantity: number;
  gross: number;
  fee: number;
  tax: number;
  net: number;
}

interface OrderConfirmModalProps {
  order: OrderConfirmData | null;
  submitting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function OrderConfirmModal({ order, submitting, onConfirm, onCancel }: OrderConfirmModalProps) {
  useEffect(() => {
    if (order === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [order, onCancel]);

  if (order === null) return null;

  const isBuy = order.side === "buy";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-granite-950/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Xác nhận đặt lệnh"
      onClick={onCancel}
    >
      <div
        className="card w-full max-w-md overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3 dark:border-granite-700">
          <h3 className="text-sm font-bold text-ink-900 dark:text-slip">
            Xác nhận lệnh{" "}
            <span className={isBuy ? "text-mkt-up" : "text-mkt-down"}>
              {isBuy ? "MUA" : "BÁN"}
            </span>
          </h3>
          <button
            type="button"
            className="btn-ghost p-1.5"
            onClick={onCancel}
            disabled={submitting}
            aria-label="Đóng"
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-2.5 p-4">
          <SummaryRow label="Mã" value={order.symbol} />
          <p className="text-xs text-ink-500 dark:text-granite-400">{order.companyName}</p>
          <SummaryRow
            label="Loại lệnh"
            value={order.type === "market" ? "Thị trường" : "Giới hạn"}
          />
          <SummaryRow
            label="Giá"
            value={order.price !== null ? `${formatNumber(order.price, 2)} ₫` : "Thị trường"}
          />
          <SummaryRow label="Khối lượng" value={`${formatQuantity(order.quantity)} CP`} />

          <div className="my-1 border-t border-dashed border-line dark:border-granite-600" />

          <SummaryRow label="Giá trị lệnh" value={`${formatNumber(order.gross, 0)} ₫`} />
          <SummaryRow
            label="Phí giao dịch (0.15%)"
            value={`${isBuy ? "+" : "−"}${formatNumber(order.fee, 0)} ₫`}
          />
          {order.tax > 0 && (
            <SummaryRow label="Thuế bán (0.1%)" value={`−${formatNumber(order.tax, 0)} ₫`} />
          )}
          <div className="flex items-center justify-between border-t border-line pt-2 text-sm font-bold text-slip dark:border-granite-700">
            <span className="board-label">{isBuy ? "Tổng chi tiêu" : "Thực nhận"}</span>
            <span className="board-num text-base">{formatNumber(order.net, 0)} ₫</span>
          </div>
        </div>

        <div className="flex gap-2 border-t border-line px-4 py-3 dark:border-granite-700">
          <Button variant="secondary" fullWidth onClick={onCancel} disabled={submitting}>
            Hủy
          </Button>
          <Button
            fullWidth
            loading={submitting}
            variant={isBuy ? "primary" : "danger"}
            onClick={onConfirm}
          >
            Xác nhận {isBuy ? "mua" : "bán"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink-500 dark:text-granite-400">{label}</span>
      <span className={cn("board-num font-semibold text-ink-900 dark:text-slip")}>{value}</span>
    </div>
  );
}
