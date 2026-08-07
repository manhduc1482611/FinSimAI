/**
 * Nhiệm vụ & Thưởng — streak, danh sách nhiệm vụ theo nhóm và nhận thưởng.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  IconBook,
  IconCalendar,
  IconCheck,
  IconGrid,
  IconStar,
  IconTrophy,
  IconWallet,
} from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Badge } from "@/components/common/Badge";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorPanel } from "@/components/common/ErrorPanel";
import { Spinner } from "@/components/common/Spinner";
import type {
  TaskProgressResponse,
  TaskListResponse,
} from "@finsim/shared-types/generated/api-types";
import { checkinToday, claimTask, listTasks } from "@/services/tasks";
import { toRequestError } from "@/services/api";
import { useToastStore } from "@/store/useToastStore";
import { formatCompactVND, formatVND, parseDecimal } from "@/utils/format";
import { cn } from "@/utils/cn";

type TaskCategory = "onboarding" | "learning" | "daily" | "streak" | "contest";

interface CategoryMeta {
  label: string;
  blurb: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}

const CATEGORY_META: Record<TaskCategory, CategoryMeta> = {
  onboarding: {
    label: "Hành trình khởi đầu",
    blurb: "Làm quen nền tảng — nhận vốn thưởng ban đầu.",
    icon: IconTrophy,
    accent: "text-brand-600 dark:text-brand-400",
  },
  learning: {
    label: "Học hỏi",
    blurb: "Trau dồi kiến thức thị trường mỗi ngày.",
    icon: IconBook,
    accent: "text-sky-600 dark:text-sky-400",
  },
  daily: {
    label: "Hằng ngày",
    blurb: "Thói quen nhỏ đều đặn, phần thưởng đều tay.",
    icon: IconCalendar,
    accent: "text-amber-600 dark:text-amber-400",
  },
  streak: {
    label: "Kỷ luật",
    blurb: "Duy trì chuỗi điểm danh liên tục không đứt quãng.",
    icon: IconStar,
    accent: "text-violet-600 dark:text-violet-400",
  },
  contest: {
    label: "Cuộc thi",
    blurb: "Gia nhập các đấu trường mô phỏng của cộng đồng.",
    icon: IconGrid,
    accent: "text-rose-600 dark:text-rose-400",
  },
};

const CATEGORY_ORDER: TaskCategory[] = [
  "onboarding",
  "learning",
  "daily",
  "streak",
  "contest",
];

function statusOf(task: TaskProgressResponse) {
  if (task.completed) {
    return "completed";
  }
  if (task.claimable) {
    return "claimable";
  }
  if (task.progress_count > 0) {
    return "in_progress";
  }
  return "not_started";
}

export default function TasksPage() {
  const [data, setData] = useState<TaskListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const toast = useToastStore((state) => state.push);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await listTasks());
    } catch (err) {
      setError(toRequestError(err).detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onCheckin = async () => {
    setChecking(true);
    try {
      const result = await checkinToday();
      if (result.already_checked_in) {
        toast("info", "Bạn đã điểm danh hôm nay rồi.");
      } else {
        toast(
          "success",
          `Điểm danh thành công · chuỗi ${result.current_streak} ngày · +${formatCompactVND(parseDecimal(result.reward_earned))}`,
        );
      }
      await load();
    } catch (err) {
      toast("error", toRequestError(err).detail);
    } finally {
      setChecking(false);
    }
  };

  const onClaim = async (task: TaskProgressResponse) => {
    setClaimingId(task.task.id);
    try {
      const result = await claimTask(task.task.id);
      toast(
        "success",
        `Nhận thưởng "${result.task.name}" · +${formatCompactVND(parseDecimal(result.reward_earned))}`,
      );
      await load();
    } catch (err) {
      toast("error", toRequestError(err).detail);
    } finally {
      setClaimingId(null);
    }
  };

  if (loading && !data) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error && !data) {
    return <ErrorPanel error={error} onRetry={() => void load()} />;
  }

  if (!data) {
    return null;
  }

  const totalReward = parseDecimal(data.total_reward_earned);
  const todayTasks = data.tasks.filter((t) => t.task.reset_frequency === "daily");

  return (
    <div>
      <PageHeader
        title="Nhiệm vụ & Thưởng"
        description="Hoàn thành nhiệm vụ để nhận thưởng vốn mô phỏng — rèn kỷ luật mỗi ngày."
      />

      <div className="mb-6 grid gap-4 md:grid-cols-4">
        <StreakCard
          current={data.streak_current}
          longest={data.streak_longest}
          alreadyCheckedIn={todayTasks.some(
            (t) => t.task.code === "daily_checkin" && t.completed,
          )}
          checking={checking}
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
          label="Đã hoàn thành"
          value={`${data.tasks.filter((t) => t.completed).length}/${data.tasks.length}`}
          hint="trong tổng số nhiệm vụ"
        />
        <StatCard
          icon={IconCalendar}
          label="Nhiệm vụ hôm nay"
          value={`${todayTasks.filter((t) => t.completed).length}/${todayTasks.length}`}
          hint="làm mới theo ngày"
        />
      </div>

      {CATEGORY_ORDER.map((category) => {
        const meta = CATEGORY_META[category];
        const tasks = data.tasks.filter((t) => t.task.category === category);
        if (tasks.length === 0) {
          return null;
        }
        const done = tasks.filter((t) => t.completed).length;
        const Icon = meta.icon;
        return (
          <Card key={category} className="mb-5 overflow-hidden">
            <div className="flex items-center gap-3 border-b border-ink-200 px-4 py-3 dark:border-ink-700">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-ink-50 dark:bg-ink-800">
                <Icon className={cn("h-5 w-5", meta.accent)} />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-ink-900 dark:text-ink-100">
                  {meta.label}
                  <span className="ml-2 text-xs font-normal text-ink-400 dark:text-ink-500">
                    {done}/{tasks.length}
                  </span>
                </h3>
                <p className="truncate text-xs text-ink-500 dark:text-ink-400">{meta.blurb}</p>
              </div>
              {done === tasks.length ? (
                <Badge variant="success">Hoàn thành</Badge>
              ) : null}
            </div>

            <ul className="divide-y divide-ink-100 dark:divide-ink-800">
              {tasks.map((task) => (
                <TaskRow
                  key={task.task.id}
                  task={task}
                  claiming={claimingId === task.task.id}
                  onClaim={() => void onClaim(task)}
                />
              ))}
            </ul>
          </Card>
        );
      })}

      {data.tasks.length === 0 && (
        <EmptyState title="Chưa có nhiệm vụ" description="Hệ thống chưa có nhiệm vụ nào để hiển thị." />
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
    <Card className="md:col-span-1 flex flex-col">
      <div className="flex items-center justify-between px-4 pt-4">
        <p className="text-sm font-semibold text-ink-900 dark:text-ink-100">Điểm danh hằng ngày</p>
        <IconStar className="h-5 w-5 text-amber-500" aria-hidden="true" />
      </div>
      <div className="flex items-baseline gap-1 px-4 pt-2">
        <span className="text-3xl font-black text-brand-600 dark:text-brand-400">{current}</span>
        <span className="text-sm text-ink-500 dark:text-ink-400">ngày liên tiếp</span>
      </div>
      <p className="px-4 pb-3 text-xs text-ink-500 dark:text-ink-400">
        Kỷ lục: <span className="font-semibold text-ink-700 dark:text-ink-200">{longest} ngày</span>
      </p>
      <div className="mt-auto px-4 pb-4">
        <Button
          size="md"
          fullWidth
          loading={checking}
          disabled={alreadyCheckedIn}
          onClick={onCheckin}
          className={alreadyCheckedIn ? "opacity-90" : undefined}
        >
          {alreadyCheckedIn ? (
            <>
              <IconCheck className="h-4 w-4" /> Đã điểm danh
            </>
          ) : (
            <>Điểm danh nhận thưởng</>
          )}
        </Button>
      </div>
    </Card>
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
    <Card>
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
          <Icon className="h-5 w-5" />
        </span>
        <p className="text-sm font-medium text-ink-600 dark:text-ink-300">{label}</p>
      </div>
      <p className="mt-2 text-2xl font-bold text-ink-900 dark:text-ink-100">{value}</p>
      <p className="text-xs text-ink-400 dark:text-ink-500">{hint}</p>
    </Card>
  );
}

function TaskRow({
  task,
  claiming,
  onClaim,
}: {
  task: TaskProgressResponse;
  claiming: boolean;
  onClaim: () => void;
}) {
  const status = statusOf(task);
  const pct = Math.min(100, Math.round((task.progress_count / task.target_count) * 100));
  const reward = parseDecimal(task.task.reward_amount);

  return (
    <li className="px-4 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium text-ink-900 dark:text-ink-100">{task.task.name}</p>
            {status === "completed" && <Badge variant="success">Hoàn thành</Badge>}
            {status === "claimable" && <Badge variant="warning">Sẵn sàng nhận</Badge>}
          </div>
          {task.task.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-ink-500 dark:text-ink-400">
              {task.task.description}
            </p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <p className="text-sm font-semibold text-brand-600 dark:text-brand-400">
            +{formatCompactVND(reward)}
          </p>
          <p className="text-xs text-ink-400 dark:text-ink-500">
            {task.progress_count}/{task.target_count}
          </p>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              status === "completed"
                ? "bg-brand-500"
                : status === "in_progress"
                  ? "bg-brand-400"
                  : "bg-ink-200 dark:bg-ink-700",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
        {status === "claimable" && (
          <Button size="sm" loading={claiming} onClick={onClaim}>
            Nhận thưởng
          </Button>
        )}
        {status === "in_progress" && (
          <span className="text-xs font-medium text-ink-400 dark:text-ink-500">{pct}%</span>
        )}
      </div>
    </li>
  );
}
