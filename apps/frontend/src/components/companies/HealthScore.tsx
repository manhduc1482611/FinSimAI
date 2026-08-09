/**
 * HealthScore — điểm sức khỏe doanh nghiệp (0-100) dạng thanh trực quan.
 */
"use client";

import { Card, CardBody, CardHeader } from "@/components/common/Card";
import { IconGauge } from "@/components/common/Icon";
import { cn } from "@/utils/cn";

export interface HealthScoreProps {
  score: number;
}

function scoreTone(score: number): { bar: string; text: string; label: string } {
  if (score >= 80) {
    return {
      bar: "bg-mkt-up",
      text: "text-mkt-up dark:text-mkt-up-400",
      label: "Sức khỏe tốt",
    };
  }
  if (score >= 60) {
    return {
      bar: "bg-brand-500",
      text: "text-brand-700 dark:text-brand-300",
      label: "Sức khỏe ổn",
    };
  }
  return {
    bar: "bg-mkt-down",
    text: "text-mkt-down dark:text-mkt-down-400",
    label: "Cần cẩn trọng",
  };
}

export function HealthScore({ score }: HealthScoreProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = scoreTone(clamped);

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <IconGauge className="h-4 w-4 text-ink-400" />
            Sức khỏe doanh nghiệp
          </span>
        }
      />
      <CardBody>
        <div className="flex items-end justify-between">
          <p className={cn("text-3xl font-bold tabular-nums board-num", tone.text)}>{clamped}</p>
          <p className="text-xs font-medium text-ink-500 dark:text-granite-400">{tone.label}</p>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
          <div
            className={cn("h-full rounded-full transition-all duration-500", tone.bar)}
            style={{ width: `${clamped}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-ink-500 dark:text-granite-400">
          Chấm điểm tổng hợp từ độ biến động giá, tăng trưởng lợi nhuận ròng và hệ số an toàn.
        </p>
      </CardBody>
    </Card>
  );
}
