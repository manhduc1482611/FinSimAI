/**
 * DailyTaskRow — 1 nhiệm vụ hằng ngày trong QuestPopover.
 * Trạng thái: chưa bắt đầu → đang dở → đã hoàn thành (chờ nhận) → đã nhận.
 */
import { IconCalendar, IconCheck } from "@/components/common/Icon";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import type { TaskProgressResponse } from "@finsim/shared-types/generated/api-types";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

export function DailyTaskRow({
  task,
  action,
  onClaim,
}: {
  task: TaskProgressResponse;
  action: boolean;
  onClaim: () => void;
}) {
  const reward = parseDecimal(task.task.reward_amount);
  const pct = Math.min(100, Math.round((task.progress_count / task.target_count) * 100));

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2",
          task.completed
            ? "border-mkt-up bg-mkt-up/10 text-mkt-up dark:border-mkt-up-400 dark:text-mkt-up-400"
            : "border-ink-200 text-ink-400 dark:border-granite-600 dark:text-granite-400",
        )}
      >
        {task.completed ? <IconCheck className="h-4 w-4" /> : <IconCalendar className="h-4 w-4" />}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-1.5">
          <p className="truncate text-sm font-medium text-ink-900 dark:text-slip">
            {task.task.name}
          </p>
          <span className="board-num text-xs font-bold text-brand-700 dark:text-brand-400">
            +{formatCompactVND(reward)}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                task.completed
                  ? "bg-mkt-up"
                  : pct > 0
                    ? "bg-brand-500"
                    : "bg-ink-300 dark:bg-granite-700",
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="shrink-0 text-[10px] font-medium text-ink-400 dark:text-granite-400">
            {task.progress_count}/{task.target_count}
          </span>
        </div>
      </div>

      {task.claimable ? (
        <Button size="sm" loading={action} onClick={onClaim}>
          Nhận
        </Button>
      ) : task.completed ? (
        <Badge variant="success" className="shrink-0">
          Đã nhận
        </Badge>
      ) : null}
    </li>
  );
}