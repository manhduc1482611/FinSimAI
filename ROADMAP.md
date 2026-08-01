# FinSimAI — Roadmap & Progress

> Consolidated from `docs/giaidoan*.md` files.

---

## Giai đoạn 1 — Backend Foundation (Hoàn thành)

- **Dự án monorepo**: Turborepo (JS) + UV workspace (Python), docker-compose (Postgres 16 + Redis 7), Makefile, `.env.example`.
- **Database**: schema 13 bảng + 8 ENUM + 23 index, migration Alembic, 4 bộ seed (companies, knowledge_base, scenarios, news_concept_map), script seed.
- **Math Engine** (thuần Python, không dùng LLM):
  - Pricing — sinh giá GBM, clip giá, bước giá kiểu VN
  - Portfolio — NAV, lãi/lỗ chưa thực hiện, mua/bán
  - Risk Metrics — Sharpe, Max Drawdown, Volatility
  - Time Compression — nén thời gian mô phỏng
  - Penalty — phạt rủi ro theo tier + cooldown
- **gRPC server**: 4 RPC, port 50051, proto + stubs sinh tự động.
- **Kiểm thử**: 93 unit test pass, coverage ~94%.

---

## Giai đoạn 2 — Backend Gateway + Realtime WebSocket (Hoàn thành)

- **Backend Gateway (FastAPI)** + **WebSocket real-time**:
  - `/ws/prices` — phát giá real-time theo time compression (tick, O/H/L, đổi sim day), leader election + snapshot cache.
  - `/ws/trades` — push `trade_fill`/`order_update` theo kênh user, xác thực trạng thái (claim-first SETNX + watermark), chống tin giả (`seq` theo kênh).
  - `/ws/mentor` — streaming trả lời mentor theo chunk, hỗ trợ hội thoại.
- **Bảo mật kết nối**: single-use ticket (không JWT trong URL), revalidation theo kỳ, heartbeat keepalive, cache chống DDoS Postgres.
- **Chạy multi-worker**: backplane Redis Pub/Sub (chỉ subscribe room các client), leader election fail-closed + fencing token, tự phục hồi khi Redis quay lại.
- **Chú ý lỗi**: một Redis ở chế độ degraded + `resync_via` REST; backpressure 2 queue (best-effort drop-oldest, reliable không drop); graceful shutdown ngắt WS bằng 1012.
- **Kiểm thử**: 102 unit test pass, `ruff` sạch.

---

## Giai đoạn 3 — AI Engine & Async Workers (Hoàn thành)

### 3.1 — AI Engine & Prompt Engineering (AI Agents + Gemini)

- **Kho Prompt tập trung** (`apps/ai_engine/prompts/`): loader `loader.py` (nạp YAML an toàn, render token `{{var}}`, cảnh báo token sát) + 5 file YAML — `mentor_prompts.yaml` (Socratic, 8 focus tâm lý + ngắt câu hỏi), `scenario_prompts.yaml` (5 loại bài báo giật gân), `social_prompts.yaml` (10 Persona MXH), `trap_prompts.yaml` (4 bẫy tâm lý), `insight_prompts.yaml` (gợi ý kiến thức).
- **Gemini integration** (`integrations/gemini.py`): Pydantic `response_schema` + `response_mime_type=application/json`, retry phân tách phản hồi (schema/policy), backoff, thiếu key thì `GeminiUnavailableError`, Agents dùng fallback deterministic 0-token.
- **Socratic Mentor Agent** (`agents/socratic_mentor.py`): không bao giờ khuyên Mua/Bán, không nhận xét đúng/sai mà bảo vệ 3 lớp (prompt chứa validator policy + retry/fallback). Fallback deterministic phát hiện 8 thiên kiến tâm lý, trả lời bằng câu hỏi ngắn gọn YAML.
- **Policy scanner** (`agents/policy.py`): chặn câu chứa từ khóa "nên mua/nên bán/khuyến nghị..." và "đúng/sai", miễn trừ câu hỏi.
- **Base Agent** (`agents/base.py`): chứa `GeminiClient` + `PromptStore`.
- **Demo CLI** (`tools/mentor_demo.py`): chạy được fallback.
- **Kiểm thử**: 44 unit test pass (prompt store + socratic mentor + policy), `ruff` sạch.
- **2 lỗi thực tế phát hiện**: `[{{industry}}]` bị parser hiểu nhầm flow mapping thành `["{{industry}}"]`; validator thêm `?` làm lỗi khuyên nên mua trên chuỗi trước khi thêm `?`.

### 3.2 — Async Task Worker (ARQ + Redis)

- **News sources** (`integrations/news_sources.py`): RSS fetcher `httpx` + `feedparser`, tách trang HTML, retry exponential, dedupe theo GUID; `default_feed_config()` = 4 Google News RSS + 3 VnExpress RSS (kiểm tra live: Cafef/Vietstock 404, `kinh-doanh/chung-khoan.rss` trả HTML).
- **Rate limiter Gemini** (`integrations/rate_limiter.py`): token bucket trên Redis + distributed lock (SET NX EX — dùng fakeredis cho test và không cần Lua EVAL), chặn gọi API khi worker chạy đồng thời.
- **Task crawl** (`tasks/crawl_tasks.py`): `crawl_news` cào 7 nguồn, đánh dấu trạng thái qua Redis `SET NX`, lưu `news:latest`; `latest_news` được theo dõi thực tế mỗi phút.
- **Task sinh nội dung** (`tasks/scenario_tasks.py`): `generate_scenario_batch` (bài báo giật gân) + `generate_social_posts` (bài MXH từ 10 personas) — gọi Gemini qua rate limiter, **tự động fallback deterministic 0-token** khi thiếu key/lỗi API/hết quota; mỗi bài MXH kèm `has_deception` + `deception_note` (tự động nhận diện nội dung thao túng).
- **Worker** (`tasks/worker.py`): WorkerSettings 3 functions + 3 cron (crawl 30p, scenario 4h, social 2h), `on_startup` setup ctx, CLI `--check` / `--burst` / `--debug`, rate limit cấu hình qua env.
- **CLI** (`tools/run_tasks.py`): enqueue / `--wait` / `--sync` / `latest-news` / `result <job_id>`.
- **Kiểm thử**: 79 unit test pass (news_sources + rate_limiter + crawl + scenario + worker settings), `ruff` sạch.

