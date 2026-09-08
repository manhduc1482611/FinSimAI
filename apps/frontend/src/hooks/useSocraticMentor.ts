/**
 * useSocraticMentor — kết nối WS tới `/ws/mentor` (qua ticket single-use) và
 * điều phối luồng chat: câu hỏi → stream chunk → kết thúc (3 chế độ v2.0).
 *
 * Trạng thái tin nhắn nằm trong `useMentorStore`; hook chỉ quản lý socket và
 * truyền `trade_context` (mode + selected_symbol) — không gửi bất kỳ số liệu
 * tài chính nào từ client (backend tự lấy từ DB qua user_id).
 */
import { useEffect, useState } from "react";

import { getWsBaseUrl, isDemoMode } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { reportTaskEvent } from "@/services/tasks";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { MentorMode, TradeContext } from "@/types/websocket";
import {
  lookupConceptLocal,
  matchKnowledgeLocal,
} from "@/utils/knowledge_matcher";
import type { MentorMessage } from "@/store/useMentorStore";

export interface SocraticMentor {
  messages: ReturnType<typeof useMentorStore.getState>["messages"];
  isStreaming: boolean;
  isReady: boolean;
  isConnected: boolean;
  lastError: string | null;
  sendAsk: (text: string, tradeContext?: Partial<TradeContext>) => void;
  sendCancel: () => void;
  reset: () => void;
}

