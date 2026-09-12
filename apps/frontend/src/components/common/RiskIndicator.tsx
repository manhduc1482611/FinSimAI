/**
 * RiskIndicator — thanh đo rủi ro (0-100) kèm nhãn mức độ.
 * Màu theo phân loại: Thấp (xanh) · Trung bình (vàng) · Cao (cam) · Rất cao (đỏ).
 */
"use client";

import { cn } from "@/utils/cn";

export type RiskLevel = "low" | "medium" | "high" | "very-high";

export function riskLevel(score: number): RiskLevel {
  if (score <= 20) return "low";
  if (score <= 50) return "medium";
  if (score <= 80) return "high";
  return "very-high";
}

export function riskLevelLabel(score: number): string {
  switch (riskLevel(score)) {
    case "low":
      return "Thấp";
    case "medium":
      return "Trung bình";
    case "high":
      return "Cao";
    case "very-high":
      return "Rất cao";
  }
}

const LEVEL_BAR: Record<RiskLevel, string> = {
  low: "bg-mkt-up",
  medium: "bg-amber-400",
  high: "bg-orange-500",
  "very-high": "bg-mkt-down",
};

const LEVEL_TEXT: Record<RiskLevel, string> = {
  low: "text-mkt-up dark:text-mkt-up-400",
  medium: "text-amber-500 dark:text-amber-400",
  high: "text-orange-500 dark:text-orange-400",
  "very-high": "text-mkt-down dark:text-mkt-down-400",
};

export interface RiskIndicatorProps {
  score: number;
  className?: string;
  /** Hiển thị tiêu đề "RỦI RO" phía trên. */
  showLabel?: boolean;
}

export function RiskIndicator({ score, className, showLabel = true }: RiskIndicatorProps) {
  const clamped = Math.min(100, Math.max(0, score));
  const level = riskLevel(clamped);

  return (
    <div className={cn("w-full", className)}>
      {showLabel && (
        <div className="flex items-baseline justify-between">
          <span className="board-label">RỦI RO</span>
          <span className="board-num text-xs font-semibold">
            {clamped}/100
          </span>
        </div>
      )}
      <div className="mt-1 flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
          <div
            className={cn("h-full rounded-full transition-all duration-300", LEVEL_BAR[level])}
            style={{ width: `${clamped}%` }}
          />
        </div>
        <span className={cn("board-label shrink-0 text-xs font-semibold", LEVEL_TEXT[level])}>
          {riskLevelLabel(clamped)}
        </span>
      </div>
    </div>
  );
}
