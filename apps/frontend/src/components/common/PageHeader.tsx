/** PageHeader — tiêu đề trang + mô tả + actions (dùng chung cho các page). */
import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: string;
  description?: string;
  badge?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, description, badge, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-black tracking-tight text-ink-900 dark:text-slip sm:text-2xl">{title}</h1>
          {badge !== undefined && <span className="shrink-0">{badge}</span>}
        </div>
        {description !== undefined && (
          <p className="mt-1 text-sm text-ink-500 dark:text-granite-300">{description}</p>
        )}
      </div>
      {actions !== undefined && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}
