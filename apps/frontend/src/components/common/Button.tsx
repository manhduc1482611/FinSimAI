/**
 * Button — primitive nút bấm với variants (primary/secondary/ghost/danger),
 * size, trạng thái loading và full-width.
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/utils/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "border border-transparent bg-brand-500 text-granite-950 hover:bg-brand-400 focus:ring-brand-500/40 dark:bg-brand-400 dark:text-granite-950 dark:hover:bg-brand-300",
  secondary:
    "border border-ink-300 bg-[#FFFDF8] text-ink-700 hover:border-brand-500 hover:text-brand-700 focus:ring-brand-500/30 dark:border-granite-600 dark:bg-granite-900 dark:text-granite-200 dark:hover:border-brand-400 dark:hover:text-brand-300",
  ghost:
    "border border-transparent text-ink-600 hover:bg-ink-100 hover:text-ink-900 dark:text-granite-200 dark:hover:bg-granite-800 dark:hover:text-slip",
  danger: "bg-mkt-down text-white hover:bg-mkt-down-500 focus:ring-mkt-down/40 border border-transparent",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors",
        "focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && <SpinnerIcon />}
      {children}
    </button>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
