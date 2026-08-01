/**
 * useKnowledge — gắn kiến thức tài chính vào một đoạn text (tin tức / câu hỏi).
 * Ưu tiên backend `/knowledge/match`; khi backend không phản hồi sẽ fallback
 * sang bộ glossary local (`knowledge_matcher`) để UI không phụ thuộc mạng.
 */
import { useCallback, useState } from "react";

import type { KnowledgeResponse } from "@finsim/shared-types/generated/api-types";

import { matchKnowledge } from "@/services/mentor";
import type { AsyncStatus } from "@/types/api";
import { matchKnowledgeLocal } from "@/utils/knowledge_matcher";

export interface KnowledgeResult {
  matches: KnowledgeResponse[];
  status: AsyncStatus;
  /** Tìm khái niệm liên quan tới text. Trả kết quả đã áp dụng. */
  match: (text: string) => Promise<KnowledgeResponse[]>;
}

export function useKnowledge(): KnowledgeResult {
  const [matches, setMatches] = useState<KnowledgeResponse[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("idle");

  const match = useCallback(async (text: string): Promise<KnowledgeResponse[]> => {
    const trimmed = text.trim();
    if (!trimmed) {
      setMatches([]);
      setStatus("idle");
      return [];
    }
    setStatus("loading");
    try {
      const response = await matchKnowledge(trimmed);
      setMatches(response.matches);
      setStatus("success");
      return response.matches;
    } catch {
      // Backend offline → fallback local, vẫn trả kết quả có ích.
      const local = matchKnowledgeLocal(trimmed);
      setMatches(local);
      setStatus("success");
      return local;
    }
  }, []);

  return { matches, status, match };
}
