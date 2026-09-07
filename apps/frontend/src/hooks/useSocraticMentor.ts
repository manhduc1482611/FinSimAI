/**
 * useSocraticMentor — kết nối WS tới `/ws/mentor` (qua ticket single-use) và
 * điều phối luồng chat: câu hỏi → stream chunk → kết thúc.
 *
 * Trạng thái tin nhắn nằm trong `useMentorStore`; hook chỉ quản lý socket.
 */
import { useEffect, useState } from "react";

import { getWsBaseUrl, isDemoMode } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { reportTaskEvent } from "@/services/tasks";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { matchKnowledgeLocal } from "@/utils/knowledge_matcher";

export interface SocraticMentor {
  messages: ReturnType<typeof useMentorStore.getState>["messages"];
  isStreaming: boolean;
  isReady: boolean;
  isConnected: boolean;
  lastError: string | null;
  sendAsk: (text: string) => void;
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

  const sendAsk = (text: string): void => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) {
      return;
    }
    const store = useMentorStore.getState();

    // Demo mode: không có WebSocket → trả lời bằng glossary local.
    if (isDemoMode()) {
      store.pushUserMessage(trimmed);
      void reportTaskEvent("mentor_chat").catch(() => {
        // bỏ qua lỗi tracking
      });
      // Simulate nhỏ để có cảm giác stream.
      setTimeout(() => {
        const matches = matchKnowledgeLocal(trimmed, 2);
        const reply = buildDemoMentorReply(trimmed, matches);
        useMentorStore.setState({ messages: [...useMentorStore.getState().messages, {
          id: `m-${Date.now()}`, role: "mentor", content: reply, ts: new Date().toISOString(),
        }], isStreaming: false });
      }, 600);
      return;
    }

    if (wsStatus !== "open") {
      store.setError("Chưa kết nối được tới Mentor — vui lòng thử lại sau giây lát.");
      return;
    }
    store.pushUserMessage(trimmed);
    void reportTaskEvent("mentor_chat").catch(() => {
      // Báo sự kiện thưởng lỗi không ảnh hưởng luồng chat.
    });
    const sessionId = useMentorStore.getState().sessionId;
    if (sessionId) {
      sendMessage({ action: "ask", message: trimmed, session_id: sessionId });
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

/** Dựng câu trả lời demo cho Mentor dựa trên glossary local. */
function buildDemoMentorReply(
  text: string,
  matches: ReturnType<typeof matchKnowledgeLocal>,
): string {
  const intro = "Mentor (Demo):";
  if (matches.length === 0) {
    return `${intro} Mình đã ghi nhận câu hỏi "${text}". Ở chế độ demo, hãy hỏi về các khái niệm như P/E, ROE, biên lợi nhuận ròng, cắt lỗ, quản trị rủi ro, khối lượng, hỗ trợ/kháng cự, hoặc lệnh market/limit.`;
  }
  const parts = matches.map(
    (m) => `• ${m.concept}: ${m.definition}`,
  );
  return `${intro} Đây là những khái niệm liên quan tới "${text}":\n${parts.join("\n")}`;
}
