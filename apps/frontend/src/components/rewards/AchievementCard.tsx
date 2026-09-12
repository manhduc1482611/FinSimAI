/**
 * AchievementCard — 1 thẻ thành tựu với nhiều bậc (tier). Mỗi bậc là 1 mốc
 * của cùng đích thành tựu (vd: streak 3/7/30 ngày). Nhận thưởng thủ công từng bậc.
 */
import { IconCheck } from "@/components/common/Icon";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import type { AchievementGroup } from "@/utils/taskGroups";
import { categoryAccent } from "@/utils/taskGroups";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

export function AchievementCard({
  group,
  action,
  onClaim,
}: {
  group: AchievementGroup;
  action: string | null;
  onClaim: (taskId: string) => void;
}) {
  const Icon = group.icon;
  const multi = group.tiers.length > 1;

  return (
    <li className="px-4 py-3">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink-100 dark:bg-granite-800">
          <Icon className={cn("h-5 w-5", categoryAccent(group.accent))} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="truncate text-sm font-semibold text-ink-900 dark:text-slip">
              {group.name}
            </p>
            {multi && (
              <Badge variant="neutral" className="text-[10px]">
                {group.completedCount}/{group.totalCount} bậc
              </Badge>
            )}
          </div>
          {group.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-ink-500 dark:text-granite-300">
              {group.description}
            </p>
          )}

          <div className="mt-2 space-y-1.5">
            {group.tiers.map((tier) => {
              const reward = parseDecimal(tier.task.reward_amount);
              const pct = Math.min(100, Math.round((tier.progress_count / tier.target_count) * 100));
              return (
                <div key={tier.task.id} className="flex items-center gap-2">
                  <span className="w-7 shrink-0 text-[10px] font-bold text-ink-400 dark:text-granite-500">
                    Bậc {tier.step}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="truncate text-xs text-ink-700 dark:text-granite-200">
                        {tier.task.name}
                      </p>
                      <span className="board-num shrink-0 text-[11px] font-bold text-brand-700 dark:text-brand-400">
                        +{formatCompactVND(reward)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-granite-800">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            tier.completed
                              ? "bg-mkt-up"
                              : pct > 0
                                ? "bg-brand-500"
                                : "bg-ink-300 dark:bg-granite-700",
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="shrink-0 text-[10px] text-ink-400 dark:text-granite-400">
                        {tier.progress_count}/{tier.target_count}
                      </span>
                    </div>
                  </div>
                  {tier.claimable ? (
                    <Button
                      size="sm"
                      className="shrink-0"
                      loading={action === tier.task.id}
                      onClick={() => onClaim(tier.task.id)}
                    >
                      Nhận
                    </Button>
                  ) : tier.claimed ? (
                    <span className="shrink-0 rounded-full bg-mkt-up/10 p-1 text-mkt-up dark:text-mkt-up-400">
                      <IconCheck className="h-3.5 w-3.5" />
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </li>
  );
}