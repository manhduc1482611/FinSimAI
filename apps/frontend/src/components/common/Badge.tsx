/**
 * Badge — nhãn trạng thái với màu theo variant (thành công/cảnh báo/nguy hiểm…).
 */
import type { ReactNode } from "react";

import { cn } from "@/utils/cn";

export type BadgeVariant = "neutral" | "success" | "warning" | "danger" | "info";

export interface BadgeProps {
  variant?: BadgeVariant;
  className?: string;
  children: ReactNode;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral:
    "bg-ink-100 text-ink-700 ring-ink-200 dark:bg-granite-700 dark:text-granite-200 dark:ring-granite-600",
  success:
    "bg-mkt-up/10 text-mkt-up ring-mkt-up/30 dark:bg-mkt-up-400/10 dark:text-mkt-up-400 dark:ring-mkt-up-400/30",
  warning:
    "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/30",
  danger:
    "bg-mkt-down/10 text-mkt-down ring-mkt-down/30 dark:bg-mkt-down-400/10 dark:text-mkt-down-400 dark:ring-mkt-down-400/30",
  info:
    "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-400/10 dark:text-sky-300 dark:ring-sky-400/30",
};

export function Badge({ variant = "neutral", className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        VARIANT_CLASSES[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
