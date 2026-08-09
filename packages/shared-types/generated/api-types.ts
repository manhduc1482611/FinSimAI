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

export type JsonValue = string | number | boolean | null | JsonValue[]
    | { [key: string]: JsonValue };

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
  refresh_token?: string | null
  token_type?: string
  expires_in?: number | null
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
  cooldown_until: string | null
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

// ─── SOCIAL · SOCIAL_COMMENT_CREATE ───
export interface SocialCommentCreate {
  content: string
}

// ─── SOCIAL · SOCIAL_COMMENT_LIST_RESPONSE ───
export interface SocialCommentListResponse {
  items: SocialCommentResponse[]
  total: number
}

// ─── SOCIAL · SOCIAL_COMMENT_RESPONSE ───
export interface SocialCommentResponse {
  id: string
  post_id: string
  author_name: string
  author_avatar: string | null
  content: string
  created_at: string
}

// ─── SOCIAL · SOCIAL_LIKE_RESPONSE ───
export interface SocialLikeResponse {
  liked: boolean
  likes_count: number
}

// ─── SOCIAL · SOCIAL_POST_CREATE ───
export interface SocialPostCreate {
  content: string
  company_symbol?: string | null
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
  liked_by_me?: boolean
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

// ─── RISK · COOLDOWN_STATUS ───
export interface CooldownStatus {
  locked: boolean
  cooldown_until?: string | null
  remaining_seconds?: number
  risk_score?: number
  reason?: string | null
}

// ─── RISK · PENALTY_REQUEST ───
export interface PenaltyRequest {
  trap_type?: string
  severity: number
  description?: string | null
}

// ─── RISK · PENALTY_RESPONSE ───
export interface PenaltyResponse {
  new_risk_score: number
  risk_score_delta: number
  points_deducted: number
  cooldown_seconds: number
  cooldown_until?: string | null
  reason?: string | null
}

// ─── CONTEST · CONTEST_CONFIG ───
export interface ContestConfig {
  template?: "classic" | "tech_news" | "fast_paced" | "micro"
  theme?: ContestTheme
  industry?: string
  company_count?: number
  difficulty?: "easy" | "normal" | "hard"
  auto_news?: boolean
  auto_social?: boolean
  rules?: ContestRules
  content?: ContestContentMeta
}

// ─── CONTEST · CONTEST_CONTENT_META ───
export interface ContestContentMeta {
  generated?: boolean
  generated_at?: string | null
  company_count?: number
  news_count?: number
  social_count?: number
  symbols?: string[]
}

// ─── CONTEST · CONTEST_CREATE_REQUEST ───
export interface ContestCreateRequest {
  name: string
  slug?: string | null
  description?: string | null
  template?: "classic" | "tech_news" | "fast_paced" | "micro"
  industry?: string
  company_count?: number | null
  difficulty?: "easy" | "normal" | "hard"
  auto_news?: boolean
  auto_social?: boolean
  theme?: ContestTheme
}

// ─── CONTEST · CONTEST_JOIN_RESPONSE ───
export interface ContestJoinResponse {
  joined: boolean
  contest_id: string
}

// ─── CONTEST · CONTEST_LIST_RESPONSE ───
export interface ContestListResponse {
  items: ContestResponse[]
  total: number
}

// ─── CONTEST · CONTEST_RESPONSE ───
export interface ContestResponse {
  id: string
  slug: string
  name: string
  description: string | null
  status: string
  config: ContestConfig
  owner_id: string | null
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  member_count?: number
}

// ─── CONTEST · CONTEST_RULES ───
export interface ContestRules {
  start_cash?: string
  cooldown_seconds?: number
  allow_short?: boolean
  volatility_multiplier?: number
  trading_duration_days?: number | null
}

// ─── CONTEST · CONTEST_TEMPLATE ───
export interface ContestTemplate {
  id: "classic" | "tech_news" | "fast_paced" | "micro"
  label: string
  description: string
  default_company_count: number
  default_industry: string
  default_rules: ContestRules
  news_emphasis: boolean
}

// ─── CONTEST · CONTEST_THEME ───
export interface ContestTheme {
  primary_color?: string
  logo_url?: string | null
}

// ─── CONTEST · CONTEST_UPDATE_REQUEST ───
export interface ContestUpdateRequest {
  name?: string | null
  slug?: string | null
  description?: string | null
  template?: "classic" | "tech_news" | "fast_paced" | "micro" | null
  industry?: string | null
  company_count?: number | null
  difficulty?: "easy" | "normal" | "hard" | null
  auto_news?: boolean | null
  auto_social?: boolean | null
  theme?: ContestTheme | null
}

// ─── ADMIN · ADMIN_CONTEST_LIST_RESPONSE ───
export interface AdminContestListResponse {
  items: AdminContestResponse[]
  total: number
}

// ─── ADMIN · ADMIN_CONTEST_RESPONSE ───
export interface AdminContestResponse {
  id: string
  slug: string
  name: string
  description: string | null
  status: string
  config: ContestConfig
  owner_id: string | null
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  member_count?: number
}

// ─── ADMIN · ADMIN_CONTEST_STATUS_UPDATE ───
export interface AdminContestStatusUpdate {
  status: "draft" | "active" | "ended"
}

// ─── ADMIN · ADMIN_ROLE_UPDATE ───
export interface AdminRoleUpdate {
  role: "user" | "host" | "admin"
}

// ─── ADMIN · ADMIN_STATUS_UPDATE ───
export interface AdminStatusUpdate {
  is_active: boolean
}

// ─── ADMIN · ADMIN_USER_LIST_RESPONSE ───
export interface AdminUserListResponse {
  items: AdminUserResponse[]
  total: number
}

// ─── ADMIN · ADMIN_USER_RESPONSE ───
export interface AdminUserResponse {
  id: string
  email: string
  username: string
  display_name: string | null
  role: string
  is_active: boolean
  created_at: string
}

// ─── TASK · CHECKIN_RESPONSE ───
export interface CheckinResponse {
  already_checked_in: boolean
  current_streak: number
  longest_streak: number
  reward_earned: string
}

// ─── TASK · TASK_ADMIN_CREATE_REQUEST ───
export interface TaskAdminCreateRequest {
  code: string
  name: string
  description?: string | null
  category: "onboarding" | "learning" | "daily" | "streak" | "contest"
  reward_amount: string
  target_count?: number
  reset_frequency?: "none" | "daily"
  is_active?: boolean
  sort_order?: number
}

// ─── TASK · TASK_ADMIN_LIST_RESPONSE ───
export interface TaskAdminListResponse {
  items: TaskAdminResponse[]
  total: number
}

// ─── TASK · TASK_ADMIN_RESPONSE ───
export interface TaskAdminResponse {
  id: string
  code: string
  name: string
  description: string | null
  category: "onboarding" | "learning" | "daily" | "streak" | "contest"
  reward_amount: string
  target_count: number
  reset_frequency: "none" | "daily"
  is_active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

// ─── TASK · TASK_ADMIN_UPDATE_REQUEST ───
export interface TaskAdminUpdateRequest {
  name?: string | null
  description?: string | null
  category?: "onboarding" | "learning" | "daily" | "streak" | "contest" | null
  reward_amount?: string | null
  target_count?: number | null
  reset_frequency?: "none" | "daily" | null
  is_active?: boolean | null
  sort_order?: number | null
}

// ─── TASK · TASK_CLAIM_RESPONSE ───
export interface TaskClaimResponse {
  task: TaskResponse
  progress_count: number
  target_count: number
  completed: boolean
  reward_earned: string
}

// ─── TASK · TASK_EVENT_REQUEST ───
export interface TaskEventRequest {
  event: string
}

// ─── TASK · TASK_EVENT_RESPONSE ───
export interface TaskEventResponse {
  accepted: boolean
  rewarded: boolean
}

// ─── TASK · TASK_LIST_RESPONSE ───
export interface TaskListResponse {
  streak_current: number
  streak_longest: number
  total_reward_earned: string
  tasks: TaskProgressResponse[]
}

// ─── TASK · TASK_PROGRESS_RESPONSE ───
export interface TaskProgressResponse {
  task: TaskResponse
  progress_count: number
  target_count: number
  completed: boolean
  claimable?: boolean
  completed_at?: string | null
}

// ─── TASK · TASK_RESPONSE ───
export interface TaskResponse {
  id: string
  code: string
  name: string
  description: string | null
  category: "onboarding" | "learning" | "daily" | "streak" | "contest"
  reward_amount: string
  target_count: number
  reset_frequency: "none" | "daily"
}

// ─── ERROR SHAPE (FastAPI mặc định) ───
export interface ApiError {
  detail: string;
}
