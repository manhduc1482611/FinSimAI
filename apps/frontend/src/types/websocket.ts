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

/** Chế độ trả lời của Mentor (kế hoạch 3 chế độ v2.0). */
export type MentorMode = "socratic" | "concept" | "plan" | "trade_now";

/** Client CHỈ gửi mode + selected_symbol — mọi số liệu tài chính lấy từ server. */
export interface TradeContext {
  mode: MentorMode;
  selected_symbol?: string;
}

/** Card khái niệm (Chế độ 1) — đồng bộ schema ConceptReply của ai_engine. */
export interface ConceptReply {
  id: string;
  name: string;
  definition: string;
  explanation?: string;
  example?: string;
  formula?: string;
  interpretation?: string;
  related: string[];
  followup_question: string;
  disclaimer?: string;
  difficulty?: number;
  category?: string;
}

/** Card khung chiến lược (Chế độ 2) — đồng bộ schema StrategyReply của ai_engine. */
export interface StrategyReply {
  framework_id: string;
  framework_name: string;
  criteria: string[];
  allocation_rule: string;
  risk_rule: string;
  how_to_trade: string[];
  questions: string[];
  disclaimer?: string;
}

/** Card phản biện lúc giao dịch (Chế độ 3) — challenge kèm risk flags từ server. */
export interface MentorChallenge {
  focus: string;
  risk_flags: string[];
  questions: string[];
  coaching_tip: string;
  disclaimer?: string;
}

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
  /** Phí môi giới 0.15% giá trị khớp (cả hai chiều) — realism engine B1. */
  fee?: number;
  /** Thuế bán 0.1% giá trị khớp (chỉ chiều sell). */
  tax?: number;
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
  mode?: MentorMode;
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
  code?: string;
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
  | WsEnvelope<ConceptReply> & { type: "mentor_concept" }
  | WsEnvelope<StrategyReply> & { type: "mentor_strategy" }
  | WsEnvelope<MentorChallenge> & { type: "mentor_challenge" }
  | WsEnvelope<WsErrorData> & { type: "error" };

/** Tin nhắn client → server. */
export type WsClientMessage =
  | { action: "ping" }
  | { action: "subscribe" | "unsubscribe"; channels: string[] }
  | { action: "snapshot" }
  | {
      action: "ask";
      message: string;
      session_id: string;
      trade_context?: TradeContext;
    }
  | { action: "cancel"; session_id: string };

/** Mã close chuẩn phía server (tương ứng connection_manager.py). */
export const WS_CLOSE_CODES = {
  AUTH_REJECT: 1008,
  RELIABLE_OVERFLOW: 1011,
  SERVER_RESTART: 1012,
} as const;

export type WsCloseCode = (typeof WS_CLOSE_CODES)[keyof typeof WS_CLOSE_CODES];
