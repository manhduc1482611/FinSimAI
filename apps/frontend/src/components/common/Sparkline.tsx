/**
 * Sparkline — biểu đồ đường mini (SVG inline) cho hiệu suất danh mục / giá.
 * Nhẹ hơn lightweight-charts, phù hợp ô tổng quan trên Dashboard.
 */
import { useId } from "react";

export interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  strokeClass?: string;
  fillClass?: string;
  strokeWidth?: number;
}

export function Sparkline({
  values,
  width = 160,
  height = 44,
  strokeClass = "stroke-brand-500",
  fillClass = "fill-brand-500/10",
  strokeWidth = 2,
}: SparklineProps) {
  const gradientId = useId();
  if (values.length < 2) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-ink-400">
        Chưa có dữ liệu
      </div>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);
  const points = values.map((value, index) => {
    const x = index * stepX;
    const y = height - ((value - min) / range) * (height - 8) - 4;
    return `${x},${y}`;
  });
  const line = points.join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      preserveAspectRatio="none"
      role="img"
      aria-hidden="true"
      className="block"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.25" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} className={fillClass} fill={`url(#${gradientId})`} />
      <polyline
        points={line}
        fill="none"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`${strokeClass} fill-none`}
      />
    </svg>
  );
}
