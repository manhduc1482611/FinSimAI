# Báo cáo Nghiệm thu — Giai đoạn 2A: WebSocket Real-time Layer

**Dự án**: FinSim AI
**Vai trò**: Lead Software Architect & Technical Auditor
**Ngày**: 2026-07-31
**Phạm vi**: Bước 2.2 — `apps/backend_gateway/websockets/` (giá real-time, khớp lệnh, Mentor streaming)

---

## 1. Báo cáo Tổng kết Công việc (Stage 2A Completion Report)

### Mã nguồn WebSocket

| File | Dòng | Trách nhiệm | Trạng thái |
|---|---|---|---|
| `websockets/connection_manager.py` | 661 | Core: quản lý kết nối, room pub/sub, heartbeat keepalive, revalidation giữa phiên (bọc on_validate/on_connect chống DB chập chờn), dọn dẹp disconnect, HAI queue outbound (best-effort drop-oldest + reliable không-drop tràn→1011), `feed_status`/`realtime_status`, backplane hooks, writer send timeout (chống Slowloris), `shutdown_connections` đóng mọi WS bằng 1012 (graceful shutdown) | ✅ |
| `websockets/price_ws.py` | 440 | `PriceBroadcaster` — tick giá 2s theo time compression, O/H/L phiên, leader election fail-closed + snapshot cache Redis, snapshot RAM TTL ngắn cho worker phụ, re-check `is_leader()` trước broadcast (lock hết hạn khi đọc DB → bỏ tick trùng) | ✅ |
| `websockets/trade_ws.py` | 514 | `TradeNotifier` — push `trade_fill`/`order_update` tới `user:{id}` QUA KÊNH RELIABLE (không drop), claim-first (SETNX trước broadcast, chống trùng push/poll), leader-locked poll watermark + lookback window 5s + watermark vượt cả batch, watermark trên Redis, `seq` tăng dần theo kênh user (INCR pipeline) | ✅ |
| `websockets/mentor_ws.py` | 279 | Mentor streaming chunk (`mentor_start/chunk/end/error/cancelled`), kiểm tra `send()` + hủy task non-blocking | ✅ |
| `websockets/auth.py` | 257 | Single-use ticket (thay JWT `?token=`): `POST /auth/ws-ticket` cấp ticket TTL ngắn, handshake `?ticket=` tiêu thụ nguyên tử `GETDEL` (Redis) / RAM pop (`ws_local_mode`), fail-closed khi Redis hỏng (1008) + `revalidate_user(user_id)` TTL-cache LRU + bắt riêng lỗi DB (giữ phiên, không đóng loạt) + user cache 30s khi bắt tay (chống Herd Postgres khi reconnect) + lỗi DB handshake → 1008 sạch | ✅ |
| `websockets/leader.py` | 85 | `LeaderElection` fail-closed — lock Redis nguyên tố bằng Lua (GET==token mới được gia hạn) + **fencing token** tăng dần theo nhiệm kỳ (Redis INCR trên counter riêng, `acquire()` trả về token, receiver bác token thấp hơn đã thấy — chống split-brain tạm thời khi leader bị pause) | ✅ |
| `websockets/backplane.py` | 416 | Relay multi-worker qua Redis Pub/Sub, dynamic subscription (lock serialize sub/unsub + đọc lại count thực), self-broadcast + skip echo, `_activate_pubsub` không rò handle khi reconnect, envelope QoS (`reliable`/`best_effort`), trạng thái `feed_status` (degraded/live) + `RESYNC_HINTS` | ✅ |
| `websockets/simtime.py` | 47 | Mirror `engine.time_compression.compressor` (ratio 1440) — tránh coupling chéo workspace | ✅ |
| `websockets/router.py` | 88 | Đăng ký 3 route + start/stop background tasks + attach/detach backplane + shutdown 1012 trước khi stop broadcaster | ✅ |
| `websockets/__init__.py` | 24 | Re-export + ghi chú kiến trúc `wsproto` | ✅ |

### Tích hợp & Cấu hình

| File | Thay đổi | Trạng thái |
|---|---|---|
| `main.py` | `register_websocket_routes(app)`, lifespan start/stop background, uvicorn `ws="wsproto"` | ✅ |
| `core/config.py` | `ws_price_tick_seconds=2.0`, `ws_trade_poll_seconds=1.0`, `ws_heartbeat_seconds=30.0`, `ws_max_queue_size=256`, `ws_local_mode=false`, `ws_revalidate_cache_ttl_seconds=60.0`, `ws_snapshot_local_cache_ttl_seconds=1.0`, `ws_write_timeout_seconds=10.0`, `ws_ticket_ttl_seconds=15.0`, `ws_sim_anchor_epoch=1767225600.0` | ✅ |
| `core/cache.py` | `get_cache()` async Redis client, `socket_connect_timeout=1.0` (không treo khi Redis mất kết nối) | ✅ |
| `Makefile` | `dev-backend` chạy `WS_LOCAL_MODE=true` (1 worker dev) + uvicorn `--ws wsproto` | ✅ |
| `tests/conftest.py` | Fixture autouse: Redis "không khả dụng" + `ws_local_mode=true` — bộ test không phụ thuộc Redis thật | ✅ |
| `models/trade.py` | Composite index `idx_transactions_watermark (created_at, id)` cho poll watermark | ✅ |
| `packages/database/migrations/versions/0002_ws_perf_indexes.py` | Migration thêm composite index watermark (bản đồng bộ cho DB đã có) | ✅ |
| `pyproject.toml` | `wsproto>=1.2.0,<2.0`, `email-validator`, `protobuf>=7.35.1`; dev group: pytest, pytest-asyncio, httpx, grpcio-tools | ✅ |
| `Makefile` | `dev-backend` chạy uvicorn `--ws wsproto` | ✅ |
| `clients/proto/*.pb2*` | Regenerate từ `packages/proto/math_engine.proto` (bản cũ hỏng descriptor) + patch relative import | ✅ |

### Unit Tests (bộ test mới — `tests/`)

