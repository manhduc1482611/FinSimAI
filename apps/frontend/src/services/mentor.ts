/**
 * Mentor / Knowledge service.
 * Mentor giao tiếp real-time qua WebSocket (`useSocraticMentor`); service này
 * phục vụ lệnh POST `/knowledge/match` để gắn kiến thức vào tin nhắn.
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
