/**
 * Type cho luồng WebSocket của Backend Gateway (xem `websockets/*.py`).
 *
 * Envelope chuẩn (connection_manager.build_message):
 *   { "type": string, "data": object, "ts": ISO-8601, "seq"?: number }
 *
 * Giá (price_ws): price/open/high/low/prev_close/change/change_pct là number (float).
 * Khớp lệnh (trade_ws): quantity/price/total là number (đã float() trong _enrich).
 * order_update: quantity/filled_quantity giữ Decimal → trên wire là string.
 */

/** Trạng thái nguồn realtime (tham chiếu realtime_status của server). */
export type RealtimeStatus = "live" | "degraded";

export interface WsEnvelope<T> {
  type: string;
  data: T;
  ts: string;
  seq?: number;
}

/** Tick giá từ `price_ws.PriceBroadcaster._build_tick`. */
export interface PriceTick {
  symbol: string;
  company_id: string;
  name?: string | null;
  sector?: string | null;
  price: number;
  open: number;
  high: number;
  low: number;
  prev_close: number;
  change: number;
  change_pct: number;
  market_cap?: number | null;
  sim_day: number;
  simulated_at: string;
}

/** Sự kiện khớp lệnh từ `trade_ws.TradeNotifier._enrich`. */
export interface TradeFill {
  transaction_id: string;
  order_id: string;
  company_id: string;
  user_id: string;
  symbol: string;
  company_name?: string | null;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  total: number;
  simulated_at?: string | null;
}

/** Cập nhật trạng thái lệnh từ `trade_ws.notify_order_update`. */
export interface OrderUpdate {
  order_id: string;
  company_id: string;
  symbol?: string | null;
  status: string;
  side?: string | null;
  quantity?: string | null;
  filled_quantity?: string | null;
  simulated_at?: string | null;
}

export interface WsWelcomeData {
  connection_id?: string;
  user_id?: string;
  channel?: string;
  realtime_status: RealtimeStatus;
}

export interface WsChannelsData {
  channels?: string[];
  active_rooms?: string[];
}

export interface WsFeedStatusData {
  status: RealtimeStatus;
  reason: string;
  since: string;
  resync_via?: string[];
}

export interface WsMentorReadyData {
  user_id?: string;
  realtime_status: RealtimeStatus;
}

export interface WsMentorStartData {
  session_id: string;
  user_id?: string;
}

export interface WsMentorChunkData {
  session_id: string;
  text: string;
}

export interface WsMentorEndData {
  session_id: string;
  reason: string;
}

export interface WsMentorCancelledData {
  session_id: string;
}

export interface WsMentorErrorData {
  session_id: string;
  message: string;
}

export interface WsErrorData {
  code: string;
  message?: string;
  action?: string;
}

/** Tin nhắn server → client (discriminated union theo `type`). */
export type WsServerMessage =
  | WsEnvelope<WsWelcomeData> & { type: "welcome" }
  | WsEnvelope<Record<string, never>> & { type: "ping" | "pong" }
  | WsEnvelope<WsChannelsData> & { type: "subscribed" | "unsubscribed" }
  | WsEnvelope<PriceTick> & { type: "price_tick" | "price_snapshot" }
  | WsEnvelope<TradeFill> & { type: "trade_fill" }
  | WsEnvelope<OrderUpdate> & { type: "order_update" }
  | WsEnvelope<WsFeedStatusData> & { type: "feed_status" }
  | WsEnvelope<WsMentorReadyData> & { type: "mentor_ready" }
  | WsEnvelope<WsMentorStartData> & { type: "mentor_start" }
  | WsEnvelope<WsMentorChunkData> & { type: "mentor_chunk" }
  | WsEnvelope<WsMentorEndData> & { type: "mentor_end" }
  | WsEnvelope<WsMentorCancelledData> & { type: "mentor_cancelled" }
  | WsEnvelope<WsMentorErrorData> & { type: "mentor_error" }
  | WsEnvelope<WsErrorData> & { type: "error" };

/** Tin nhắn client → server. */
export type WsClientMessage =
  | { action: "ping" }
  | { action: "subscribe" | "unsubscribe"; channels: string[] }
  | { action: "snapshot" }
  | { action: "ask"; message: string; session_id: string }
  | { action: "cancel"; session_id: string };

/** Mã close chuẩn phía server (tương ứng connection_manager.py). */
export const WS_CLOSE_CODES = {
  AUTH_REJECT: 1008,
  RELIABLE_OVERFLOW: 1011,
  SERVER_RESTART: 1012,
} as const;

export type WsCloseCode = (typeof WS_CLOSE_CODES)[keyof typeof WS_CLOSE_CODES];