| File | Tests | Trạng thái |
|---|---|---|
| `test_connection_manager.py` | 18 | ✅ |
| `test_price_ws.py` | 9 | ✅ |
| `test_trade_ws.py` | 20 | ✅ |
| `test_mentor_ws.py` | 4 | ✅ |
| `test_auth.py` | 15 | ✅ |
| `test_simtime.py` | 7 | ✅ |
| `test_backplane.py` | 15 | ✅ |
| `test_leader.py` | 7 | ✅ |
| **Tổng** | **95** | **✅ 95/95 pass** |

`ruff check` trên `websockets/` + `tests/` + `core/config.py` + `core/cache.py` + `models/`: **✅ All checks passed**.

*Hồi tố Giai đoạn 2A+ (production hardening, 2026-07-31): bộ test tăng 44 → 58, bổ sung
`test_leader.py` (fail-closed), `test_backplane.py` mở rộng (self-broadcast + reconnect),
`test_auth.py` mở rộng (TTL cache revalidation), price/trade takeover-state test.
Chạy `uv run pytest tests -q` → `58 passed in ~4s`.*

*Hồi tố Giai đoạn 2A+ vòng 3 (hiệu năng & an toàn ở quy mô lớn, 2026-07-31): test 58 → 66.
Bổ sung: Lua lock atomic (`test_leader`), dynamic subscription (`test_backplane`),
Redis pipeline batching (`test_trade_ws`), writer send timeout (`test_connection_manager`),
LRU eviction auth cache (`test_auth`), snapshot RAM cache worker phụ (`test_price_ws`).
Chạy `uv run pytest tests -q` → `66 passed in ~3s`.*

*Hồi tố Giai đoạn 2A+ vòng 4 (phản biện hiệu năng/an toàn, 2026-07-31): test 66 → 75.
Bổ sung: revalidation giữ phiên khi DB chập chờn (`test_auth`, `test_connection_manager`),
claim-first chống trùng push/poll (`test_trade_ws`), lock serialize sub/unsub +
đóng pubsub cũ khi reconnect (`test_backplane`). Chạy `uv run pytest tests -q` → `75 passed in ~4s`.*

*Hồi tố Giai đoạn 2A+ vòng 5 (an toàn xác thực WS + QoS + degraded mode, 2026-07-31): test 75 → 85.
Bổ sung: single-use ticket thay JWT `?token=` (`test_auth` viết lại theo ticket + single-use/expiry),
QoS 2 queue — reliable ưu tiên trước + tràn → đóng 1011 (`test_connection_manager`),
`feed_status` degraded/live chỉ phát khi đổi trạng thái + envelope `qos=reliable`
(`test_backplane`). Chạy `uv run pytest tests -q` → `85 passed in ~5s`.*

*Hồi tố Giai đoạn 2A+ vòng 6 (5 nghẽn production từ phản biện, 2026-07-31): test 85 → 93.
Vá toàn bộ 5 điểm — watermark lookback, `seq` per-channel, shutdown 1012, re-check leader
trước broadcast, SETNX namespaced + TTL. Xem phần "Kết luận" để biết chi tiết từng hạng mục.
Chạy `uv run pytest tests -q` → `93 passed in ~4s`.*

*Hồi tố Giai đoạn 2A+ vòng 7 (đối chiếu 4 điểm vận hành thực tế, 2026-07-31): test 93 → 95.
Phản biện: (1) Pub/Sub fire-and-forget mất tin khớp lệnh → xác nhận ĐÚNG, triển khai Redis
Streams để Giai đoạn 3 (xem "Việc còn lại"); (2) split-brain tạm thời khi leader bị pause →
vá NGAY bằng **fencing token** (mã nhiệm kỳ tăng dần, Lua `INCR` counter riêng, `acquire()`
trả về token — receiver chỉ chấp nhận token cao hơn); (3) SimTime 1:1440 quá nhạy với timer
trễ → xác nhận mã ĐÃ tính tuyệt đối `max((now-anchor), 0) × ratio`, chỉ bổ sung test chống
hồi quy (không dùng timer cộng dồn); (4) bão reconnect khi tràn reliable queue (1011) → ghi
nhận client-side contract (backoff + jitter cho 1011/1012) cho Giai đoạn 3. Chạy
`uv run pytest tests -q` → `95 passed in ~4s`.*

---

## 2. Rà soát Kiến trúc & Coupling

### 2.1. Kiến trúc và giao thức

```
Client ──WebSocket──► /ws/prices  price_ws.create_price_endpoint
                     /ws/trades   trade_ws.create_trade_endpoint   (single-use ticket bắt buộc)
                     /ws/mentor   mentor_ws.create_mentor_endpoint (single-use ticket bắt buộc)
                              │
                              ▼
              connection_manager.ConnectionManager
              └─ rooms: "prices:SYMBOL", "prices:*", "user:{user_id}"
               └─ per-connection HAI queue + writer task: best-effort (tick) drop-oldest,
               │    reliable (trade fill) KHÔNG drop — tràn → đóng 1011 để client resync
               └─ keepalive ping — KHÔNG kick client passive; chỉ writer/transport chết mới đóng
               └─ revalidate user mỗi chu kỳ heartbeat (TTL-cache, không query DB mỗi nhịp)
              │
              ▼
              backplane.Backplane  ──Redis Pub/Sub──►  worker khác (chỉ room có client local)
              └─ DYNAMIC subscription: subscribe đúng channel `finsim:ws:<room>` khi room
              │   có ≥1 client local (qua hook on_room_changed) — KHÔNG pattern "finsim:ws:*"
              │   để 9/10 worker không phải giải mã tick của room mà mình không có client
               └─ worker phát broadcast local NGAY + publish envelope {room,payload,sender,qos}
               └─ subscriber bỏ qua message của chính mình (sender) → không trùng
               └─ Redis hỏng → local-only + task nền dò lại (exponential backoff), tự phục hồi
               └─ mất Redis → `feed_status` degraded + `resync_via` REST; khôi phục → live

Leader election fail-closed (Redis lock nguyên tố bằng Lua): "finsim:ws:leader:price"/":trade"
  └─ GET(key)==token mới được gia hạn — leader hết TTL bị thay KHÔNG thể đè token đối thủ
  └─ chỉ leader đọc DB mỗi chu kỳ; leader chết → lock hết TTL → worker khác tiếp quản
  └─ MẤT Redis → KHÔNG worker nào tự xưng leader (chống split-brain N× DB + trùng tin)
  └─ Fencing token: mỗi nhiệm kỳ leader nhận mã số tăng dần (Lua INCR counter riêng);
  │    broadcast mang token, receiver bác token ≤ đã thấy → chặn split-brain tạm thời
  │    khi leader cũ bị pause (GC) lâu hơn TTL rồi tỉnh dậy phát nốt tin đang dở
  └─ 1 instance (ws_local_mode=true) → luôn leader, không đụng Redis
  └─ Failover kế thừa state: price session (snapshot cache) + trade watermark (Redis key)
```

