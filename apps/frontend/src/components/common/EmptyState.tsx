/** EmptyState — trạng thái chưa có dữ liệu với thông điệp + hành động tuỳ chọn. */
import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-300 bg-[#FFFDF8] px-6 py-12 text-center dark:border-granite-700 dark:bg-granite-900">
      {icon !== undefined && (
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ink-100 text-ink-400 dark:bg-granite-800 dark:text-granite-300">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-ink-900 dark:text-slip">{title}</h3>
      {description !== undefined && (
        <p className="mt-1 max-w-md text-sm text-ink-500 dark:text-granite-300">{description}</p>
      )}
      {action !== undefined && <div className="mt-4">{action}</div>}
    </div>
  );
}
