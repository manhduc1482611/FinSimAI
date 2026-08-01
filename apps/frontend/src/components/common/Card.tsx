/**
 * Card — khung nội dung chuẩn (class `.card` đã khai báo trong globals.css).
 */
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/utils/cn";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div className={cn("card", className)} {...rest}>
      {children}
    </div>
  );
}

export interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}

/** Đầu card: tiêu đề + mô tả + action (bên phải). */
export function CardHeader({
  title,
  description,
  action,
  className,
  ...rest
}: CardHeaderProps) {
  return (
    <div
      className={cn("flex items-start justify-between gap-4 border-b border-ink-200 px-4 py-3 dark:border-ink-700", className)}
      {...rest}
    >
      <div className="min-w-0">
        {title !== undefined && (
          <h3 className="text-sm font-semibold text-ink-900 dark:text-ink-100">{title}</h3>
        )}
        {description !== undefined && (
          <p className="mt-0.5 text-xs text-ink-500 dark:text-ink-400">{description}</p>
        )}
      </div>
      {action !== undefined && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function CardBody({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-4 py-4", className)} {...rest}>
      {children}
    </div>
  );
}