- **Envelope chuẩn**: `{"type": ..., "data": {...}, "ts": ISO8601-UTC}` qua `build_message()`.
- **Multi-worker + dynamic subscription**: `broadcast_to_room`/`broadcast_to_user` (và bản
  `*_reliable`) serialize JSON 1 lần rồi gọi Backplane: broadcast local NGAY cho client của
  worker phát + publish envelope `{room, payload, sender, qos}` lên `finsim:ws:<room>`. Worker
  CHỈ subscribe channel của room đang có ≥1 client local (`on_room_changed` hook từ manager;
  start/reconnect đồng bộ lại từ `rooms_with_clients()`). Không dùng `psubscribe("finsim:ws:*")`
  — với 10 worker × 5.000 room, một tick `prices:ACB` sẽ bắt 9 worker không có client ACB phải
  giải mã JSON + gọi broadcast mỗi lần; dynamic subscription cắt bỏ toàn bộ chi phí vô ích đó.
  Subscriber bỏ qua tin do chính mình phát (`sender`) → mỗi worker nhận đúng 1 bản, không trùng.
- **Recovery backplane**: Redis hỏng → local-only + task nền dò lại (`ping` + re-subscribe các
  room đang có client) theo exponential backoff (1s→30s); Redis quay lại → tự phục hồi,
  không cần restart.
- **Leader election fail-closed + Lua atomic + fencing token**: `LeaderElection` giành/gia hạn lock bằng một
  script Lua duy nhất — chỉ `pexpire` khi `GET(key) == token`. Lỗi kinh điển bị vá: `SET XX EX`
  chỉ kiểm tra key TỒN TẠI, nên leader A bị treo quá TTL (GC/CPU), B giành lock, A tỉnh dậy
  `SET XX` sẽ GHI ĐÈ token B → hai worker cùng tưởng mình là leader. Lua chặn đúng kịch bản
  đó. **Vòng 7 bổ sung fencing token**: cùng script Lua, khi giành chủ mới `INCR` một counter
  riêng (`finsim:ws:leader:price:fence`) và trả về mã nhiệm kỳ — gia hạn giữ nguyên token, chuyển
  giao sang nhiệm kỳ mới nhận token CAO HƠN. Mọi broadcast phải mang token; receiver chỉ nhận
  token cao hơn token đã thấy → chặn "split-brain tạm thời": leader A bị pause lâu hơn TTL, B tiếp
  quản (token cao), A tỉnh dậy giữa chừng phát nốt tick đang dở bằng token thấp — receiver bác
  tin đó. `acquire()` giờ trả về fencing token (`0` = không phải leader). Mất Redis → worker KHÔNG
  tự xưng leader (fail-closed). `ws_local_mode=true` (chạy đúng 1 instance/dev/test) → luôn leader
  (token cục bộ), không đụng Redis.
- **Failover kế thừa state**: price session (open/high/low/prev_close/sim_day) tái tạo từ
  snapshot cache Redis; trade watermark lưu key `finsim:ws:trade:watermark` → leader mới
  không reset phiên giá, không quét lại bảng transactions từ đầu (dedupe SETNX vẫn là
  lưới an toàn thứ hai).
- **Redis batching (không N round-trip)**: dedupe SETNX + exists-check + watermark của
  TradeNotifier gom qua `pipeline()` — 500 giao dịch khớp lệnh cùng lúc = 1 round-trip,
  không phải 1.500. Poll watermark được hỗ trợ bởi composite index
  `idx_transactions_watermark (created_at, id)` (model + migration 0002) — không Seq Scan +
  Sort toàn bộ bảng mỗi 1–3s.
- **Writer send timeout (chống Slowloris)**: `asyncio.wait_for(send_text, timeout=10s)` —
  client mạng yếu/cố tình ngắt ACK (TCP zero-window) bị đóng sau 10s thay vì writer treo
  vô hạn thành zombie giữ RAM.
- **QoS 2 queue (tách drop-oldest khỏi tin giao dịch)**: mỗi kết nối có `queue` best-effort
  (tick giá, snapshot, control — drop-oldest khi client đọc chậm) và `reliable_queue` (trade
  fill / order update / notification — KHÔNG drop). `_next_payload` ưu tiên reliable và chờ
  đồng thời cả hai queue (không bao giờ làm rơi tin). Reliable đầy → đóng kết nối code 1011
  `"reliable queue overflow — reconnect to resync"` để client reconnect + resync qua REST:
  mất kết nối còn hơn "mất tin giao dịch thầm lặng". Envelope Redis mang `qos` để worker khác
  relay đúng kênh.
- **Single-use ticket (không JWT trong URL)**: JWT cũ truyền qua `?token=` sẽ nằm nguyên trong
  URL → rò rỉ vào access log / APM trace / browser history. Thay bằng: REST `POST
  /api/v1/auth/ws-ticket` (JWT qua header `Authorization`) trả `{ticket, ttl_seconds,
  expires_at}`; handshake dùng `?ticket=<ticket>`; server tiêu thụ nguyên tử `GETDEL` (Redis)
  / `pop` (RAM khi `ws_local_mode`) — dùng đúng 1 lần, TTL mặc định 15s. Thiếu/sai/hết hạn/
  tái dùng ticket → đóng 1008; Redis hỏng → fail-closed (từ chối) vì không thể xác minh.
