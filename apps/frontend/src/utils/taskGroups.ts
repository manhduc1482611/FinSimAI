/**
 * Phân nhóm nhiệm vụ theo 2 nhóm hiển thị:
 *   - Nhóm "daily"       → nhiệm vụ hằng ngày (reset mỗi ngày).
 *   - Nhóm "achievement" → thành tựu tích lũy, gộp theo "tier key".
 *
 * Tier key = code nhiệm vụ bỏ hậu tố số (vd: streak_3/7/30 → streak,
 * read_5_knowledge/read_10_knowledge → read_knowledge) để gộp các bậc
 * của cùng một thành tựu thành 1 thẻ.
 */
import type { ComponentType } from "react";

import {
  IconBook,
  IconCalendar,
  IconCheck,
  IconGrid,
  IconStar,
  IconTrophy,
} from "@/components/common/Icon";
import type { TaskProgressResponse, TaskResponse } from "@finsim/shared-types/generated/api-types";

export type RewardGroup = "daily" | "achievement";

export type TaskIcon = ComponentType<{ className?: string }>;

/** Màu chữ theo category (dùng cho icon thành tựu). */
export function categoryAccent(category: TaskResponse["category"]): string {
  switch (category) {
    case "onboarding":
      return "text-brand-700 dark:text-brand-400";
    case "learning":
      return "text-sky-600 dark:text-sky-400";
    case "streak":
      return "text-violet-600 dark:text-violet-400";
    case "contest":
      return "text-rose-600 dark:text-rose-400";
    case "daily":
      return "text-amber-600 dark:text-amber-400";
    default:
      return "text-ink-600 dark:text-granite-300";
  }
}

/** Icon đại diện cho nhiệm vụ theo category — các category dễ phân biệt. */
export function taskIconFor(task: TaskResponse): TaskIcon {
  switch (task.category) {
    case "onboarding":
      return IconTrophy;
    case "learning":
      return IconBook;
    case "streak":
      return IconStar;
    case "contest":
      return IconGrid;
    case "daily":
      return IconCalendar;
    default:
      return IconCheck;
  }
}

/** Tier key của nhiệm vụ — bỏ hậu tố số ở cuối code. */
export function tierKeyOf(task: TaskResponse): string {
  const parts = task.code.split("_").filter(Boolean);
  while (parts.length > 0 && /^\d+$/.test(parts[parts.length - 1])) {
    parts.pop();
  }
  return parts.join("_") || task.code;
}

/** Một bậc trong thẻ thành tựu (các bậc của cùng tier). */
export interface AchievementTier extends TaskProgressResponse {
  step: number;
}

/** Nhóm thành tựu đã gộp bậc — 1 thẻ hiển thị nhiều bậc. */
export interface AchievementGroup {
  key: string;
  name: string;
  description: string;
  icon: TaskIcon;
  accent: TaskResponse["category"];
  tiers: AchievementTier[];
  totalCount: number;
  completedCount: number;
  claimableCount: number;
  allClaimed: boolean;
}

/** Gộp các nhiệm vụ thành tựu (group !== daily) theo tier key, bậc tăng dần. */
export function groupAchievements(tasks: TaskProgressResponse[]): AchievementGroup[] {
  const map = new Map<string, AchievementGroup>();

  for (const task of tasks) {
    const key = tierKeyOf(task.task);
    let group = map.get(key);
    if (!group) {
      group = {
        key,
        name: task.task.name,
        description: task.task.description ?? "",
        icon: taskIconFor(task.task),
        accent: task.task.category,
        tiers: [],
        totalCount: 0,
        completedCount: 0,
        claimableCount: 0,
        allClaimed: false,
      };
      map.set(key, group);
    }
    group.tiers.push({ ...task, step: 0 });
    group.totalCount += 1;
  }

  const groups: AchievementGroup[] = [];
  for (const group of map.values()) {
    group.tiers.sort((a, b) => a.target_count - b.target_count);
    // Gán step: bậc thấp nhất là 1, tăng dần theo target.
    group.tiers.forEach((tier, index) => {
      tier.step = index + 1;
    });
    group.completedCount = group.tiers.filter((t) => t.completed).length;
    group.claimableCount = group.tiers.filter((t) => t.claimable).length;
    group.allClaimed = group.tiers.every((t) => t.claimed);
    // Tên nhóm lấy từ bậc gốc (target nhỏ nhất) cho có nghĩa nhất.
    const base = group.tiers[0];
    if (base) {
      group.name = base.task.name;
      group.description = base.task.description ?? "";
      group.icon = taskIconFor(base.task);
      group.accent = base.task.category;
    }
    groups.push(group);
  }

  // Sắp theo tổng step (quy mô) rồi tới số bậc đã nhận.
  groups.sort(
    (a, b) =>
      b.tiers.reduce((s, t) => s + t.target_count, 0) -
      a.tiers.reduce((s, t) => s + t.target_count, 0),
  );
  return groups;
}

/** Nhiệm vụ hằng ngày (group === daily) giữ nguyên từng mã, không gộp. */
export function dailyTasksOf(tasks: TaskProgressResponse[]): TaskProgressResponse[] {
  return tasks.filter((t) => t.task.group === "daily");
}