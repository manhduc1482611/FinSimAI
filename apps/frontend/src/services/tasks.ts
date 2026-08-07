/**
 * Nhiệm vụ & Thưởng service — `/api/v1/tasks`.
 */
import type {
  CheckinResponse,
  TaskClaimResponse,
  TaskEventResponse,
  TaskListResponse,
} from "@finsim/shared-types/generated/api-types";

import { apiClient } from "@/services/api";

/** GET /tasks → danh sách nhiệm vụ + streak + tổng thưởng. */
export function listTasks(): Promise<TaskListResponse> {
  return apiClient.get<TaskListResponse>("/api/v1/tasks");
}

/** POST /tasks/checkin → điểm danh hằng ngày. */
export function checkinToday(): Promise<CheckinResponse> {
  return apiClient.post<CheckinResponse>("/api/v1/tasks/checkin");
}

/** POST /tasks/events → báo sự kiện hành vi (mentor chat, hoàn thành kịch bản...). */
export function reportTaskEvent(event: string): Promise<TaskEventResponse> {
  return apiClient.post<TaskEventResponse>("/api/v1/tasks/events", { event });
}

/** POST /tasks/{taskId}/claim → nhận thưởng cho nhiệm vụ. */
export function claimTask(taskId: string): Promise<TaskClaimResponse> {
  return apiClient.post<TaskClaimResponse>(`/api/v1/tasks/${taskId}/claim`);
}
