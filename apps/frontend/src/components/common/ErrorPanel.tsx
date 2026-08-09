/** ErrorPanel — hiển thị lỗi API kèm nút thử lại. */
import type { RequestError } from "@/types/api";

import { Button } from "@/components/common/Button";

export interface ErrorPanelProps {
  error: string | RequestError | null;
  onRetry?: () => void;
}

function toMessage(error: string | RequestError | null): string {
  if (error === null) {
    return "Đã xảy ra lỗi không xác định";
  }
  if (typeof error === "string") {
    return error;
  }
  return error.detail || `Lỗi HTTP ${error.status}`;
}

export function ErrorPanel({ error, onRetry }: ErrorPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-mkt-down/40 bg-mkt-down/10 px-6 py-8 text-center">
      <p className="text-sm font-semibold text-mkt-down dark:text-mkt-down-400">{toMessage(error)}</p>
      {onRetry !== undefined && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Thử lại
        </Button>
      )}
    </div>
  );
}
