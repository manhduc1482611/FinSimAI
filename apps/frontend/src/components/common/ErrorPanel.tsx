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
    <div className="flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center dark:border-red-500/30 dark:bg-red-500/10">
      <p className="text-sm font-semibold text-red-700 dark:text-red-400">{toMessage(error)}</p>
      {onRetry !== undefined && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Thử lại
        </Button>
      )}
    </div>
  );
}