- **Degraded mode khi mất Redis (SPOF của lớp realtime)**: mất cầu nối Redis → leader election
  fail-closed làm feed đóng băng 5-10s mà client không hay biết. Backplane giờ phát `feed_status`
  tới MỌI kết nối local (không qua Redis — không thể dựa vào Redis để lan truyền tín hiệu mất
  Redis) chỉ khi trạng thái THAY ĐỔI (degraded/live, không spam), kèm `resync_via` các endpoint
  REST thay thế (`/api/v1/companies`, `/api/v1/trades/orders`, `/api/v1/trades/portfolio`).
  Welcome frame mới nhúng `realtime_status` để client vừa mở socket biết ngay nên resync.
- **Auth cache LRU (tránh Thundering Herd)**: cache revalidation theo `user_id` là
  `OrderedDict`; khi vượt 20k entry chỉ đá entry cũ nhất (LRU) + entry hết hạn — KHÔNG
  `clear()` toàn bộ (xả sạch khiến hàng chục nghìn kết nối cùng query Postgres ở nhịp
  heartbeat kế tiếp).
- **Price snapshot RAM cache ở worker phụ**: worker không phải leader nạp snapshot từ Redis
  `HGETALL` 1 lần, giữ RAM `ws_snapshot_local_cache_ttl_seconds=1s` — 1.000 client kết nối mới
  trong cùng giây → 1 lệnh HGETALL thay vì 1.000.
- **Revalidation an toàn khi DB chập chờn**: `revalidate_user`/`_load_active_user` chỉ trả
  False/throw `WebSocketException` khi user xóa/bị khóa; lỗi DB (timeout, pool cạn, asyncpg
  restart) được bắt riêng → trả True GIỮ kết nối và thử lại nhịp heartbeat sau, KHÔNG cache
  kết quả. `handle_connection` cũng bọc `on_validate` trong try/except (defense-in-depth).
  Trước khi vá: một đợt Postgres chập chờn 1-2s làm TOÀN BỘ client tới chu kỳ revalidate bị
  đóng socket đồng loạt.
- **Trade push claim-first (chống trùng push/poll)**: `_push_transactions` giành quyền phát
  bằng SETNX (pipeline 1 round-trip) TRƯỚC khi broadcast; giao dịch claim thất bại (đã delivered)
  không được gửi. Cách cũ broadcast-tồi-mark mở cửa sổ race: poll SELECT DB đúng lúc giữa send
  và SETNX → đẩy trùng `trade_fill`. `_poll_once` đồng thời luôn đẩy watermark vượt qua cả batch
  đã đọc (kể cả tin đã delivered) — không lặp lại vĩnh viễn một tin cuối bảng.
- **Subscribe/unsubscribe serialize bằng lock**: `on_room_changed` khóa `_sub_lock` quanh
  check→`await`→update và quyết định dựa trên SỐ CLIENT THỰC đọc lại từ manager (không tin
  tham số `count` của sự kiện cũ). Join/leave đan xen tốc độ cao không thể làm room "lệch trạng
  thái" (subscribe mà đã rỗng, hay để lọt subscribe cho room mới có client).
- **Không rò handle PubSub khi reconnect**: `_activate_pubsub` dừng listener cũ + `aclose()`
  pubsub cũ trước khi cài pubsub mới. Trước khi vá: (1) pubsub cũ bị gán đè không đóng → tích
  tụ handle trong event loop khi mạng chập chờn; (2) publish lỗi nhưng listener cũ còn sống →
  sau reconnect có HAI listener cùng relay → message trùng tới client.
- **Heartbeat + revalidation**: server gửi keepalive ping định kỳ; client passive KHÔNG bị
  kick — chỉ transport/writer lỗi mới đóng. User còn active được kiểm tra lại mỗi chu kỳ
  (đóng 1008 khi tài khoản bị khóa); kết quả cache theo `user_id` TTL 60s để 10k client
  không tạo 333 query/s lên Postgres.
- **Price**: client gửi `{"action":"subscribe"|"unsubscribe","channels":["prices:ACB","prices:*"]}`; server trả `price_tick` khi giá đổi, `price_snapshot` khi subscribe/`snapshot`.
- **Trades**: phòng cá nhân `user:{user_id}`; nhận `trade_fill` ngay khi khớp lệnh (event-driven qua
  `notify_transactions`); task nền của leader poll `transactions` theo watermark để bù phát — hai
  đường này được khử trùng bằng Redis `SETNX` `finsim:ws:tx:<id>` (gom pipeline) + deque `_seen_ids`.
- **Mentor**: `{"action":"ask","message":...,"session_id":...}` → `mentor_start` → nhiều `mentor_chunk` → `mentor_end`; `cancel`/disconnect hủy task đang chạy; server kiểm tra kết quả `send()` và dừng stream ngay khi kết nối đứt.

### 2.2. Điểm kiến trúc then chốt — package `websockets` trùng tên thư viện pip

Package local `apps/backend_gateway/websockets/` che (shadow) thư viện pip `websockets` mà
uvicorn dùng cho WS server. **Đã xác minh bằng thực nghiệm**: chạy uvicorn mặc định crash với
`ModuleNotFoundError: No module named 'websockets.legacy'`. Giải pháp bắt buộc — uvicorn phải
chạy `--ws wsproto` (áp dụng tại `Makefile` và `main.py`). `Starlette TestClient` dùng WebSocket
session thuần ASGI nên không bị ảnh hưởng — toàn bộ test bên dưới chạy an toàn.

