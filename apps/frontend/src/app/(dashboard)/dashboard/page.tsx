/**
 * Bảng điều khiển người dùng — tổng quan + lối vào các khu vực chính.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  IconBuilding,
  IconCalendar,
  IconGrid,
  IconMentor,
  IconNews,
  IconSocial,
  IconTrade,
  IconTrophy,
  IconWallet,
} from "@/components/common/Icon";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuthStore } from "@/store/useAuthStore";
import { listTasks } from "@/services/tasks";
import { formatCompactVND, parseDecimal } from "@/utils/format";
import type { TaskListResponse } from "@finsim/shared-types/generated/api-types";

const SECTIONS = [
  {
    href: "/news",
    icon: IconNews,
    title: "Tin tức",
    description: "Cảm xúc thị trường & mức tác động.",
  },
  {
    href: "/companies",
    icon: IconBuilding,
    title: "Doanh nghiệp",
    description: "Phân tích cơ bản từng công ty.",
  },
  {
    href: "/trade",
    icon: IconTrade,
    title: "Giao dịch",
    description: "Đặt lệnh & theo dõi danh mục.",
  },
  {
    href: "/trade/mentor",
    icon: IconMentor,
    title: "AI Mentor",
    description: "Phản biện quyết định theo Socratic.",
  },
  {
    href: "/social",
    icon: IconSocial,
    title: "Cộng đồng",
    description: "Heatmap & bài viết xã hội.",
  },
  {
    href: "/contests",
    icon: IconGrid,
    title: "Cuộc thi",
    description: "Tham gia các đấu trường mô phỏng.",
  },
  {
    href: "/tasks",
    icon: IconTrophy,
    title: "Nhiệm vụ & Thưởng",
    description: "Điểm danh, hoàn thành nhiệm vụ nhận thưởng.",
    highlight: true,
  },
];

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const [tasks, setTasks] = useState<TaskListResponse | null>(null);

  useEffect(() => {
    let active = true;
    void listTasks()
      .then((data) => {
        if (active) {
          setTasks(data);
        }
      })
      .catch(() => {
        // Dashboard vẫn dùng được khi API thưởng lỗi — chỉ ẩn strip.
      });
    return () => {
      active = false;
    };
  }, []);

  const todayCompleted =
    tasks?.tasks.filter((t) => t.task.reset_frequency === "daily" && t.completed).length ?? 0;
  const todayTotal =
    tasks?.tasks.filter((t) => t.task.reset_frequency === "daily").length ?? 0;
  const rewardEarned = tasks ? parseDecimal(tasks.total_reward_earned) : null;

  return (
    <div>
      <PageHeader
        title={user ? `Xin chào, ${user.display_name ?? user.username}!` : "Bảng điều khiển"}
        description="Chọn khu vực để bắt đầu — dữ liệu được mô phỏng trong môi trường an toàn."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <QuickStat
          icon={IconCalendar}
          label="Nhiệm vụ hôm nay"
          value={tasks ? `${todayCompleted}/${todayTotal}` : "—"}
          href="/tasks"
        />
        <QuickStat
          icon={IconTrophy}
          label="Chuỗi điểm danh"
          value={tasks ? `${tasks.streak_current} ngày` : "—"}
          href="/tasks"
        />
        <QuickStat
          icon={IconWallet}
          label="Tổng thưởng đã nhận"
          value={rewardEarned !== null ? formatCompactVND(rewardEarned) : "—"}
          href="/tasks"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <Link
              key={section.href}
              href={section.href}
              className={
                "card group p-6 transition-shadow hover:shadow-md " +
                (section.highlight
                  ? "border-brand-300 bg-brand-50/50 dark:border-brand-700 dark:bg-brand-500/10"
                  : "")
              }
            >
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="text-sm font-semibold text-ink-900 group-hover:text-brand-700 dark:text-ink-100">
                {section.title}
              </h3>
              <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">{section.description}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function QuickStat({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  href: string;
}) {
  return (
    <Link href={href} className="card flex items-center gap-3 p-4 transition-shadow hover:shadow-md">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0">
        <span className="block text-xs text-ink-500 dark:text-ink-400">{label}</span>
        <span className="block truncate text-base font-bold text-ink-900 dark:text-ink-100">
          {value}
        </span>
      </span>
    </Link>
  );
}
