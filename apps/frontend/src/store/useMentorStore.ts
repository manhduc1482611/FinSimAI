/**
 * Mentor store — phiên chat với Mentor qua WebSocket (3 chế độ v2.0).
 *
 * Luồng WebSocket do `useSocraticMentor` quản lý; store giữ **trạng thái UI**:
 * session id, mode hiện tại, selected_symbol, danh sách tin nhắn (text + card
 * concept/strategy/challenge), trạng thái streaming/ready/lỗi.
 */
import { create } from "zustand";

import type {
  ConceptReply,
  MentorChallenge,
  MentorMode,
  StrategyReply,
  TradeContext,
  WsServerMessage,
} from "@/types/websocket";

export type MentorMessageKind = "text" | "concept" | "strategy" | "challenge";

export interface MentorMessage {
  id: string;
  role: "user" | "mentor";
  content: string;
  ts: string;
  /** Loại card khi tin nhắn mentor là structured (concept/strategy/challenge). */
  kind?: MentorMessageKind;
  concept?: ConceptReply;
  strategy?: StrategyReply;
  challenge?: MentorChallenge;
}

export interface MentorContext extends TradeContext {
  /** Mode mặc định khi user chưa chọn (socratic). */
  mode: MentorMode;
}

interface MentorState {
  /** Session id đang hoạt động (sinh phía client). */
  sessionId: string | null;
  messages: MentorMessage[];
  /** Mode + symbol đang dùng cho câu hỏi tiếp theo (kế hoạch 3 chế độ). */
  tradeContext: MentorContext;
  /** Đề nghị focus ô nhập từ bên ngoài (nút "Hỏi Mentor" trên trade page). */
  focusRequest: number;
  /** Mentor đang stream phản hồi. */
  isStreaming: boolean;
  /** Kết nối WS sẵn sàng nhận câu hỏi. */
  isReady: boolean;
  lastError: string | null;
  /** Đã nạp lịch sử từ DB cho phiên hiện tại (chống nạp lặp). */
  historyLoaded: boolean;
  /** Bắt đầu phiên mới, xoá tin nhắn cũ. */
  startSession: () => void;
  resetSession: () => void;
  pushUserMessage: (content: string) => void;
  pushMentorMessage: (message: Omit<MentorMessage, "id" | "ts">) => void;
  setTradeContext: (context: Partial<MentorContext>) => void;
  requestFocus: () => void;
  /** Nạp lịch sử từ DB khi mở panel lần đầu (A3.2). */
  seedHistory: (
    items: {
      id: string;
      role: "user" | "mentor";
      content: string;
      kind?: MentorMessageKind;
      ts: string;
    }[],
  ) => void;
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

const DEFAULT_CONTEXT: MentorContext = {
  mode: "socratic",
  selected_symbol: undefined,
};

export const useMentorStore = create<MentorState>()((set, get) => ({
  sessionId: null,
  messages: [],
  tradeContext: { ...DEFAULT_CONTEXT },
  focusRequest: 0,
  isStreaming: false,
  isReady: false,
  lastError: null,
  historyLoaded: false,

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
      tradeContext: { ...DEFAULT_CONTEXT },
      isStreaming: false,
      isReady: false,
      lastError: null,
      historyLoaded: false,
    });
  },

  seedHistory: (items) => {
    if (get().historyLoaded || items.length === 0) {
      set({ historyLoaded: true });
      return;
    }
    set({
      historyLoaded: true,
      // Giữ session id hiện tại; lịch sử cũ chỉ để xem, câu mới thuộc phiên này.
      messages: [...items, ...get().messages],
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

  pushMentorMessage: (message) => {
    const { sessionId } = get();
    const full: MentorMessage = {
      id: createId(),
      ...message,
      ts: new Date().toISOString(),
    };
    set({
      sessionId: sessionId ?? createId(),
      messages: [...get().messages, full],
    });
  },

  setTradeContext: (context) => {
    set({
      tradeContext: { ...get().tradeContext, ...context },
    });
  },

  requestFocus: () => {
    set({ focusRequest: get().focusRequest + 1 });
  },

  onServerMessage: (message) => {
    switch (message.type) {
      case "mentor_ready": {
        set({ isReady: true, lastError: null });
        break;
      }
      case "mentor_start": {
        set({
          isStreaming: true,
          lastError: null,
          tradeContext: {
            ...get().tradeContext,
            mode: message.data.mode ?? get().tradeContext.mode,
          },
        });
        break;
      }
      case "mentor_chunk": {
        set({
          messages: appendChunk(get().messages, message.data.text),
        });
        break;
      }
      case "mentor_concept": {
        // Server đã trả card concept — thêm card, text followup nếu có.
        set({
          isStreaming: false,
          messages: [
            ...get().messages,
            {
              id: createId(),
              role: "mentor",
              content: message.data.followup_question ?? "",
              ts: new Date().toISOString(),
              kind: "concept",
              concept: message.data,
            },
          ],
        });
        break;
      }
      case "mentor_strategy": {
        set({
          isStreaming: false,
          messages: [
            ...get().messages,
            {
              id: createId(),
              role: "mentor",
              content: "",
              ts: new Date().toISOString(),
              kind: "strategy",
              strategy: message.data,
            },
          ],
        });
        break;
      }
      case "mentor_challenge": {
        set({
          isStreaming: false,
          messages: [
            ...get().messages,
            {
              id: createId(),
              role: "mentor",
              content: "",
              ts: new Date().toISOString(),
              kind: "challenge",
              challenge: message.data,
            },
          ],
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
        set({
          isStreaming: false,
          lastError: message.data.message ?? "Mentor gặp lỗi.",
        });
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