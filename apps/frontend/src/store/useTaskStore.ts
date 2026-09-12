/**
 * Nhiệm vụ & Thưởng store — dùng chung cho Header (QuestPopover), trang /tasks
 * và dashboard. Tự lookup: refetch khi đổi ngày (giờ VN) và memo hoá request.
 */
import { create } from "zustand";

import type {
  CheckinResponse,
  TaskClaimResponse,
  TaskListResponse,
} from "@finsim/shared-types/generated/api-types";

import { checkinToday, claimTask, listTasks } from "@/services/tasks";
import { toRequestError } from "@/services/api";

/** Ngày theo giờ Việt Nam (Asia/Ho_Chi_Minh), dạng YYYY-MM-DD. */
function vnDay(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function countClaimable(data: TaskListResponse | null): number {
  return data?.tasks.filter((t) => t.claimable).length ?? 0;
}

interface TaskState {
  data: TaskListResponse | null;
  loading: boolean;
  error: string | null;
  fetchedDay: string | null;
  actionTaskId: string | null;
  claimableCount: number;
  /** Nạp danh sách (memo: bỏ qua nếu đang load hoặc đã có data cùng ngày). */
  fetchTasks: () => Promise<void>;
  /** Refetch bất kể trạng thái (dùng sau checkin/claim/sự kiện). */
  refresh: () => Promise<void>;
  /** Điểm danh hằng ngày → trả kết quả để UI toast. */
  checkin: () => Promise<CheckinResponse>;
  /** Nhận thưởng task → trả reward_earned. */
  claim: (taskId: string) => Promise<string>;
}

export const useTaskStore = create<TaskState>()((set, get) => ({
  data: null,
  loading: false,
  error: null,
  fetchedDay: null,
  actionTaskId: null,
  claimableCount: 0,

  fetchTasks: async () => {
    const state = get();
    if (state.loading || (state.data !== null && state.fetchedDay === vnDay())) {
      return;
    }
    set({ loading: true, error: null });
    try {
      const data = await listTasks();
      set({ data, loading: false, fetchedDay: vnDay() });
    } catch (err) {
      set({ error: toRequestError(err).detail, loading: false });
    }
  },

  refresh: async () => {
    set({ loading: true, error: null });
    try {
      const data = await listTasks();
      set({ data, loading: false, fetchedDay: vnDay() });
    } catch (err) {
      set({ error: toRequestError(err).detail, loading: false });
    }
  },

  checkin: async () => {
    set({ actionTaskId: "__checkin__" });
    try {
      const result = await checkinToday();
      await get().refresh();
      return result;
    } finally {
      set({ actionTaskId: null });
    }
  },

  claim: async (taskId: string) => {
    set({ actionTaskId: taskId });
    try {
      const result: TaskClaimResponse = await claimTask(taskId);
      await get().refresh();
      return result.reward_earned;
    } finally {
      set({ actionTaskId: null });
    }
  },
}));

// Đồng bộ claimableCount mỗi khi data đổi.
useTaskStore.subscribe((state, prev) => {
  if (state.data !== prev.data) {
    useTaskStore.setState({ claimableCount: countClaimable(state.data) });
  }
});