/**
 * TradePanel — form đặt lệnh: chọn công ty, side, loại lệnh, giá & khối lượng.
 */
"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { SelectField, TextField } from "@/components/common/Field";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { useAuthStore } from "@/store/useAuthStore";
import { useTradeStore } from "@/store/useTradeStore";
import type { CompanyResponse } from "@finsim/shared-types/generated/api-types";
import { formatNumber, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

type Side = "buy" | "sell";
type OrderType = "market" | "limit";

export interface TradePanelProps {
  companies: CompanyResponse[];
  companiesLoading: boolean;
  companiesError: string | null;
  /** Điều khiển công ty đang chọn từ bên ngoài (terminal). Khi không truyền, panel tự quản lý. */
  companyId?: string;
  onCompanyIdChange?: (companyId: string) => void;
}

export function TradePanel({
  companies,
  companiesLoading,
  companiesError,
  companyId,
  onCompanyIdChange,
}: TradePanelProps) {
  const submitOrder = useTradeStore((state) => state.submitOrder);
  const orderStatus = useTradeStore((state) => state.orderStatus);
  const orderError = useTradeStore((state) => state.error);
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);

  const [internalCompanyId, setInternalCompanyId] = useState("");
  const [side, setSide] = useState<Side>("buy");
  const [type, setType] = useState<OrderType>("limit");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const activeCompanyId = companyId !== undefined ? companyId : internalCompanyId;

  useEffect(() => {
    if (internalCompanyId === "" && companies.length > 0) {
      setInternalCompanyId(companies[0].id);
    }
  }, [companies, internalCompanyId]);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === activeCompanyId) ?? null,
    [companies, activeCompanyId],
  );

  // Khi đổi công ty → gợi ý giá mặc định = giá hiện tại (chỉ khi đang limit).
  useEffect(() => {
    if (selectedCompany && type === "limit") {
      setPrice(String(selectedCompany.current_price));
    }
  }, [selectedCompany, type]);

  const handleCompanyChange = (next: string) => {
    if (onCompanyIdChange !== undefined) {
      onCompanyIdChange(next);
    } else {
      setInternalCompanyId(next);
    }
  };

  const quantityNum = Number(quantity);
  const priceNum = Number(price.replace(/,/g, "."));
  const hasValidQuantity = Number.isFinite(quantityNum) && quantityNum > 0;
  const hasValidPrice = type === "market" || (Number.isFinite(priceNum) && priceNum > 0);
  const estimatedCost = hasValidQuantity && (type === "market" || hasValidPrice)
    ? quantityNum * (type === "market" ? parseDecimal(selectedCompany?.current_price) : priceNum)
    : null;
  const availableCash = parseDecimal(user?.cash_balance);

  const handleSubmit = async () => {
    setFieldError(null);
    setResult(null);
    if (!selectedCompany) {
      setFieldError("Vui lòng chọn công ty.");
      return;
    }
    if (!hasValidQuantity) {
      setFieldError("Khối lượng phải là số lớn hơn 0.");
      return;
    }
    if (type === "limit" && !hasValidPrice) {
      setFieldError("Giá giới hạn phải lớn hơn 0.");
      return;
    }
    if (side === "buy" && estimatedCost !== null && estimatedCost > availableCash) {
      setFieldError(`Vốn khả dụng không đủ (cần ${formatNumber(estimatedCost)} ₫).`);
      return;
    }
    try {
      const order = await submitOrder({
        company_id: selectedCompany.id,
        side,
        type,
        price: type === "limit" ? String(priceNum) : null,
        quantity: String(quantityNum),
      });
      setResult(
        `Đã đặt lệnh ${side === "buy" ? "MUA" : "BÁN"} ${formatNumber(quantityNum)} ${selectedCompany.symbol} — trạng thái: ${order.status}`,
      );
    } catch (error) {
      setFieldError(error instanceof Error ? error.message : "Không đặt được lệnh.");
    }
  };

  return (
    <Card>
      <CardHeader
        title="Đặt lệnh"
        description={token ? undefined : "Đăng nhập để đặt lệnh thực"}
      />
      <CardBody className="space-y-4">
        {!token && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Bạn chưa đăng nhập — đây là giao diện minh họa, chưa thể đặt lệnh thật.
          </div>
        )}

        {companiesError !== null ? (
          <ErrorPanel error={companiesError} />
        ) : (
          <SelectField
            label="Công ty"
            value={activeCompanyId}
            onChange={(event) => handleCompanyChange(event.target.value)}
            disabled={companiesLoading}
          >
            <option value="" disabled>
              {companiesLoading ? "Đang tải..." : "Chọn công ty"}
            </option>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.symbol} — {company.name}
              </option>
            ))}
          </SelectField>
        )}

        <div className="flex gap-1 rounded-lg border border-ink-200 bg-ink-100 p-1 dark:border-granite-700 dark:bg-granite-950">
          <button
            type="button"
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm font-bold transition-colors",
              side === "buy"
                ? "bg-mkt-up text-white"
                : "text-ink-600 hover:bg-white dark:text-granite-300 dark:hover:bg-granite-800",
            )}
            onClick={() => setSide("buy")}
          >
            Mua
          </button>
          <button
            type="button"
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm font-bold transition-colors",
              side === "sell"
                ? "bg-mkt-down text-white"
                : "text-ink-600 hover:bg-white dark:text-granite-300 dark:hover:bg-granite-800",
            )}
            onClick={() => setSide("sell")}
          >
            Bán
          </button>
        </div>

        <div className="flex gap-1 rounded-lg border border-ink-200 bg-ink-100 p-1 dark:border-granite-700 dark:bg-granite-950">
          <button
            type="button"
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-bold transition-colors",
              type === "market" ? "bg-brand-500 text-granite-950" : "text-ink-600 dark:text-granite-300",
            )}
            onClick={() => setType("market")}
          >
            Thị trường
          </button>
          <button
            type="button"
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-xs font-bold transition-colors",
              type === "limit" ? "bg-brand-500 text-granite-950" : "text-ink-600 dark:text-granite-300",
            )}
            onClick={() => setType("limit")}
          >
            Giới hạn
          </button>
        </div>

        {selectedCompany !== null && (
          <div className="board flex items-center justify-between">
            <span className="board-label">Giá hiện tại</span>
            <span className="board-num text-sm font-bold text-slip">
              {formatNumber(parseDecimal(selectedCompany.current_price))} ₫
            </span>
          </div>
        )}

        {type === "limit" && (
          <TextField
            label="Giá giới hạn (₫)"
            type="number"
            min="0"
            step="0.01"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            placeholder="0.00"
          />
        )}

        <TextField
          label="Khối lượng (cổ phiếu)"
          type="number"
          min="0"
          step="1"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value)}
          placeholder="0"
        />

        {estimatedCost !== null && (
          <div className="board flex items-center justify-between">
            <span className="board-label">
              {side === "buy" ? "Ước tính chi phí" : "Ước tính thu về"}
            </span>
            <span className="board-num text-sm font-bold text-slip">{formatNumber(estimatedCost)} ₫</span>
          </div>
        )}

        {side === "buy" && token !== null && (
          <div className="flex items-center justify-between text-xs text-ink-400 dark:text-granite-400">
            <span>Vốn khả dụng</span>
            <span className="board-num">{formatNumber(availableCash)} ₫</span>
          </div>
        )}

        {fieldError !== null && (
          <div className="rounded-lg border border-mkt-down/40 bg-mkt-down/10 px-3 py-2 text-xs text-mkt-down dark:text-mkt-down-400">
            {fieldError}
          </div>
        )}
        {orderError !== null && fieldError === null && (
          <div className="rounded-lg border border-mkt-down/40 bg-mkt-down/10 px-3 py-2 text-xs text-mkt-down dark:text-mkt-down-400">
            {orderError}
          </div>
        )}
        {result !== null && (
          <div className="rounded-lg border border-brand-500/50 bg-brand-500/10 px-3 py-2 text-xs font-medium text-brand-700 dark:text-brand-300">
            {result}
          </div>
        )}

        <Button
          fullWidth
          loading={orderStatus === "loading"}
          disabled={orderStatus === "loading" || !token}
          variant={side === "buy" ? "primary" : "danger"}
          onClick={() => void handleSubmit()}
        >
          {side === "buy" ? "Đặt lệnh mua" : "Đặt lệnh bán"}
        </Button>

        {selectedCompany !== null && (
          <div className="flex justify-center">
            <Badge variant="neutral">{selectedCompany.symbol}</Badge>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