Smoke test uvicorn (xác nhận import chain + wsproto):
```powershell
$env:JWT_SECRET="smoke"
$env:DATABASE_URL="postgresql+asyncpg://x:x@localhost:5432/x"
uv run python -c "from uvicorn.config import Config; c = Config('main:app', ws='wsproto'); c.load(); print(c.ws_protocol_class.__module__)"
# → uvicorn.protocols.websockets.wsproto_impl
```

### 2.3. SOLID & Coupling

| Nguyên tắc | Đánh giá |
|---|---|
| **S** | ✅ `ConnectionManager` (vận chuyển), `PriceBroadcaster` (giá), `TradeNotifier` (khớp lệnh), `auth` (xác thực), `simtime` (thời gian) — mỗi module một việc |
| **O** | ✅ Các endpoint là factory (`create_*_endpoint`) nhận DI: manager/broadcaster/notifier/provider/auth → mở rộng/test mà không sửa lõi |
| **L** | ✅ `MentorStreamProvider` là Protocol — `StaticMentorStream` (placeholder) thay bằng AI streaming ở Giai đoạn 3, không đổi giao thức WS |
| **I** | ✅ `PollSource`/`SymbolResolver`/`PriceSource` là interface nhỏ gọn, đúng nhu cầu |
| **D** | ✅ Endpoint + component nhận phụ thuộc qua constructor; singletons chỉ là default |

**Phụ thuộc vòng**: ✅ Không có. Đồ thị import là DAG thuần:

```
router.py → connection_manager.py
          → price_ws.py → auth.py / simtime.py
          → trade_ws.py → auth.py
          → mentor_ws.py → auth.py
```
Không module nào import `router.py` ngược lại. `websockets/` không import `services/` hay `clients/`.

---

## 3. Kịch bản nghiệm thu (Acceptance Test Script)

### 3.1. Chạy bộ test tự động

```powershell
cd apps/backend_gateway
uv run pytest tests -v
```

**Kết quả kỳ vọng**: `95 passed`. Các kịch bản phủ:

| Kịch bản | Hàm test |
|---|---|
| Kết nối → welcome, subscribe → snapshot + ack, nhận `price_tick` khi giá đổi | `test_price_ws_endpoint_full_flow` |
| Unsubscribe → không còn nhận tick; action lạ → `error.unknown_action`; channel sai → `error.invalid_channels` | `test_price_ws_endpoint_full_flow` |
| Phiên O/H/L theo dõi, sang sim day mới reset session | `test_session_high_low_track`, `test_sim_day_rollover_resets_session` |
| Trade: kết nối có ticket hợp lệ → welcome `user:42` → nhận `trade_fill` từ nguồn poll | `test_trade_ws_endpoint_streams_fills` |
| Trade không có ticket → bắt tay bị từ chối 1008 | `test_trade_ws_endpoint_rejects_unauthenticated` |
| Trade: poll dedupe theo `transaction_id` + watermark tiến | `test_poll_once_delivers_and_dedupes` |
| Mentor: ask → start → chunk → end; message trống → `error.invalid_message` | `test_mentor_ws_endpoint_streams_answer`, `test_mentor_ws_endpoint_rejects_empty_message` |
| Mentor: cancel giữa chừng → `mentor_cancelled`, kết nối vẫn sống (ping→pong) | `test_mentor_ws_endpoint_cancel` |
| Ngắt kết nối đột ngột → cleanup rooms + cancel task đang chạy | `test_connect_disconnect_cleanup`, `test_on_connect_and_on_disconnect_hooks` |
| Client đọc chậm → drop-oldest best-effort, không chặn server | `test_drop_oldest_when_consumer_slow` |
| Tin reliable ưu tiên trước tin best-effort khi cả hai xếp hàng | `test_reliable_message_prioritized_over_best_effort` |
| Reliable queue đầy → đóng kết nối 1011 (không drop tin giao dịch) để client resync | `test_reliable_overflow_closes_connection_with_1011` |
| Mất Redis → `feed_status` degraded + `resync_via`; khôi phục → live (chỉ phát khi đổi trạng thái) | `test_feed_status_broadcast_only_on_state_change`, `test_reconnect_loop_recovers_when_redis_returns` |
| Welcome nhúng `realtime_status` (live/degraded) cho client mới | `test_welcome_includes_realtime_status`, `test_realtime_status_reflects_backplane_status` |
| Envelope Redis mang `qos=reliable` cho trade fill → relay qua kênh reliable | `test_publish_room_reliable_marks_envelope_qos`, `test_listener_relays_reliable_message_via_reliable_channel` |
| Heartbeat: client im lặng → server ping keepalive, KHÔNG bị kick; kết nối vẫn sống | `test_handle_connection_keepalive_ping_on_silence_does_not_kick` |
| Revalidation: token hết hạn giữa phiên → đóng 1008 + dọn dẹp | `test_handle_connection_revalidates_periodically_and_closes` |
| Writer chết (socket đóng đột ngột) → cleanup kết nối sạch, không rò rỉ task | `test_writer_failure_cleans_up_connection` |
| Lỗi handler → `error.internal_error` (kết nối không đứt) | `test_handle_connection_internal_error_reports_but_keeps_open` |
| Backplane: publish → Redis channel đúng room/user; fallback local-only khi Redis hỏng | `test_backplane.py` (4 test) |
| Ticket hợp lệ → vào; thiếu/sai/hết hạn/tái dùng ticket, user không tồn tại/inactive → 1008 | `test_auth.py` (13 test) |

### 3.2. Kiểm tra thủ công với uvicorn thật (cần Postgres chạy)

> `main.py` lifespan bắt buộc kiểm tra DB (`_check_database`) trước khi boot. Khởi động
> Postgres + Redis bằng `docker compose up -d db redis` (hoặc instance cục bộ), tạo `.env`
> từ `.env.example`, chạy migration + seed, rồi:

```powershell
cd apps/backend_gateway
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --ws wsproto
```

Dùng trình duyệt/CLI WebSocket (đảm bảo client dùng thư viện WS độc lập, không import từ
package local):

