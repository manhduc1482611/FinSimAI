/**
 * useWebSocket — hook quản lý vòng đời WebSocket với reconnect có backoff + jitter.
 *
 * - Tự động reconnect khi server đóng (nhất là close code 1012 = rolling restart).
 * - Dừng hẳn (không spam) khi bị từ chối xác thực (1008).
 * - Heartbeat: gửi `{"action":"ping"}` mỗi 30s để giữ kết nối qua proxy.
 * - Message server → client được parse thành `WsServerMessage` (không dùng `any`).
 */
import { useEffect, useRef, useState } from "react";

import { WS_CLOSE_CODES, type WsClientMessage, type WsServerMessage } from "@/types/websocket";

export type WsConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error";

export interface UseWebSocketOptions {
  url: string | null;
  /** Khi false, không mở kết nối (ví dụ: chưa đăng nhập). */
  enabled?: boolean;
  onMessage?: (message: WsServerMessage) => void;
  onOpen?: () => void;
  onClose?: (code: number, reason: string) => void;
  maxRetries?: number;
}

export interface UseWebSocketResult {
  status: WsConnectionStatus;
  lastError: string | null;
  /** Gửi message client → server (no-op khi socket chưa mở). */
  sendMessage: (message: WsClientMessage) => void;
}

const HEARTBEAT_INTERVAL_MS = 30_000;

/** Parse một message từ server thành `WsServerMessage` — trả null nếu không hợp lệ. */
export function parseWsMessage(raw: string): WsServerMessage | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return null;
    }
    const envelope = parsed as { type?: unknown; data?: unknown; ts?: unknown; seq?: unknown };
    if (typeof envelope.type !== "string") {
      return null;
    }
    if (typeof envelope.ts !== "string" && envelope.type !== "error") {
      return null;
    }
    return parsed as WsServerMessage;
  } catch {
    return null;
  }
}

function shouldStopRetry(code: number): boolean {
  // 1008: auth reject — ticket/phiên không hợp lệ, tránh spam reconnect.
  return code === WS_CLOSE_CODES.AUTH_REJECT;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketResult {
  const { url, enabled = true, onMessage, onOpen, onClose, maxRetries = 10 } = options;

  const socketRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlersRef = useRef({ onMessage, onOpen, onClose });
  handlersRef.current = { onMessage, onOpen, onClose };

  const [status, setStatus] = useState<WsConnectionStatus>("idle");
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !url) {
      setStatus("idle");
      return;
    }

    const socketUrl: string = url;
    let disposed = false;

    const clearHeartbeat = () => {
      if (heartbeatRef.current !== null) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    };

    const clearReconnect = () => {
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    function scheduleReconnect(code: number) {
      if (disposed) {
        return;
      }
      if (shouldStopRetry(code)) {
        setStatus("error");
        setLastError("Phiên đăng nhập không hợp lệ — vui lòng đăng nhập lại.");
        return;
      }
      if (retryCountRef.current >= maxRetries) {
        setStatus("error");
        setLastError(`Mất kết nối (sau ${maxRetries} lần thử). Vui lòng tải lại trang.`);
        return;
      }
      const attempt = retryCountRef.current;
      const baseDelay = Math.min(1000 * 2 ** attempt, 15_000);
      const jitterMs = ((Date.now() % 300) + 1) * 1;
      retryCountRef.current += 1;
      setStatus("connecting");
      reconnectTimerRef.current = setTimeout(connect, baseDelay + jitterMs);
    }

    function sendHeartbeat() {
      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: "ping" } satisfies WsClientMessage));
      }
    }

    function connect() {
      if (disposed) {
        return;
      }
      setStatus("connecting");
      setLastError(null);

      if (typeof window === "undefined" || typeof WebSocket === "undefined") {
        setStatus("error");
        setLastError("Trình duyệt không hỗ trợ WebSocket");
        return;
      }

      let socket: WebSocket;
      try {
        socket = new WebSocket(socketUrl);
      } catch (error) {
        setStatus("error");
        setLastError(error instanceof Error ? error.message : "Không mở được WebSocket");
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        if (disposed) {
          return;
        }
        retryCountRef.current = 0;
        setStatus("open");
        handlersRef.current.onOpen?.();
        clearHeartbeat();
        heartbeatRef.current = window.setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        const message = parseWsMessage(event.data);
        if (message !== null) {
          handlersRef.current.onMessage?.(message);
        }
      };

      socket.onerror = () => {
        // WebSocket không có event error có dữ liệu; việc đóng sẽ trigger onclose.
      };

      socket.onclose = (event: CloseEvent) => {
        if (disposed) {
          return;
        }
        clearHeartbeat();
        handlersRef.current.onClose?.(event.code, event.reason);
        scheduleReconnect(event.code);
      };
    }

    connect();

    return () => {
      disposed = true;
      clearHeartbeat();
      clearReconnect();
      socketRef.current?.close(1000, "component unmounted");
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, enabled, maxRetries]);

  const sendMessage = (message: WsClientMessage): void => {
    socketRef.current?.send(JSON.stringify(message));
  };

  return { status, lastError, sendMessage };
}
