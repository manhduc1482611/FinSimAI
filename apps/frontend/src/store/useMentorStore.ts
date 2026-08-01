/**
 * Mentor store — phiên chat Socratic với Mentor qua WebSocket.
 *
 * Luồng WebSocket do `useSocraticMentor` quản lý; store chỉ giữ **trạng thái UI**:
 * session id, danh sách tin nhắn, trạng thái streaming/ready/lỗi.
 */
import { create } from "zustand";

import type { WsServerMessage } from "@/types/websocket";

export interface MentorMessage {
  id: string;
  role: "user" | "mentor";
  content: string;
  ts: string;
}

interface MentorState {
  /** Session id đang hoạt động (sinh phía client). */
  sessionId: string | null;
  messages: MentorMessage[];
  /** Mentor đang stream phản hồi. */
  isStreaming: boolean;
  /** Kết nối WS sẵn sàng nhận câu hỏi. */
  isReady: boolean;
  lastError: string | null;
  /** Bắt đầu phiên mới, xoá tin nhắn cũ. */
  startSession: () => void;
  resetSession: () => void;
  pushUserMessage: (content: string) => void;
  onServerMessage: (message: WsServerMessage) => void;
  setReady: (ready: boolean) => void;
  setError: (error: string | null) => void;
}

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export const useMentorStore = create<MentorState>()((set, get) => ({
  sessionId: null,
  messages: [],
  isStreaming: false,
  isReady: false,
  lastError: null,

  startSession: () => {
    set({
      sessionId: createId(),
      messages: [],
      isStreaming: false,
      lastError: null,
    });
  },

  resetSession: () => {
    set({
      sessionId: null,
      messages: [],
      isStreaming: false,
      isReady: false,
      lastError: null,
    });
  },

  pushUserMessage: (content) => {
    const { sessionId } = get();
    const message: MentorMessage = {
      id: createId(),
      role: "user",
      content,
      ts: new Date().toISOString(),
    };
    set({
      sessionId: sessionId ?? createId(),
      messages: [...get().messages, message],
      isStreaming: true,
      lastError: null,
    });
  },

  onServerMessage: (message) => {
    switch (message.type) {
      case "mentor_ready": {
        set({ isReady: true, lastError: null });
        break;
      }
      case "mentor_start": {
        set({ isStreaming: true, lastError: null });
        break;
      }
      case "mentor_chunk": {
        set({
          messages: appendChunk(get().messages, message.data.text),
        });
        break;
      }
      case "mentor_end": {
        set({ isStreaming: false });
        break;
      }
      case "mentor_cancelled": {
        set({ isStreaming: false });
        break;
      }
      case "mentor_error": {
        set({ isStreaming: false, lastError: message.data.message });
        break;
      }
      case "error": {
        set({ lastError: message.data.message ?? message.data.code });
        break;
      }
      default:
        // Các sự kiện khác (welcome, ping…) không ảnh hưởng mentor chat.
        break;
    }
  },

  setReady: (ready) => {
    set({ isReady: ready });
  },

  setError: (error) => {
    set({ lastError: error });
  },
}));

/** Append text vào tin nhắn mentor cuối cùng (streaming), hoặc tạo mới. */
function appendChunk(
  messages: MentorMessage[],
  text: string,
): MentorMessage[] {
  const last = messages[messages.length - 1];
  if (last && last.role === "mentor") {
    return [
      ...messages.slice(0, -1),
      { ...last, content: last.content + text },
    ];
  }
  const chunk: MentorMessage = {
    id: createId(),
    role: "mentor",
    content: text,
    ts: new Date().toISOString(),
  };
  return [...messages, chunk];
}
