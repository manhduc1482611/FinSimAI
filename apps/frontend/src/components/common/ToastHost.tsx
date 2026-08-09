/**
 * ToastHost — hiển thị các toast ở góc phải trên; mount một lần trong root layout.
 */
"use client";

import { IconCheck, IconClose, IconWarning } from "@/components/common/Icon";
import { useToastStore, type ToastType } from "@/store/useToastStore";
import { cn } from "@/utils/cn";

const ICONS: Record<ToastType, React.ComponentType<{ className?: string }>> = {
  success: IconCheck,
  error: IconWarning,
  info: IconCheck,
};

const STYLES: Record<ToastType, { ring: string; icon: string }> = {
  success: { ring: "border-brand-400/60 dark:border-brand-400", icon: "text-brand-600 dark:text-brand-400" },
  error: { ring: "border-mkt-down/40 dark:border-mkt-down-400", icon: "text-mkt-down dark:text-mkt-down-400" },
  info: { ring: "border-ink-300 dark:border-granite-600", icon: "text-ink-500 dark:text-granite-300" },
};

export function ToastHost() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  return (
    <div
      className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(92vw,22rem)] flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = ICONS[toast.type];
        const style = STYLES[toast.type];
        return (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-[#FFFDF8] p-3 shadow-lg dark:bg-granite-900",
              style.ring,
            )}
          >
            <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", style.icon)} aria-hidden="true" />
            <p className="flex-1 text-sm text-ink-800 dark:text-slip">{toast.message}</p>
            <button
              type="button"
              className="btn-ghost p-1 text-ink-400 hover:text-ink-600 dark:hover:text-granite-200"
              onClick={() => dismiss(toast.id)}
              aria-label="Đóng thông báo"
            >
              <IconClose className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
