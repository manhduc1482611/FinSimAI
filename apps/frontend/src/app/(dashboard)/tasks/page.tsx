/**
 * Nhiệm vụ & Thưởng — 2 nhóm: Hằng ngày (reset mỗi ngày) và Thành tựu (tích lũy, đa bậc).
 * Dùng chung store `useTaskStore` với QuestPopover trên Header.
 */
"use client";

import { useEffect } from "react";

import {
  IconCalendar,
  IconCheck,
  IconStar,
  IconTrophy,
  IconWallet,
} from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Card, CardBody } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { LoggedOutPrompt } from "@/components/common/LoggedOutPrompt";
import { Spinner } from "@/components/common/Spinner";
import { useTaskStore } from "@/store/useTaskStore";
import { useAuthStore } from "@/store/useAuthStore";
import { useToastStore } from "@/store/useToastStore";
import { formatCompactVND, formatVND, parseDecimal } from "@/utils/format";
import { categoryAccent, dailyTasksOf, groupAchievements } from "@/utils/taskGroups";
import { toRequestError } from "@/services/api";
import { cn } from "@/utils/cn";
import { DailyTaskRow } from "@/components/rewards/DailyTaskRow";
import { AchievementCard } from "@/components/rewards/AchievementCard";

export default function TasksPage() {
  const user = useAuthStore((state) => state.user);
  const data = useTaskStore((state) => state.data);
  const loading = useTaskStore((state) => state.loading);
  const error = useTaskStore((state) => state.error);
  const actionTaskId = useTaskStore((state) => state.actionTaskId);
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const checkin = useTaskStore((state) => state.checkin);
  const claim = useTaskStore((state) => state.claim);
  const toast = useToastStore((state) => state.push);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  const onCheckin = async () => {
    try {
      const result = await checkin();
      if (result.already_checked_in) {
        toast("info", "Bạn đã điểm danh hôm nay rồi.");
      } else {
        toast("success", `Điểm danh thành công · chuỗi ${result.current_streak} ngày`);
      }
    } catch (err) {
      toast("error", toRequestError(err).detail);
    }
  };

  const onClaimById = async (taskId: string) => {
    const task = data?.tasks.find((t) => t.task.id === taskId);
    try {
      const reward = await claim(taskId);
      toast(
        "success",
        `Nhận thưởng "${task?.task.name ?? "Nhiệm vụ"}" · +${formatCompactVND(parseDecimal(reward))}`,
      );
    } catch (err) {
      toast("error", toRequestError(err).detail);
    }
  };

  if (!user) {
    return (
      <div>
        <PageHeader
          title="Nhiệm vụ & Thưởng"
          description="Hoàn thành nhiệm vụ để nhận thưởng vốn mô phỏng — rèn kỷ luật mỗi ngày."
        />
        <LoggedOutPrompt
          title="Đăng nhập để xem nhiệm vụ"
          description="Điểm danh hằng ngày, hoàn thành nhiệm vụ và nhận thưởng vốn mô phỏng. Bạn cần đăng nhập để theo dõi chuỗi kỷ luật của mình."
        />
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error && !data) {
    return <ErrorPanel error={error} onRetry={() => void fetchTasks()} />;
  }

  if (!data) {
    return null;
  }

  const dailyTasks = dailyTasksOf(data.tasks);
  const achievementGroups = groupAchievements(data.tasks);
  const claimableCount = data.tasks.filter((t) => t.claimable).length;
  const totalReward = parseDecimal(data.total_reward_earned);
  const alreadyCheckedIn = dailyTasks.some((t) => t.task.code === "daily_checkin" && t.completed);

  return (
    <div>
      <PageHeader
        title="Nhiệm vụ & Thưởng"
        description="Nhiệm vụ hằng ngày làm mới vào 00:00 — thành tựu tích lũy lâu dài. Nhận thưởng thủ công khi hoàn thành."
      />

      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <StreakCard
          current={data.streak_current}
          longest={data.streak_longest}
          alreadyCheckedIn={alreadyCheckedIn}
          checking={actionTaskId === "__checkin__"}
          onCheckin={() => void onCheckin()}
        />
        <StatCard
          icon={IconWallet}
          label="Tổng thưởng đã nhận"
          value={formatVND(totalReward)}
          hint="Cộng thẳng vào vốn mô phỏng"
        />
        <StatCard
          icon={IconTrophy}
          label="Sẵn sàng nhận"
          value={String(claimableCount)}
          hint="nhiệm vụ đã hoàn thành, chờ nhận thưởng"
        />
        <StatCard
          icon={IconCalendar}
          label="Nhiệm vụ hôm nay"
          value={`${dailyTasks.filter((t) => t.completed).length}/${dailyTasks.length}`}
          hint="chỉ tính nhóm Hằng ngày"
        />
      </div>

      {/* Nhóm 1: Hằng ngày */}
      <Card className="mb-6 overflow-hidden">
        <div className="flex items-center gap-3 border-b border-line px-4 py-3 dark:border-granite-700">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-ink-100 dark:bg-granite-800">
            <IconCalendar className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold text-ink-900 dark:text-slip">
              Hằng ngày
              <span className="board-num ml-2 text-xs font-medium text-ink-400 dark:text-granite-400">
                {dailyTasks.filter((t) => t.completed).length}/{dailyTasks.length}
              </span>
            </h3>
            <p className="truncate text-xs text-ink-500 dark:text-granite-300">
              Làm mới mỗi ngày lúc 00:00 (giờ Việt Nam).
            </p>
          </div>
        </div>
        <ul className="divide-y divide-ink-100 dark:divide-granite-800">
          {dailyTasks.map((task) => (
            <DailyTaskRow
              key={task.task.id}
              task={task}
              action={actionTaskId === task.task.id}
              onClaim={() => void onClaimById(task.task.id)}
            />
          ))}
          {dailyTasks.length === 0 && (
            <li className="px-4 py-8">
              <EmptyState title="Chưa có nhiệm vụ hằng ngày" description="Hệ thống chưa có nhiệm vụ nào để hiển thị." />
            </li>
          )}
        </ul>
      </Card>

      {/* Nhóm 2: Thành tựu */}
      <h4 className="mb-3 flex items-center gap-2 text-sm font-bold text-ink-900 dark:text-slip">
        <IconTrophy className="h-4 w-4 text-brand-600 dark:text-brand-400" />
        Thành tựu
        <span className="board-num text-xs font-medium text-ink-400 dark:text-granite-400">
          {achievementGroups.reduce((s, g) => s + g.completedCount, 0)}/
          {achievementGroups.reduce((s, g) => s + g.totalCount, 0)} bậc
        </span>
      </h4>

      {achievementGroups.length === 0 ? (
        <Card>
          <CardBody className="py-12">
            <EmptyState title="Chưa có thành tựu" description="Hệ thống chưa có thành tựu nào để hiển thị." />
          </CardBody>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {achievementGroups.map((group) => {
            const Icon = group.icon;
            return (
              <Card key={group.key} className="overflow-hidden">
                <div className="flex items-center gap-3 border-b border-line px-4 py-3 dark:border-granite-700">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink-100 dark:bg-granite-800">
                    <Icon className={cn("h-5 w-5", categoryAccent(group.accent))} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-bold text-ink-900 dark:text-slip">
                      {group.name}
                      {group.tiers.length > 1 && (
                        <span className="board-num ml-2 text-xs font-medium text-ink-400 dark:text-granite-400">
                          {group.completedCount}/{group.totalCount} bậc
                        </span>
                      )}
                    </h3>
                    {group.description && (
                      <p className="truncate text-xs text-ink-500 dark:text-granite-300">
                        {group.description}
                      </p>
                    )}
                  </div>
                  {group.claimableCount > 0 ? (
                    <Badge variant="warning" className="shrink-0">
                      {group.claimableCount} bậc nhận được
                    </Badge>
                  ) : group.completedCount === group.totalCount ? (
                    <Badge variant="success" className="shrink-0">
                      <IconCheck className="mr-1 h-3.5 w-3.5" /> Hoàn thành
                    </Badge>
                  ) : null}
                </div>
                <ul className="divide-y divide-ink-100 dark:divide-granite-800">
                  <AchievementCard
                    group={group}
                    action={actionTaskId}
                    onClaim={(taskId) => void onClaimById(taskId)}
                  />
                </ul>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StreakCard({
  current,
  longest,
  alreadyCheckedIn,
  checking,
  onCheckin,
}: {
  current: number;
  longest: number;
  alreadyCheckedIn: boolean;
  checking: boolean;
  onCheckin: () => void;
}) {
  return (
    <div className="ticket ticket-notch flex flex-col md:col-span-1">
      <div className="flex items-center justify-between px-4 pt-4">
        <p className="board-label">Số vé kỷ luật</p>
        <IconStar className="h-5 w-5 text-amber-500" aria-hidden="true" />
      </div>
      <div className="flex items-baseline gap-1 px-4 pt-2">
        <span className="board-num text-4xl font-black text-brand-600 dark:text-brand-400">
          {current}
        </span>
        <span className="text-sm text-ink-500 dark:text-granite-300">ngày liên tiếp</span>
      </div>
      <p className="px-4 pb-3 text-xs text-ink-500 dark:text-granite-300">
        Kỷ lục: <span className="font-semibold text-ink-700 dark:text-slip">{longest} ngày</span>
      </p>
      <div className="mt-auto px-4 pb-4">
        {alreadyCheckedIn ? (
          <Badge variant="success" className="justify-center py-1.5">
            <IconCheck className="mr-1 h-3.5 w-3.5" /> Đã điểm danh
          </Badge>
        ) : (
          <Button size="md" fullWidth loading={checking} onClick={onCheckin}>
            Điểm danh nhận thưởng
          </Button>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="board flex items-center gap-2.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-500/15 text-brand-400">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <p className="board-label">{label}</p>
        <p className="board-num truncate text-xl font-bold text-slip">{value}</p>
        <p className="truncate text-xs text-ink-400 dark:text-granite-300">{hint}</p>
      </div>
    </div>
  );
}