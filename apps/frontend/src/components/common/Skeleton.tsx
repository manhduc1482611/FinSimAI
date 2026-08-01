/** Skeleton — khối giữ chỗ phát sáng khi dữ liệu đang tải. */
import type { HTMLAttributes } from "react";

import { cn } from "@/utils/cn";

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Ví dụ: "h-4 w-24" — mặc định full-width cao 1rem. */
  className?: string;
}

export function Skeleton({ className, ...rest }: SkeletonProps) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-ink-200/70 dark:bg-ink-700/70", className ?? "h-4 w-full")}
      aria-hidden="true"
      {...rest}
    />
  );
}

/** Một card giữ chỗ trong danh sách đang tải. */
export function CardSkeleton() {
  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-3/4" />
      <div className="flex items-center justify-between pt-1">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

/** Lưới card giữ chỗ dùng khi load danh sách. */
export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }, (_, index) => (
        <CardSkeleton key={index} />
      ))}
    </div>
  );
}