1. **Prices** — `ws://localhost:8000/ws/prices`
   - Gửi `{"action":"subscribe","channels":["prices:*"]}` → nhận ack + `price_snapshot`, sau đó
     `price_tick` mỗi khi giá đổi (tick chu kỳ 2s).
   - Đóng socket đột ngột → server log `WS disconnected`, không có lỗi crash.
2. **Trades** — `ws://localhost:8000/ws/trades?ticket=<ticket>`
   - Cấp ticket: `POST /api/v1/auth/ws-ticket` với header `Authorization: Bearer <JWT>` →
     `{ticket, ttl_seconds, expires_at}` (single-use, TTL ~15s — chỉ dùng 1 lần, không để
     JWT nằm trong URL).
   - Gửi `{"action":"subscribe"}` → welcome chứa `user:{id}` + `realtime_status`; đặt lệnh qua
     REST `/api/v1/trades/orders` → nhận `trade_fill` ngay khi khớp (đi qua kênh reliable).
   - Không truyền ticket / ticket đã dùng → kết nối bị từ chối (code 1008).
3. **Mentor** — `ws://localhost:8000/ws/mentor?ticket=<ticket>`
   - Gửi `{"action":"ask","session_id":"s1","message":"Nên mua ACB không?"}` → nhận `mentor_start`,
     nhiều `mentor_chunk`, `mentor_end`; gửi `cancel` giữa chừng → `mentor_cancelled`.

---

## 4. Phân tích Điểm mù & Giới hạn đã biết

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Boot uvicorn thật + kết nối thực | 🟡 Chưa chạy trên máy hiện tại | Không có Docker/Postgres/Redis local. Đã xác minh: `Config('main:app', ws='wsproto').load()` OK + TestClient end-to-end trên 3 endpoint; backplane/leader election được test qua mock Redis (fixture autouse) |
| `Company.is_active`, `Company.updated_at`, `User.is_active`, cột `Transaction` | ✅ Đã xác minh | Tồn tại trong `models/company.py`, `models/user.py`, `models/trade.py` |
| `default_price_source` / `_default_poll_source` (DB thật) | 🟡 Chỉ test gián tiếp | Test dùng fake sources; cần DB thật để smoke (mục 3.2) |
| `trade_notifier` poll nối DB khi client online | ✅ Logic đã test | Dedupe + watermark qua fake poll_source |
| Mentor placeholder | 🟢 Theo kế hoạch | `StaticMentorStream` rule-based; Giai đoạn 3 thay bằng AI Engine qua `MentorStreamProvider` |
| Secret JWT test ngắn | ✅ Đã xử lý | `conftest.py` đặt secret >= 32 bytes, hết cảnh báo |
| `protobuf` runtime/`email-validator`/proto regen | ✅ Đã sửa | Blocker tiền đề từ Giai đoạn 1 được xử lý để gateway import được |

---

## 5. Bảng Checklist Nghiệm thu

| Tiêu chí | Đạt |
|---|---|
| Broadcast giá real-time theo time compression (tick, O/H/L, sim day) | ✅ |
| Kênh khớp lệnh theo người dùng (`user:{user_id}`) + bù phát khi offline | ✅ |
| Mentor streaming chunk + cancel giữa chừng + hủy khi disconnect | ✅ |
| Single-use ticket bắt buộc cho trades/mentor (`POST /auth/ws-ticket` → `?ticket=`, tiêu thụ nguyên tử GETDEL), từ chối 1008 — JWT không vào URL | ✅ |
| Revalidation giữa phiên: TTL-cache theo `user_id` LRU — không query DB mỗi nhịp | ✅ |
| Heartbeat keepalive không kick client passive (chỉ transport chết mới đóng) | ✅ |
| Multi-worker: backplane dynamic subscription (chỉ subscribe room có client local) | ✅ |
| Reconnect loop: Redis quay lại → backplane tự phục hồi (exponential backoff, không restart) | ✅ |
| Leader election fail-closed + Lua atomic: gia hạn chỉ khi `GET(key)==token` (chống split-brain) | ✅ |
| Fencing token: mã nhiệm kỳ tăng dần (Lua INCR counter riêng), `acquire()` trả về token, receiver bác token ≤ đã thấy — chống split-brain tạm thời khi leader bị pause | ✅ |
| SimTime tính tuyệt đối `max((now-anchor), 0) × ratio` (không tích lũy theo số lần gọi — trễ tick không tích lũy sai số ở tỉ lệ 1:1440) | ✅ |
| Failover kế thừa state: price session từ snapshot cache + trade watermark trên Redis | ✅ |
| Redis batching: dedupe SETNX + watermark gom pipeline (1 round-trip/batch) | ✅ |
| Composite index `idx_transactions_watermark (created_at, id)` cho poll watermark (model + migration 0002) | ✅ |
| Writer send timeout 10s: Slowloris/TCP zero-window bị đóng, không zombie giữ RAM | ✅ |
| Auth cache LRU eviction (không clear toàn bộ — tránh Thundering Herd Postgres) | ✅ |
| Revalidation an toàn khi DB chập chờn: lỗi DB → giữ kết nối, thử lại nhịp sau (không đóng loạt) | ✅ |
| Trade push claim-first: SETNX trước broadcast (chống race trùng tin với poll catch-up) | ✅ |
| Subscribe/unsubscribe serialize bằng lock + đọc lại số client thực (không lệch trạng thái room) | ✅ |
| Reconnect không rò handle PubSub: dừng listener cũ + aclose() pubsub cũ trước khi cài mới | ✅ |
| Price worker phụ: snapshot RAM cache TTL 1s (1 HGETALL/giây, không 1.000) | ✅ |
| Dedupe giữa push event-driven và poll catch-up (Redis SETNX + watermark) | ✅ |
| Backpressure: HAI queue bounded — best-effort drop-oldest không chặn broadcast; reliable (trade fill) không drop, tràn → đóng 1011 để resync | ✅ |
| Degraded mode: mất Redis → `feed_status` degraded + `resync_via` REST (broadcast local, chỉ phát khi đổi trạng thái); welcome nhúng `realtime_status` | ✅ |
| Watermark poll có Lookback Window (`created_at >= watermark − 5s`): không bỏ sót giao dịch "commit lệch thời gian" (Postgres `now()` = thời điểm START tx) | ✅ |
| Mỗi tin `trade_fill`/`order_update` gắn `seq` tăng dần THEO KÊNH user (Redis INCR, pipeline) — client dò gap (1 → 3) để phát hiện mất tin và resync REST | ✅ |
| Graceful shutdown đóng mọi WS bằng Close Code **1012** (Service Restart) trong `stop_ws_background` — client reconnect có backoff + jitter, chống Thundering Herd khi rolling deploy | ✅ |
| Leader re-check `is_leader()` ngay trước broadcast (price): lock hết hạn trong lúc đọc DB → leader khác thay thế → KHÔNG đẩy tick trùng (split-brain ngắn) | ✅ |
| User cache khi bắt tay WS (TTL 30s, LRU): N client reconnect cùng lúc → 1 SELECT/user, chống Herd Postgres; lỗi DB lúc handshake → 1008 sạch (client retry backoff) | ✅ |
| Dedupe SETNX: prefix namespaced `finsim:ws:dedup:trade:{id}` + `ex=300` cố định (không rò RAM Redis) | ✅ |
| Kết nối được đăng ký trong `main.py` + background task start/stop qua lifespan | ✅ |
| Uvicorn chạy `--ws wsproto` (tránh xung đột package `websockets`) | ✅ |
| Test tự động 95/95 pass + `ruff` sạch | ✅ |
| Không phụ thuộc vòng; DI cho endpoint/component | ✅ |

