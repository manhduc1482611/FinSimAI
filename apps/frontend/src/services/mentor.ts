/**
 * Mentor / Knowledge service.
 * Mentor giao tiếp real-time qua WebSocket (`useSocraticMentor`); service này
 * phục vụ lệnh POST `/knowledge/match` để gắn kiến thức vào tin nhắn và
 * GET `/mentor/history` để phục hồi hội thoại sau reload (A3.2).
 */
import type {
  KnowledgeMatchRequest,
  KnowledgeMatchResponse,
} from "@finsim/shared-types/generated/api-types";

import { apiClient } from "@/services/api";

/** POST /knowledge/match → tìm khái niệm liên quan đến text. */
export function matchKnowledge(
  text: string,
): Promise<KnowledgeMatchResponse> {
  const body: KnowledgeMatchRequest = { text };
  return apiClient.post<KnowledgeMatchResponse>("/api/v1/knowledge/match", body);
}

/** Một tin nhắn mentor trả về từ DB server. */
export interface MentorHistoryItem {
  id: string;
  session_id: string;
  role: "user" | "mentor";
  content: string;
  focus: string | null;
  prompt_version: string | null;
  created_at: string;
}

interface MentorHistoryResponse {
  items: MentorHistoryItem[];
  total: number;
}

/** GET /mentor/history → tin nhắn gần nhất (cũ → mới) từ DB. */
export function fetchMentorHistory(
  limit = 50,
): Promise<MentorHistoryResponse> {
  return apiClient.get<MentorHistoryResponse>("/api/v1/mentor/history", { limit });
}