export function useSocraticMentor(): SocraticMentor {
  const user = useAuthStore((state) => state.user);
  const messages = useMentorStore((state) => state.messages);
  const isStreaming = useMentorStore((state) => state.isStreaming);
  const isReady = useMentorStore((state) => state.isReady);
  const lastError = useMentorStore((state) => state.lastError);

  const [ticketUrl, setTicketUrl] = useState<string | null>(null);

  useEffect(() => {
    if (isDemoMode() || !user) {
      setTicketUrl(null);
      useMentorStore.getState().setReady(isDemoMode());
      return;
    }
    let cancelled = false;
    fetchWsTicket()
      .then((ticket) => {
        if (cancelled) {
          return;
        }
        setTicketUrl(`${getWsBaseUrl()}/ws/mentor?ticket=${encodeURIComponent(ticket.ticket)}`);
      })
      .catch(() => {
        if (!cancelled) {
          useMentorStore
            .getState()
            .setError("Không lấy được ticket WebSocket — kiểm tra phiên đăng nhập.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const { status: wsStatus, sendMessage } = useWebSocket({
    url: ticketUrl,
    enabled: ticketUrl !== null,
    onMessage: (message) => {
      useMentorStore.getState().onServerMessage(message);
    },
    onClose: () => {
      useMentorStore.getState().setReady(false);
    },
  });

  const sendAsk = (text: string, tradeContext?: Partial<TradeContext>): void => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    const store = useMentorStore.getState();

    // Mode mặc định từ store; nếu gọi với tradeContext khác thì dùng cái đó.
    const mode = tradeContext?.mode ?? store.tradeContext.mode;
    const selectedSymbol =
      tradeContext?.selected_symbol ??
      store.tradeContext.selected_symbol;

    // Demo mode: không có WebSocket → trả lời bằng glossary local.
    if (isDemoMode()) {
store.setTradeContext({ mode, selected_symbol: selectedSymbol });
      store.pushUserMessage(trimmed);
      void reportTaskEvent("mentor_chat").catch(() => {
        // bỏ qua lỗi tracking
      });
      // Simulate nhỏ để có cảm giác stream.
      setTimeout(() => {
        const reply = buildDemoMentorReply(trimmed, mode, selectedSymbol);
        useMentorStore.setState({ isStreaming: false });
        useMentorStore.getState().pushMentorMessage(reply);
      }, 600);
      return;
    }

    if (wsStatus !== "open") {
      store.setError("Chưa kết nối được tới Mentor — vui lòng thử lại sau giây lát.");
      return;
    }
    store.setTradeContext({ mode, selected_symbol: selectedSymbol });
    store.pushUserMessage(trimmed);
    void reportTaskEvent("mentor_chat").catch(() => {
      // Báo sự kiện thưởng lỗi không ảnh hưởng luồng chat.
    });
    const sessionId = useMentorStore.getState().sessionId;
    if (sessionId) {
      sendMessage({
        action: "ask",
        message: trimmed,
        session_id: sessionId,
        trade_context: { mode, selected_symbol: selectedSymbol },
      });
    }
  };

  const sendCancel = (): void => {
    const store = useMentorStore.getState();
    const sessionId = store.sessionId;
    if (sessionId && wsStatus === "open") {
      sendMessage({ action: "cancel", session_id: sessionId });
    }
    store.setReady(false);
  };

  const reset = (): void => {
    useMentorStore.getState().resetSession();
  };

  return {
    messages,
    isStreaming,
    isReady: isDemoMode() ? true : isReady,
    isConnected: isDemoMode() ? true : wsStatus === "open",
    lastError,
    sendAsk,
    sendCancel,
    reset,
  };
}

/** Dựng phản hồi demo cho Mentor theo mode (một phần dùng glossary local). */
function buildDemoMentorReply(
  text: string,
  mode: MentorMode,
  selectedSymbol: string | undefined,
): Omit<MentorMessage, "id" | "ts"> {
  const intro = "Mentor (Demo):";

  if (mode === "concept") {
    const match = lookupConceptLocal(text);
    if (match !== null) {
      return {
        role: "mentor",
        content: match.interpretation,
        kind: "concept",
        concept: {
          id: match.id,
          name: match.concept,
          definition: match.definition,
          explanation: match.explanation,
          example: match.example,
          formula: match.formula,
          interpretation: match.interpretation,
          related: match.related,
          followup_question:
            "Bạn hiểu cách áp dụng khái niệm này vào một tình huống cụ thể của mình không? Hãy thử mô tả quyết định bạn đang cân nhắc.",
        },
      };
    }
    return {
      role: "mentor",
      content: `${intro} Glossary demo chưa có khái niệm này. Hãy thử hỏi về một thuật ngữ như P/E, ROE, net margin, cắt lỗ, lãi kép, FOMO, hỗ trợ/kháng cự...`,
    };
  }

  if (mode === "trade_now" && selectedSymbol !== undefined) {
    const matches = matchKnowledgeLocal(text);
    const riskLine =
      matches.length > 0
        ? `Về mặt kiến thức liên quan (${matches
            .map((m) => m.concept)
            .join(", ")}), hãy đối chiếu quyết định của bạn với nguyên tắc quản trị rủi ro.`
        : "Hãy đối chiếu quyết định của bạn với nguyên tắc quản trị rủi ro.";
    return {
      role: "mentor",
      content: `${intro} Bạn đang cân nhắc giao dịch ${selectedSymbol}. ${riskLine}\nNhững câu hỏi để tự phản biện: bạn đã xác định mức lỗ tối đa chấp nhận cho mã này chưa? Tỷ trọng vị thế dự kiến là bao nhiêu so với tổng tài sản?`,
    };
  }

  if (mode === "plan") {
    return {
      role: "mentor",
      content: `${intro} Ở chế độ đề xuất hướng đầu tư, hãy cho mình biết thêm: mục tiêu của bạn là tăng trưởng, thu nhập hay bảo toàn vốn? Nhịp đầu tư dài bao lâu, và bạn chấp nhận rủi ro ở mức nào? Dựa trên đó mình sẽ gợi ý một khung chiến lược để bạn tự đánh giá.`,
    };
  }

  const matches = matchKnowledgeLocal(text);
  if (matches.length === 0) {
    return {
      role: "mentor",
      content: `${intro} Mình đã ghi nhận câu hỏi "${text}". Hãy thử đặt câu hỏi phản biện: thông tin bạn dựa vào đến từ đâu, và độ tin cậy của nó được kiểm chứng thế nào?`,
    };
  }
  const parts = matches.map((m) => `• ${m.concept}: ${m.definition}`);
  return {
    role: "mentor",
    content: `${intro} Những khái niệm liên quan tới "${text}":\n${parts.join("\n")}`,
  };
}