### Tổng hợp

| Hạng mục | OK | Cần cải thiện |
|---|---|---|
| Mã nguồn WebSocket | 10/10 | — |
| Tích hợp & Cấu hình | 9/9 | — |
| Unit Tests | 95/95 | — |
| Kiến trúc (SOLID/coupling/wsproto) | 4/4 | — |
| **Tổng** | **118/118** | — |

---

## 6. Kết luận

### Verdict: ✅ **Nghiệm thu đạt — sẵn sàng chuyển sang Giai đoạn 3**

- Toàn bộ mã nguồn WebSocket (giá / khớp lệnh / mentor) đã hoàn thiện, có DI để test và mở rộng.
- Bộ kịch bản test tự động phủ các đường chính: connect/disconnect đột ngột, subscribe/broadcast,
  nhận `trade_fill`, streaming + cancel mentor, heartbeat keepalive, revalidation, backpressure
  drop-oldest + reliable (1011), xác thực single-use ticket, backplane multi-worker, degraded mode.
- Hạ tầng tiền đề (protobuf, email-validator, proto regenerate, `wsproto`) đã được xử lý để
  gateway boot sạch.
- **Hồi tố Giai đoạn 2A+**: bổ sung backplane multi-worker (Redis Pub/Sub), leader election fail-closed,
  snapshot cache Redis, dedupe `SETNX`, revalidation token giữa phiên, và bỏ cơ chế "kick client
  passive" — 6 lỗ hổng production-readiness đã được vá.
- **Hồi tố Giai đoạn 2A+ (vòng 2)**: vá tiếp 5 rủi ro nghiêm trọng do phản biện — (1) split-brain
  leader election khi Redis chập chờn → fail-closed, (2) DDoS Postgres từ revalidation heartbeat →
  TTL-cache `(user_id, exp)`, (3) mất state/watermark khi leader failover → snapshot session + watermark
  trên Redis, (4) backplane "một đi không trở lại" → self-broadcast + skip echo + reconnect backoff,
  (5) phụ thuộc tuyệt đối vào Pub/Sub echo → tự broadcast local ngay. Test 58/58 pass, `ruff` sạch.
- **Hồi tố Giai đoạn 2A+ (vòng 3, hiệu năng & an toàn quy mô lớn)**: vá 5 lỗ hổng phản biện —
  (1) gia hạn lock bằng `SET XX` không kiểm tra token → script Lua nguyên tố `GET==token` mới được
  gia hạn (chống split-brain), (2) `psubscribe("finsim:ws:*")` gửi mọi tin tới mọi worker → dynamic
  subscription theo room có client local, (3) 1.500 round-trip Redis nối tiếp khi 500 giao dịch +
  Seq Scan bảng `transactions` → pipeline batching + composite index `(created_at, id)`, (4) `send_text`
  treo vô hạn (Slowloris) → timeout cứng 10s, (5) Thundering Herd khi auth cache `clear()` toàn bộ +
  worker phụ gọi HGETALL cho từng client → LRU eviction + snapshot RAM cache TTL 1s.
  Test 66/66 pass, `ruff` sạch.
- **Hồi tố Giai đoạn 2A+ (vòng 4, phản biện lỗi & rủi ro thực tế)**: vá 4 vấn đề do phản biện —
  (1) lỗi DB tại revalidation văng ra ngoài làm đóng socket hàng loạt → bắt riêng lỗi DB, trả True
  giữ phiên + không cache + bọc `on_validate` trong `handle_connection`, (2) broadcast-tồi-SETNX mở
  cửa sổ trùng tin giữa event-push và poll catch-up → claim-first (SETNX trước send) + watermark
  luôn vượt cả batch, (3) subscribe/unsubscribe đan xen lệch trạng thái room → lock serialize + đọc
  lại số client thực, (4) rò handle PubSub + hai listener cùng relay khi reconnect → `_activate_pubsub`
  dừng listener cũ + `aclose()` pubsub cũ trước khi cài mới. Test 75/75 pass, `ruff` sạch.
