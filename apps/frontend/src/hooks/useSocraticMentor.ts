/**
 * useSocraticMentor — kết nối WS tới `/ws/mentor` (qua ticket single-use) và
 * điều phối luồng chat: câu hỏi → stream chunk → kết thúc.
 *
 * Trạng thái tin nhắn nằm trong `useMentorStore`; hook chỉ quản lý socket.
 */
import { useEffect, useState } from "react";

import { getWsBaseUrl } from "@/services/api";
import { fetchWsTicket } from "@/services/auth";
import { reportTaskEvent } from "@/services/tasks";
import { useAuthStore } from "@/store/useAuthStore";
import { useMentorStore } from "@/store/useMentorStore";
import { useWebSocket } from "@/hooks/useWebSocket";

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
  const token = useAuthStore((state) => state.token);
  const messages = useMentorStore((state) => state.messages);
  const isStreaming = useMentorStore((state) => state.isStreaming);
  const isReady = useMentorStore((state) => state.isReady);
  const lastError = useMentorStore((state) => state.lastError);

  const [ticketUrl, setTicketUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setTicketUrl(null);
      useMentorStore.getState().setReady(false);
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
  }, [token]);

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
    isReady,
    isConnected: wsStatus === "open",
    lastError,
    sendAsk,
    sendCancel,
    reset,
  };
}
