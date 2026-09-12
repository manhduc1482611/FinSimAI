/**
 * QuestPopover — nút nhiệm vụ ở góc trên bên phải (gần tài khoản).
 * - Trigger: icon cúp + badge đỏ nhỏ hiện số nhiệm vụ SẴN SÀNG NHẬN ở góc nút.
 * - Popover: 2 tab "Hằng ngày" (reset mỗi ngày) và "Thành tựu" (tích lũy, đa bậc).
 */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { IconCheck, IconClose, IconCalendar, IconStar, IconTrophy, IconWallet } from "@/components/common/Icon";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";
import { Spinner } from "@/components/common/Spinner";
import { useTaskStore } from "@/store/useTaskStore";
import { useAuthStore } from "@/store/useAuthStore";
import { useToastStore } from "@/store/useToastStore";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import { toRequestError } from "@/services/api";
import { dailyTasksOf, groupAchievements } from "@/utils/taskGroups";
import { cn } from "@/utils/cn";
import { DailyTaskRow } from "@/components/rewards/DailyTaskRow";
import { AchievementCard } from "@/components/rewards/AchievementCard";

type Tab = "daily" | "achievement";

export function QuestPopover() {
  const user = useAuthStore((state) => state.user);
  const data = useTaskStore((state) => state.data);
  const loading = useTaskStore((state) => state.loading);
  const actionTaskId = useTaskStore((state) => state.actionTaskId);
  const claimableCount = useTaskStore((state) => state.claimableCount);
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const refresh = useTaskStore((state) => state.refresh);
  const checkin = useTaskStore((state) => state.checkin);
  const claim = useTaskStore((state) => state.claim);
  const toast = useToastStore((state) => state.push);

  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("daily");
  const rootRef = useRef<HTMLDivElement>(null);

  // Preload một lần khi mount để badge claimableCount sáng sớm (kể cả khi chưa mở).
  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  // Mỗi lần mở → refetch để dữ liệu luôn mới (nhiệm vụ có thể hoàn thành khi đi đè).
  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  // Đóng khi bấm ra ngoài / Escape.
  useEffect(() => {
    if (!open) {
      return;
    }
    const onMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

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

  const alreadyCheckedIn = data?.tasks.some(
    (t) => t.task.code === "daily_checkin" && t.completed,
  );

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Nhiệm vụ & Thưởng"
        title="Nhiệm vụ & Thưởng"
        className={cn(
          "btn-ghost relative p-2",
          open && "bg-ink-100 text-brand-700 dark:bg-granite-800 dark:text-brand-400",
        )}
      >
        <IconTrophy className="h-5 w-5" />
        {claimableCount > 0 && (
          <span className="animate-pop-in absolute -top-0.5 -right-0.5 flex h-4 min-w-[1.1rem] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] leading-none font-bold text-white shadow-sm">
            {claimableCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute top-full right-0 z-40 mt-2 flex w-[22rem] max-w-[90vw] flex-col overflow-hidden rounded-xl border border-line bg-paper shadow-xl dark:border-granite-700 dark:bg-granite-900">
          <div className="border-b border-line px-4 py-3 dark:border-granite-700">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-bold text-ink-900 dark:text-slip">Nhiệm vụ & Thưởng</p>
              {data && (
                <Badge variant="success">
                  <IconWallet className="mr-1 h-3.5 w-3.5" />
                  {formatCompactVND(parseDecimal(data.total_reward_earned))}
                </Badge>
              )}
            </div>

            <div className="mt-2 flex items-center gap-2">
              <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg bg-ink-100 px-2.5 py-1.5 dark:bg-granite-800">
                <IconStar className="h-4 w-4 shrink-0 text-amber-500" />
                <span className="board-num truncate text-xs text-ink-600 dark:text-granite-300">
                  Chuỗi {data ? data.streak_current : "—"} ngày
                  {data && data.streak_longest > 0 && (
                    <span className="text-ink-400 dark:text-granite-500"> · kỷ lục {data.streak_longest}</span>
                  )}
                </span>
              </div>
              <Button
                size="sm"
                variant="secondary"
                loading={actionTaskId === "__checkin__"}
                disabled={alreadyCheckedIn}
                onClick={() => void onCheckin()}
              >
                {alreadyCheckedIn ? <IconCheck className="h-4 w-4" /> : <IconCalendar className="h-4 w-4" />}
                {alreadyCheckedIn ? "Đã điểm danh" : "Điểm danh"}
              </Button>
            </div>
          </div>

          {!user ? (
            <div className="p-4 text-center">
              <p className="text-sm font-bold text-ink-900 dark:text-slip">Đăng nhập để theo dõi nhiệm vụ</p>
              <p className="mt-1 text-xs text-ink-500 dark:text-granite-300">
                Điểm danh hằng ngày và nhận thưởng vốn mô phỏng.
              </p>
              <Link href="/login" className="btn-primary mt-3 inline-flex">
                Đăng nhập
              </Link>
            </div>
          ) : loading && !data ? (
            <div className="flex justify-center py-12">
              <Spinner size="md" />
            </div>
          ) : !data ? (
            <div className="p-4" />
          ) : (
            <>
              <div className="flex border-b border-line px-2 dark:border-granite-700">
                <TabButton tab={tab} current="daily" onClick={() => setTab("daily")}>
                  Hằng ngày
                </TabButton>
                <TabButton tab={tab} current="achievement" onClick={() => setTab("achievement")}>
                  Thành tựu
                </TabButton>
                <button
                  type="button"
                  className="ml-auto p-2 text-ink-400 hover:text-ink-700 dark:text-granite-400 dark:hover:text-slip"
                  onClick={() => setOpen(false)}
                  aria-label="Đóng"
                >
                  <IconClose className="h-4 w-4" />
                </button>
              </div>

              <div className="max-h-[22rem] overflow-y-auto">
                {tab === "daily" ? (
                  <ul className="divide-y divide-ink-100 dark:divide-granite-800">
                    {dailyTasksOf(data.tasks).map((task) => (
                      <DailyTaskRow
                        key={task.task.id}
                        task={task}
                        action={actionTaskId === task.task.id}
                        onClaim={() => void onClaimById(task.task.id)}
                      />
                    ))}
                    {dailyTasksOf(data.tasks).length === 0 && (
                      <li className="px-4 py-6 text-center text-xs text-ink-400 dark:text-granite-400">
                        Chưa có nhiệm vụ hằng ngày nào.
                      </li>
                    )}
                  </ul>
                ) : (
                  <ul className="divide-y divide-ink-100 dark:divide-granite-800">
                    {groupAchievements(data.tasks).map((group) => (
                      <AchievementCard
                        key={group.key}
                        group={group}
                        action={actionTaskId}
                        onClaim={(taskId) => void onClaimById(taskId)}
                      />
                    ))}
                    {groupAchievements(data.tasks).length === 0 && (
                      <li className="px-4 py-6 text-center text-xs text-ink-400 dark:text-granite-400">
                        Chưa có thành tựu nào.
                      </li>
                    )}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function TabButton({
  tab,
  current,
  onClick,
  children,
}: {
  tab: Tab;
  current: Tab;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const active = tab === current;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "border-b-2 px-3 py-2 text-xs font-semibold transition-colors",
        active
          ? "border-brand-500 text-brand-700 dark:border-brand-400 dark:text-brand-400"
          : "border-transparent text-ink-400 hover:text-ink-600 dark:text-granite-400 dark:hover:text-granite-200",
      )}
    >
      {children}
    </button>
  );
}