- **Hồi tố Giai đoạn 2A+ (vòng 5, an toàn xác thực WS + QoS + degraded mode)**: đánh giá 5 mục phản
  biện → vá 3 mục khả thi ngay: (1) JWT qua `?token=` rò rỉ vào access log/APM trace → single-use
  ticket qua REST `POST /auth/ws-ticket`, handshake `?ticket=` tiêu thụ nguyên tử `GETDEL`, TTL 15s,
  fail-closed khi Redis hỏng; (2) drop-oldest làm mất cả tin giao dịch → tách 2 queue, trade fill đi
  kênh reliable không drop, tràn → đóng 1011 để resync; (5) client "chết lặng" khi mất Redis →
  `feed_status` degraded/live + `resync_via` REST + welcome nhúng `realtime_status`. Hai mục còn lại
  ghi nhận cho Giai đoạn 3 (xem "Việc còn lại"): (3) Redis Streams thay Pub/Sub + (4) transactional
  outbox + CDC. Test 85/85 pass, `ruff` sạch.
- **Hồi tố Giai đoạn 2A+ (vòng 6, 5 nghẽn production từ phản biện)**: vá toàn bộ 5 điểm —
  (1) **Watermark Flaw**: Postgres `now()` = START tx, giao dịch commit lệch thời gian bị watermark
  bỏ sót vĩnh viễn → poll đọc Lookback Window `created_at >= watermark − 5s` (dedupe SETNX + seen_ids
  chặn đẩy trùng); (2) **Pub/Sub mất tin silent** → gắn `seq` tăng dần theo kênh user (Redis INCR
  pipeline) cho mọi `trade_fill`/`order_update`, client dò gap → resync REST; Streams chuyển hẳn
  sang Giai đoạn 3; (3) **Thundering Herd khi rolling deploy** → `stop_ws_background` đóng mọi WS bằng
  Close Code **1012** (Service Restart) để client backoff + jitter, cộng user cache 30s khi bắt tay
  (N reconnect → 1 SELECT/user) và lỗi DB lúc handshake → 1008 sạch thay vì 500; (4) **Block Event
  Loop phá leader election** → vòng phát price re-check `is_leader()` ngay trước broadcast (lock hết
  hạn trong lúc đọc DB → bỏ tick, không đẩy trùng); (5) **RAM Redis cho SETNX** → prefix namespaced
   `finsim:ws:dedup:trade:{id}` + `ex=300` cố định (vốn đã có TTL, giờ kiểm chứng bằng test). Test
   93/93 pass, `ruff` sạch.
- **Hồi tố Giai đoạn 2A+ (vòng 7, đối chiếu 4 điểm vận hành thực tế)**: đánh giá lại 4 rủi ro →
  vá/ghi nhận như sau: (1) **Pub/Sub fire-and-forget mất tin khớp lệnh** — xác nhận đúng (backplane
  vẫn Pub/Sub thuần, mất tin là mất hẳn) → chuyển hẳn sang Redis Streams ở Giai đoạn 3; (2)
  **Split-brain tạm thời khi leader bị pause** — vá NGAY bằng **fencing token**: cùng script Lua
  `INCR` counter riêng khi giành chủ mới, `acquire()` trả về mã nhiệm kỳ tăng dần, gia hạn giữ
  nguyên, receiver bác token ≤ đã thấy (chặn leader cũ tỉnh dậy phát nốt tin đang dở bằng token
  thấp); (3) **SimTime 1:1440 nhạy cảm với timer trễ** — rà soát mã xác nhận simtime ĐÃ tính tuyệt
  đối `max((now - anchor), 0) × ratio` từ wall-clock, không có timer cộng dồn nào; chỉ bổ sung
  test chống hồi quy (trễ tick không tích lũy sai số); (4) **Bão reconnect khi tràn reliable
  queue** — phía server đã đóng 1011/1012 sạch; client SDK chưa tồn tại trong repo nên ghi nhận
  contract (exponential backoff + jitter cho 1011/1012) vào Giai đoạn 3. Test 95/95 pass, `ruff`
  sạch.

### Việc còn lại trước Giai đoạn 3 (không chặn nghiệm thu):

1. 🟡 Chạy lại mục 3.2 khi có môi trường Postgres **+ Redis** để xác nhận end-to-end: multi-worker
   (`uvicorn --workers 2`) phát giá qua backplane, leader election failover, và khả năng phục hồi
   backplane khi Redis quay lại sau khi ngắt.
2. 🟢 Giai đoạn 3: thay `StaticMentorStream` bằng AI Engine (giữ nguyên giao thức WS).
3. 🟢 Nối `notify_transactions`/`notify_order_update` vào `services/trading_service.py` sau khi
   khớp lệnh (đường push in-process + backplane hiện đã có, chờ nối).
4. 🟡 Giai đoạn 3 — **Redis Streams** (mục 2 phản biện vòng 6, từng là mục 3 vòng 5): hiện Pub/Sub
   "mất tin là mất hẳn" (không replay được). Vòng 6 đã vá TẠM bằng `seq` per-channel (client phát
   hiện gap → resync REST) nhưng chưa thay thế bus. Giai đoạn 3: chuyển bus realtime sang Stream
   (consumer group, `XREADGROUP` + `XPENDING`/`XAUTOCLAIM`) để (a) message có backlog/replay khi
   client/worker reconnect, (b) watermark đồng bộ giữa các consumer, (c) trace. Pub/Sub giữ cho
   fan-out giá tốc độ cao không cần bền. Kèm client-side contract: nhận Close Code 1012 → backoff +
   jitter trước khi reconnect, không dồn dập `POST /auth/ws-ticket` khi rolling deploy.
5. 🟡 Giai đoạn 3 — **Transactional Outbox + CDC** (mục 4 phản biện vòng 5): `notify_transactions`
   đang "gọi sau commit" nên có cửa sổ mất tin giữa commit DB và broadcast (crash ở giữa). Vòng 6 đã
   vá TẠM bằng Lookback Window (bắt lại giao dịch commit lệch thời gian) nhưng không triệt để bằng
   ghi sự kiện vào bảng `outbox` NGAY trong transaction khớp lệnh; một worker (Debezium/Outbox
   Relay) đọc outbox (watermark/row-locking) rồi publish lên realtime bus → "chính xác một lần"
   giữa DB và WS.

---

*Báo cáo nghiệm thu kết thúc. Chờ phê duyệt để bước sang Giai đoạn 3: AI Mentor & AI Engine.*
