/* eslint-disable */
// AUTO-GENERATED — DO NOT EDIT.
// Nguồn: scripts/generate_ts_types.py (Pydantic schemas của Backend Gateway).
//
// QUY ƯỚC TYPE (khớp đúng wire format của FastAPI):
//   - Decimal → string   (FastAPI serialize Decimal thành JSON string)
//   - datetime → string  (ISO-8601)
//   - uuid → string
//   - Optional field (có default) → `field?: T | null`
// Nếu backend đổi schema, chạy lại: `npm run generate:types` (root).

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

// ─── USER · LOGIN_REQUEST ───
export interface LoginRequest {
  username?: string | null
  email?: string | null
  password: string
}

// ─── USER · REGISTER_REQUEST ───
export interface RegisterRequest {
  email: string
  username: string
  password: string
  display_name?: string | null
}

// ─── USER · TOKEN_RESPONSE ───
export interface TokenResponse {
  access_token: string
  token_type?: string
}

// ─── USER · USER_RESPONSE ───
export interface UserResponse {
  id: string
  email: string
  username: string
  display_name: string | null
  avatar_url: string | null
  role: string
  cash_balance: string
  frozen_cash: string
  risk_score: number
  is_active: boolean
  created_at: string
}

// ─── USER · USER_UPDATE ───
export interface UserUpdate {
  display_name?: string | null
  avatar_url?: string | null
}

// ─── USER · WS_TICKET_RESPONSE ───
export interface WsTicketResponse {
  ticket: string
  ttl_seconds: number
  expires_at: string
}

// ─── NEWS · NEWS_LIST_RESPONSE ───
export interface NewsListResponse {
  items: NewsResponse[]
  total: number
}

// ─── NEWS · NEWS_RESPONSE ───
export interface NewsResponse {
  id: string
  title: string
  summary: string | null
  content: string
  source: string
  category: string
  sentiment: string
  impact_score: number
  company_id: string | null
  is_ai_generated: boolean
  simulated_at: string
  created_at: string
}

// ─── COMPANY · COMPANY_LIST_RESPONSE ───
export interface CompanyListResponse {
  items: CompanyResponse[]
  total: number
}

// ─── COMPANY · COMPANY_RESPONSE ───
export interface CompanyResponse {
  id: string
  symbol: string
  name: string
  description: string | null
  sector: string
  current_price: string
  volatility: string
  shares_outstanding: string
  market_cap: string | null
  health_score: number
  pe_ratio: string | null
  roe: string | null
  net_margin: string | null
}

// ─── TRADE · ORDER_REQUEST ───
export interface OrderRequest {
  company_id: string
  side: "buy" | "sell"
  type?: "market" | "limit"
  price?: string | null
  quantity: string
}

// ─── TRADE · ORDER_RESPONSE ───
export interface OrderResponse {
  id: string
  company_id: string
  side: "buy" | "sell"
  type: "market" | "limit"
  status: "pending" | "filled" | "partially_filled" | "cancelled" | "rejected"
  price: string | null
  quantity: string
  filled_quantity: string
  created_at: string
}

// ─── TRADE · PORTFOLIO_LIST_RESPONSE ───
export interface PortfolioListResponse {
  items: PortfolioResponse[]
  total_cash: string
  total_nav: string
}

// ─── TRADE · PORTFOLIO_RESPONSE ───
export interface PortfolioResponse {
  company_id: string
  symbol: string
  company_name: string
  quantity: string
  average_buy_price: string
  current_price: string
  market_value: string
  unrealized_pnl: string
}

// ─── SOCIAL · SOCIAL_POST_LIST_RESPONSE ───
export interface SocialPostListResponse {
  items: SocialPostResponse[]
  total: number
}

// ─── SOCIAL · SOCIAL_POST_RESPONSE ───
export interface SocialPostResponse {
  id: string
  author_name: string
  author_avatar: string | null
  persona_type: string
  content: string
  sentiment: string
  virality_score: number
  likes_count: number
  shares_count: number
  comments_count: number
  company_id: string | null
  news_id: string | null
  simulated_at: string
  created_at: string
}

// ─── KNOWLEDGE · KNOWLEDGE_LIST_RESPONSE ───
export interface KnowledgeListResponse {
  items: KnowledgeResponse[]
  total: number
}

// ─── KNOWLEDGE · KNOWLEDGE_MATCH_REQUEST ───
export interface KnowledgeMatchRequest {
  text: string
}

// ─── KNOWLEDGE · KNOWLEDGE_MATCH_RESPONSE ───
export interface KnowledgeMatchResponse {
  matches: KnowledgeResponse[]
}

// ─── KNOWLEDGE · KNOWLEDGE_RESPONSE ───
export interface KnowledgeResponse {
  id: string
  keyword: string
  concept: string
  definition: string
  category: string
  difficulty: number
  related_keywords: string[] | null
  created_at: string
}

// ─── ERROR SHAPE (FastAPI mặc định) ───
export interface ApiError {
  detail: string;
}