### 3.2+ — Chưa bắt đầu triển khai

Các file stub trống (0 bytes), chưa triển khai:
- `agents/scenario_gen.py`, `agents/news_insight.py`, `agents/social_agent.py`, `agents/news_crawler.py`, `agents/behavior_analyzer.py`
- `main_ai.py`

### Trạng thái

Giai đoạn 3.1 + 3.2 hoàn thành (chạy thử trên Redis portable + Gemini thật, xem bản demo).

### Ghi chú thực tế (đã chạy thử)

- **Redis portable**: `C:\Users\ADMIN\AppData\Local\Temp\opencode\redis\opencode.conf` — cần `bind 127.0.0.1 ::1` (Python resolve `localhost` thành `::1` trước); khởi tạo: `Start-Process redis-server.exe opencode.conf`.
- **API key**: đặt `GEMINI_API_KEY` trong `.env` để gitignore. Key free-tier gemini-2.5-flash có **quota 20 req/ngày** và khi hết quota (429 RESOURCE_EXHAUSTED) task tự fallback deterministic, không crash, log cảnh báo.
- **Kết quả chạy thử**: crawl 140 bài/0 lỗi; scenario/social sinh bài tiếng Việt tự động schema qua Gemini; `latest-news` hiển thị tin mới nhất từ Google News RSS; worker `--burst` xử lý job trong queue rồi thoát.
- **3 lỗi thực tế phát hiện khi chạy thực tế**: (1) ARQ `get_kwargs` chỉ được `__dict__` và chỉ burst một `functions`/`on_startup` (đã thêm `_burst_settings()` + test hồi quy); (2) `pool.get_job` bị bug ARQ 0.28 và dùng `arq.jobs.Job(job_id, pool)`; (3) `asyncio.TimeoutError` và `TimeoutError` trùng tên (ruff UP041).

---

## Giai đoạn 4 — Frontend UI/UX (Đang triển khai)

### Trang (App Router)
- Landing `/` — giới thiệu tính năng, chuyển hướng `/news` khi đã đăng nhập.
- Auth: `/login`, `/register` — validation client-side, auto-login sau đăng ký, layout tập trung.
- Dashboard (`AppShell` = Sidebar + Header): `/news` (+ `/[id]`), `/companies` (+ `/[id]`), `/trade`, `/trade/mentor`, `/social`.
- `/social` — danh sách bài đăng MXH, lọc theo persona + tag, skeleton loading, empty state, badge tag.
- `layout.tsx` root + `globals.css`.

### Components (62 file .ts/.tsx/.css trong `src/`)
- **common/**: AuthProvider, Badge, Button, Card, EmptyState, ErrorPanel, Field, Icon, PageHeader, Skeleton, Spinner.
- **layout/**: AppShell, Header, Sidebar, UserMenu.
- **news/**: NewsCard, NewsFilter, NewsList.
- **companies/**: CompanyCard, CompanyFilter, CompanyList.
- **trade/**: TradePanel (đặt lệnh mua/bán, market/limit, kiểm tra tiền mặt), PortfolioTable (PnL client-side), OrderTable.
- **mentor/**: MentorChat (streaming, suggestion chips, badge trạng thái).
- **social/**: SocialPostCard (persona, sentiment, virality) + `page.tsx` hoàn thiện.

### Hooks
- `useWebSocket.ts` — reconnect backoff + jitter, heartbeat 30s, dùng retry khi close code 1008, parse envelope.
- `useTrade.ts` — REST + WS `/ws/trades` (re-fetch khi nhận `trade_fill`/`order_update`).
- `useSocraticMentor.ts` — lấy WS ticket + send ask/cancel mentor.
- `useKnowledge.ts` — match kiến thức (backend + fallback local).

### Services / Store
- services: `api` (base), `auth`, `news`, `companies`, `trade`, `mentor`, `social`.
- store (Zustand): `useAuthStore`, `useNewsStore`, `useTradeStore`, `useMentorStore`.

### Types / Utils
- `types/api.ts`, `types/websocket.ts` (discriminated-union: price_tick, trade_fill, order_update, mentor_*, feed_status, welcome, error + close codes).
- `utils/format.ts` (VND/number/date + parseDecimal), `utils/domain.ts` (nhận diện tiếng Việt), `utils/pnl.ts`, `utils/knowledge_matcher.ts` (10 khái niệm, không dấu), `utils/cn.ts`.

### Kiểm thử
- `npm run typecheck` (tsc --noEmit): đạt.

### Việc cần thiếu
- Heatmap MXH (mỗi danh sách + filter, chưa có heatmap).
- Knowledge base: mỗi gợi ý trên trang tin chi tiết, chưa thêm 3 điểm chú thích (companies/trade).

### Trạng thái
Đang triển khai (phần lớn hoàn thành, chưa commit).

---

## Giai đoạn 5 — Chưa bắt đầu

*(Chưa thực hiện.)*