# FinSimAI — Nhật ký sửa lỗi (chống trùng lặp)

> Mục đích: mỗi phiên chỉ tập trung làm **một việc cho thật hoàn hảo**, rồi ghi lại ở đây.
> Trước khi bắt đầu việc mới, đọc file này để không làm lại việc đã xong.
>
> Nguồn danh sách: review toàn diện 2026-10-13 (bảo mật / giao dịch / mô phỏng / mentor /
> frontend / triển khai). Cập nhật trạng thái tại cột "Trạng thái".

---

## Bảng trạng thái tổng quan

| # | Mức | Việc | Vùng | Trạng thái |
|---|-----|------|------|-----------|
| 1 | P0 | Refresh token dùng được như access token | `core/dependencies.py` | ✅ **Xong 2026-10-13** |
| 2 | P0 | `JWT_SECRET` mặc định + không chặn khởi động production | `core/config.py`, `main.py` | ✅ **Xong 2026-10-13** |
| 3 | P0 | Cơ chế "tin tức → giá" chưa tồn tại | `market_service`, `price_generator` | ✅ **Xong 2026-10-13** |
| 4 | P0 | Lệnh mua market có thể làm hỏng công ty (freeze/fill) | `api/v1/trades.py`, `trading_service` | ✅ **Xong 2026-10-13** |
| 5 | P0 | Không có biên độ giá cho lệnh limit + thiếu validation lệnh | `schemas/trade.py`, `trading_service` | ✅ **Xong 2026-10-13** |
| 6 | P0 | Math/AI Engine mở công khai, `n_steps` không giới hạn (DoS) | `math_engine/http_server.py`, `ai_engine` | ✅ **Xong 2026-10-13** |
| 7 | P0 | Backend demo Apps Script: plaintext, seed admin, URL hard-code | `scripts/gsheets-backend/`, `api.ts` | ✅ **Xong 2026-10-13** |
| 8 | P0 | Frontend bịa giá và lịch sử giá | `usePriceStream.ts`, `PriceChart.tsx` | ✅ **Xong 2026-10-13** |
| 9 | P1 | T+2 tính theo ngày thực thay vì giờ mô phỏng | `settlement_service.py` | ✅ **Xong 2026-10-13** |
| 10 | P1 | Biên ±7% không có hiệu lực (neo sai mốc) | `price_generator.py` | ✅ **Xong 2026-10-13** |
| 11 | P1 | `_apply_sell_fill` sinh tiền từ hư không khi thiếu portfolio | `trading_service` | ✅ **Xong 2026-10-13** |
| 12 | P1 | Rate limit đăng nhập: đếm sai + thiếu `FORWARDED_ALLOW_IPS` + email hoa/thường | `api/v1/auth.py`, `render.yaml` | ✅ **Xong 2026-10-13** |
| 13 | P1 | Bộ lọc policy mentor bị lách (tiếng Việt + tiếng Anh) | `ai_engine/agents/policy.py` | ✅ **Xong 2026-10-13** |
| 14 | P1 | `render.yaml` thiếu `INTERNAL_API_KEY`, `BACKEND_GATEWAY_URL` | `render.yaml`, `.env.example` | ✅ **Xong 2026-10-13** |
| 15 | P1 | CI không chạy khi push, mypy strict không chạy, thiếu test frontend/integration | `.github/workflows`, `apps` | ✅ **Xong 2026-10-13** |
| 16 | P1 | Vệ sinh repo + frontend: `.opencode/`, `/metrics` mở, `remotePatterns:**` | nhiều nơi | ✅ **Xong 2026-10-13** |

Thứ tự ưu tiên đề xuất (theo review): **1, 2** (vài giờ) → giới hạn `n_steps` (#6),
xóa URL mặc định (#7) → #5, #4, #9, #8 (vài ngày) → #3, gộp Math Engine, endpoint lịch sử
giá, test đồng thời/frontend (một tuần).

---

## ✅ #1 — Refresh token dùng được như access token (2026-10-13)

**Lỗ hổng (P0):** `core/dependencies.py::_resolve_user` decode JWT rồi lấy `sub` mà **không
kiểm tra claim `type`**. Vì access token và refresh token cùng ký bằng `JWT_SECRET`, một
refresh token (sống **30 ngày**) gọi được **mọi API được bảo vệ** — biến token 60 phút thành
token 30 ngày. Test cũ chỉ kiểm tra chiều ngược lại (`/auth/refresh` từ chối access token),
không phủ chiều này.

**Sửa:**
- `apps/backend_gateway/core/dependencies.py`: trong `_resolve_user`, sau khi decode, thêm
  `if payload.get("type") != "access": return None`. Fail-closed: token **thiếu** claim
  `type` (định dạng cũ) cũng bị từ chối. Refresh token không còn dùng được ở REST/HTTP.
- Không đổi đường `/auth/refresh` (đã có kiểm tra `type == "refresh"`).
- WS không bị ảnh hưởng: handshake dùng single-use ticket, không truyền JWT.
- Thêm `apps/backend_gateway/tests/test_token_type.py` (6 test): access hợp lệ → 200; refresh
  làm access → 401; token thiếu `type` → 401; user inactive → 401; user không tồn tại → 401;
  thiếu token → 401. Kiểm tra ở ranh giới HTTP thật (`get_current_user` + `get_db` override).

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest tests/test_token_type.py tests/test_auth_hardening.py tests/test_auth.py tests/test_roles.py -q   # 36 passed
.venv\Scripts\python.exe -m ruff check core/dependencies.py tests/test_token_type.py                                               # All checks passed
```

**Lưu ý kèm theo (chưa sửa, thuộc #1 nhưng chuyển sang việc riêng nếu cần):**
- Cơ chế "xoay vòng" refresh token **chưa thu hồi token cũ** — không có `jti` / danh sách
  thu hồi, nên token cũ vẫn dùng được tới khi hết hạn. Cần một việc riêng nếu muốn revoke.

---

## ✅ #6 — Siết Math Engine & AI Engine (2026-10-13)

**Lỗ hổng (P0):**
- `math_engine/http_server.py` mở công khai, `n_steps` không giới hạn → `n_steps=10**9`
  cấp mảng numpy khổng lồ + vòng lặp Python → DoS instance free. `nav_history` cũng không trần.
- `ai_engine` mở `/docs`, route `/api/v1/mentor*` không auth → ai cũng đốt quota Gemini.

**Sửa — giới hạn tham số:**
- Math Engine: `n_steps: Field(ge=1, le=MAX_N_STEPS=10_000)`, `nav_history: Field(max_length=100_000)`,
  `holdings: max_length=1_000`, `dt_years: ge=0`. Vượt trần → 422.

**Sửa — auth nội bộ (shared secret `INTERNAL_API_KEY`, header `X-Internal-Api-Key`):**
- Math Engine: dependency `require_internal_key` gắn cho 4 route `/api/v1/*`; health vẫn mở.
  Có key → bắt buộc khớp (`compare_digest`); production thiếu key → 503 fail-closed; dev mở.
- AI Engine: cùng dependency gắn ở cấp `APIRouter`; tắt `/docs`, `/redoc`, `/openapi.json`
  khi `ENVIRONMENT=production`; giới hạn `message ≤ 2000`, `history ≤ 20`.
- Gateway `math_client` + `mentor_client`: gửi `X-Internal-Api-Key` khi `settings.internal_api_key` có giá trị.
- `render.yaml`: thêm `INTERNAL_API_KEY` (+ `ENVIRONMENT=production`) cho math-engine, ai-engine-api,
  backend-gateway; thêm `BACKEND_GATEWAY_URL` cho ai-engine-api.

**Test:** math_engine `tests/test_http_server.py` (10 ca), ai_engine `tests/test_mentor_api.py`
(+4 ca auth/độ dài). Kết quả: math 106 passed, ai 176 passed, gateway 273 passed (2 đỏ sẵn có).

**Chưa làm (việc lớn hơn, tách riêng):** gộp Math Engine vào gateway như một thư viện (bỏ 1 service
free tier, hết cold start). Đây là refactor kiến trúc, không nằm trong phạm vi vá bảo mật này.

---

## ✅ #2 — Chốt chặn JWT secret production (2026-10-13)

**Lỗ hổng (P0):** `JWT_SECRET` mặc định `dev-secret-change-me` và `render.yaml` để
`sync: false`. Quên điền biến → bất kỳ ai biết giá trị mặc định đều ký được JWT hợp lệ.

**Sửa:** `core/config.py` thêm `@model_validator(mode="after")` `_validate_production_secrets`:
khi `environment == production` thì **từ chối khởi động** nếu `jwt_secret` là mặc định hoặc
ngắn hơn 32 ký tự (fail-fast ngay lúc import settings, trước cả khi kết nối DB). Dev/test
không bị ảnh hưởng. Hằng số `DEFAULT_JWT_SECRET`, `MIN_JWT_SECRET_LENGTH`.

**Test:** `tests/test_config_hardening.py` (5 ca). `ruff` sạch.

---

## ✅ #7 — Vá & cô lập backend demo Google Apps Script (2026-10-13)

**Bối cảnh:** tồn tại một backend demo song song chạy trên Google Apps Script + Google
Sheets (`scripts/gsheets-backend/`), dùng cho bản demo trên Vercel khi KHÔNG chạy FastAPI.
Nó mở công khai ("Anyone") và có nhiều lỗ hổng P0.

**Lỗ hổng (P0) đã xác nhận:**
- `apps/frontend/src/services/api.ts` hard-code URL `exec` của Apps Script làm **mặc định** →
  bất kỳ deploy nào lỡ bật demo mode sẽ gọi một backend công khai ngoài dự án.
- `Code.gs` seed `demo/demo123`, `admin/admin123`, `host/host123` — mật khẩu **plaintext**
  lưu thẳng trong cột `password` của Google Sheet.
- `Router.gs` `authLogin_` so sánh mật khẩu thô; danh tính suy từ `?demo_user=` (mặc định
  `u-demo`); token `demo.<uuid>` không kiểm tra.
- Route `/admin/*` **không kiểm tra role** → ai cũng đổi role/status user qua HTTP.

**Quyết định (người dùng chọn):** *vá + cô lập*, KHÔNG xóa — giữ demo chạy được nhưng đóng
các lỗ hổng. KHÔNG đổi kiến trúc sang auth thật cho demo.

**Sửa — frontend (`apps/frontend/src/services/api.ts`):**
- Xóa URL Apps Script hard-code. `getSsApiBaseUrl()` chỉ đọc `NEXT_PUBLIC_SS_API_URL`
  (không còn giá trị mặc định).
- Trong nhánh demo của `request()`: nếu bật demo mà thiếu URL → ném `ApiClientError` rõ
  ràng, KHÔNG âm thầm gọi backend nào.
- `apps/frontend/.env.example`: tài liệu hóa `NEXT_PUBLIC_DEMO_MODE` / `NEXT_PUBLIC_SS_API_URL`
  và nhấn mạnh URL là bắt buộc.

**Sửa — Apps Script (`scripts/gsheets-backend/Code.gs`):**
- Thêm `hashPassword_` / `verifyPassword_` (salt riêng từng user, SHA-256, định dạng
  `sha256$<salt>$<hex>`), `sha256Hex_`, `timingSafeEqual_`, `isHashedPassword_`.
- Seed **chỉ còn `u-demo`** (role `user`); bỏ hẳn seed `u-admin`/`u-host-1` (backdoor).
  Mật khẩu lấy từ Script Property `DEMO_USER_PASSWORD`; nếu chưa đặt thì sinh ngẫu nhiên,
  lưu lại property và ghi log — **không hard-code mật khẩu** trong mã nguồn.
- Thêm `migrateUserSecurity_()` (idempotent, chạy cuối `seedIfEmpty_` mỗi request): xóa dòng
  `u-admin`/`u-host-1` seed cũ và băm lại mọi mật khẩu plaintext còn sót.
- Contest seed `co-1` đổi `owner_id` từ `u-host-1` (đã bỏ) sang `u-demo`.

**Sửa — Apps Script (`scripts/gsheets-backend/Router.gs`):**
- `authLogin_` dùng `verifyPassword_`; nếu gặp plaintext cũ thì tự nâng cấp sang băm ngay sau
  lần đăng nhập đầu (defense-in-depth, kể cả khi migration chưa chạy).
- `authRegister_` băm mật khẩu trước khi ghi.
- Thêm `requireAdmin_(q)`: chặn toàn bộ nhánh `/admin/*` nếu người gọi không có role `admin`
  (trả 403). Vì seed đã bỏ admin, mặc định **không ai** vào được `/admin/*` ở demo.

**Kiểm chứng:**
```
node --check Code.gs(Router.gs/Rewards.gs)              # cú pháp hợp lệ (đổi .gs → .js)
tsc --noEmit -p apps/frontend/tsconfig.json            # pass
npm run lint (apps/frontend)                            # No ESLint warnings or errors
```

**Hệ quả vận hành (cần biết):**
- Deploy frontend ở chế độ demo BẮT BUỘC đặt `NEXT_PUBLIC_SS_API_URL`.
- Sheet demo mới: đặt Script Property `DEMO_USER_PASSWORD` (hoặc đọc log lần seed đầu).
- Sheet demo cũ: dòng `u-admin`/`u-host-1` sẽ bị xóa ở request kế tiếp; mật khẩu cũ của
  `u-demo` (vd `demo123`) vẫn đăng nhập được nhưng được băm lại ngay.
- Đây là backend demo (không có xác thực thật). Muốn có auth thật thì chạy FastAPI thay vì
  demo mode; không nằm trong phạm vi vá này.

---

## ✅ #5 — Biên độ giá trần/sàn cho lệnh limit + siết validation lệnh (2026-10-13)

**Lỗ hổng (P0):**
- `OrderRequest` (schemas/trade.py) chỉ ràng buộc `price > 0`, `quantity > 0`; **không có biên
  độ** quanh giá thị trường → user đặt limit giá bất kỳ (vd mua 1000×, bán 0.001×). Lệnh treo
  có thể tự khớp (2 tài khoản) ở mức giá thao túng để **chuyển tiền** giữa các tài khoản, phá
  tính thực tế của mô phỏng. Khớp user↔user dùng thẳng giá limit nên không có gì chặn.
- `quantity` không trần, không giới hạn phần thập phân; `price` không giới hạn phần thập phân
  → giá trị vượt `Numeric(20,2)` / `Numeric(20,4)` bị Postgres **làm tròn âm thầm** (lệch tiền
  đóng băng / thực nhận) hoặc tràn cột (lỗi 500).

**Sửa:**
- `core/config.py`: thêm `price_band_pct = 0.07` (±7% theo HOSE) và
  `max_order_quantity = 1_000_000_000` (trần khối lượng/lệnh).
- `schemas/trade.py` (`OrderRequest`):
  - `quantity: Field(gt=0, le=max_order_quantity)`.
  - `field_validator("price")`: tối đa 2 chữ số thập phân (khớp `Numeric(20,2)`).
  - `field_validator("quantity")`: tối đa 4 chữ số thập phân (khớp `Numeric(20,4)`).
  - Giữ nguyên quy tắc cũ: limit bắt buộc có giá, market bỏ giá.
- `services/trading_service.py`: thêm 2 hàm thuần, dễ test:
  - `price_band_bounds(reference, band_pct) -> (lower, upper)` — làm tròn tới cent.
  - `is_price_within_band(price, reference, band_pct)` — inclusive; fail-open khi
    `reference <= 0` (chưa có giá tham chiếu hợp lệ; các check vốn/CP vẫn bảo vệ).
- `api/v1/trades.py::create_order`: sau khi lấy company, với lệnh **limit** kiểm tra giá trong
  biên độ; ngoài biên độ → **422** với `detail.code = "price_out_of_band"` kèm
  `reference_price`, `lower`, `upper`, `band_pct`. Lệnh market không áp biên độ (đã ngầm nằm
  trong biên qua giá thị trường + slippage ≤2%).

**Test (mới 19 ca):**
- `tests/test_order_validation.py` (11 ca): scale giá/KL, trần KL, giá bắt buộc cho limit,
  market bỏ giá, biên đúng bằng trần.
- `tests/test_order_band_api.py` (4 ca): giá trên trần / dưới sàn → 422 `price_out_of_band`;
  giá đúng biên và lệnh market đi tiếp qua cổng giá (tới check vốn → 400).
- `tests/test_trading_service.py` (+4 ca): `price_band_bounds` (±7%, làm tròn cent),
  `is_price_within_band` (biên inclusive, fail-open khi reference ≤ 0).

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest -q          # 292 passed, 2 failed (đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check <các file đã sửa>   # All checks passed
```

**Ghi chú (chưa làm, không thuộc phạm vi):** lệnh đang treo không được kiểm tra lại khi giá
thị trường dịch chuyển (band động) — khớp vẫn bị chặn bởi giá limit + thanh khoản, nên không
tạo được fill giá phi lý. Nếu muốn đúng luật hơn: tự huỷ lệnh treo khi giá vượt biên.

---

## ✅ #4 — Lệnh mua market làm hỏng công ty do freeze/fill (2026-10-13)

**Lỗ hổng (P0):** lệnh market buy đóng băng đúng bằng `qty × giá_hiện_tại × (1+fee)`
nhưng khi khớp lại có thể trả **nhiều hơn** số đã đóng băng, làm `cash_balance` âm →
vi phạm `CheckConstraint cash_balance >= 0` → `IntegrityError` khi commit **giữa
`match_orders`**. Vì không có try/except quanh fill, cả nhịp khớp của công ty bị abort;
lệnh market buy lỗi nằm đầu sổ (`price DESC NULLS FIRST`) nên **mắc kẹt vĩnh viễn** —
mỗi nhịp lại abort (công ty "đóng băng"). Hai đường gây overpay:
1. **Market-maker**: giá khớp trượt lên tới +2% (`compute_fill_price`) ≫ buffer phí 0.15%.
2. **User↔user**: `_price_crosses(None, sell_price)` luôn True → market buy khớp với
   lệnh bán limit treo ở **bất kỳ giá nào**; sau khi giá trôi, lệnh treo có thể cao hơn
   giá hiện tại rất nhiều (`fill_price = sell_price`).
Ngoài ra `_buy_freeze_price` trả `buy.price` (chưa gồm phí) cho lệnh limit → khớp **một
phần** rò rỉ đúng phần phí mỗi lượt, cũng có thể đẩy cash âm.

**Sửa:**
- `core/config.py`: thêm `max_slippage_impact = 0.02` (trần tác động thị trường).
- `services/slippage.py`: dùng `settings.max_slippage_impact` thay hằng số 0.02 cứng;
  thêm `round_down_to_tick` (làm tròn xuống bội số tick khi chặn trần giá).
- `api/v1/trades.py::create_order`: lệnh **market buy** đóng băng ở
  `giá_hiện_tại × (1 + max_slippage_impact) × (1 + fee)` — dư buffer để khớp trượt lên.
- `services/trading_service.py`:
  - `_buy_freeze_price` trả **đơn giá đã đóng băng thực tế** (`frozen_cash / khối lượng
    còn lại`, đã gồm buffer phí) cho mọi loại lệnh → khớp một phần hoàn đúng tiền, hết rò phí.
  - Thêm `_buy_max_fill_price`: giá khớp tối đa để không âm số dư — limit = giá limit,
    market = phần đóng băng đã bỏ buffer phí (≈ giá hiện tại × (1+max_slippage_impact)).
  - `_fill_against_market`: chặn trần giá mua bằng `_buy_max_fill_price` (market bị chặn
    khi giá trôi lên, làm tròn xuống tick); trước đây chỉ limit mới được chặn.
  - Pass user↔user: nếu lệnh mua không đủ tiền đóng băng cho giá của lệnh bán → **không
    khớp trong sổ**, `rollback` + `break`, để pass market-maker khớp ở giá thị trường.

**Vì sao an toàn:** với lệnh limit `fill ≤ limit = đơn giá đóng băng/(1+fee)`; với market
`fill ≤ giá_hiện_tại_đặt × (1+max_slippage_impact)` = đơn giá đóng băng/(1+fee). Do đó
`unfreeze ≥ fill_qty × fill × (1+fee) = total_debit` → `cash_balance` không bao giờ giảm.

**Test (mới 9 ca):** `test_trading_service.py` (+4): `_buy_freeze_price` gồm phí cho limit;
`_buy_max_fill_price` cho limit/market; market bỏ buffer phí nhưng giữ buffer trượt giá;
frozen=0 → 0. `test_trade_costs.py` (+2): khớp một phần không rò phí; khớp tại đúng giá tối
đa giữ cash ≥ 0. `test_slippage.py` (+2): `round_down_to_tick`; `max_slippage_impact` cấu
hình được. `test_order_band_api.py` (+1): market buy đóng băng đúng công thức có buffer.

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest -q          # 301 passed, 2 failed (đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check <các file đã sửa>   # All checks passed
```

**Ghi chú (chưa làm):** frontend (`TradePanel`) ước tính vốn cho lệnh market chỉ theo giá
hiện tại (chưa gồm buffer trượt giá 2%), nên user dùng sát toàn bộ số dư có thể bị backend
từ chối "Insufficient available cash". Cân nhắc đồng bộ buffer sang frontend nếu muốn UX
khớp tuyệt đối. Khoản dư đóng băng được hoàn lại ngay khi khớp.

---

## ✅ #9 — T+2 tính theo ngày mô phỏng (không phải ngày thực) (2026-10-13)

**Lỗ hổng (P1):** hệ thống nén thời gian **1:1440** (1 phút thực = 1 ngày giao dịch ảo, xem
`realtime/simtime.py`), nhưng `settlement_deadline` cộng thẳng
``simulated_at + timedelta(days=settings.settlement_days)`` = **2 ngày THỰC**. Trong một
phiên mô phỏng (vài chục phút), user bán xong **không bao giờ** thấy tiền về tài khoản khả
dụng — sai hoàn toàn với bất biến "T+2" mà sản phẩm quảng bá. Tiền nằm kẹt ở `settling_cash`
vô thời hạn. Sai lệch đúng bằng tỉ lệ nén: **1440×** (2 ngày thực = 2880 ngày ảo).

**Sửa:** quy đổi "ngày GIAO DỊCH MÔ PHỎNG" sang giây thực qua đồng hồ nén.
- `realtime/simtime.py`: thêm hằng `REAL_SECONDS_PER_SIM_DAY = SIM_SECONDS_PER_DAY /
  DEFAULT_COMPRESSION_RATIO` (= 60 giây) và hàm `real_seconds_for_sim_days(days, ratio)`
  (nghịch đảo của `real_to_sim_epoch`). Xuất ở `realtime/__init__.py`.
- `services/settlement_service.py::settlement_deadline`: `simulated_at +
  timedelta(seconds=real_seconds_for_sim_days(settings.settlement_days))` → T+2 = **120 giây
  thực**. `settles_at` vẫn lưu bằng đồng hồ thực UTC (đồng bộ với `release_due` so `<= now()`),
  chỉ đổi **độ dài** khoảng chờ. Bỏ import `update` không dùng.
- `core/config.py`: cập nhật chú thích `settlement_days` (ngày mô phỏng, không phải ngày thực).

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest tests/test_settlement.py tests/test_simtime.py -q   # passed
.venv\Scripts\python.exe -m ruff check realtime/simtime.py realtime/__init__.py services/settlement_service.py core/config.py tests/test_settlement.py   # All checks passed
```

**Test:** `tests/test_settlement.py` cập nhật + bổ sung: `REAL_SECONDS_PER_SIM_DAY == 60`,
T+2 = +120 giây và **khác** +2 ngày thực (chốt chống tái phát bug), nhánh naive vẫn gán UTC.

**Sửa kèm (test flaky sẵn có, không liên quan #9):**
`tests/test_market_service.py::test_fetch_price_values_falls_back_when_unavailable` gọi GBM
fallback với `seed=None` → `random.Random()` **không seed**, có ~8% xác suất giá làm tròn về
đúng `42.10` khiến assert `price != 42.10` **đỏ giả** (đã tái hiện 1/30 lần chạy). Truyền
`seed=7` cố định để test tất định. Đây là lỗi test có sẵn, được sửa để giữ suite xanh ổn định.

---

## ✅ #15 — CI: push trigger + mypy strict + test frontend/integration (2026-10-13)

**Lỗ hổng (P1):**
- `.github/workflows/ci.yml` chỉ chạy `on: pull_request` → push thẳng lên `main`
  không qua gate.
- `[tool.mypy] strict = true` đã cấu hình nhưng **không có bước nào chạy mypy**.
  Thực trạng: math_engine 151 lỗi, backend_gateway 112, ai_engine chặn bởi
  "duplicate module `crawl_tasks`", packages/database sạch.
- Frontend **không có test đơn vị**; backend thiếu test integration ở mức ráp app.
- 24 lỗi **ruff sẵn có** trong phạm vi CI (I001/F401/E501/F841/N814/SIM103) khiến
  bước "Ruff lint" lẽ ra phải đỏ.

**Sửa — CI (`.github/workflows/ci.yml`):**
- Thêm `on.push.branches: [main]` (giữ `pull_request`).
- Thêm 4 bước **Mypy strict** chạy TỪNG app (`packages/database`, `backend_gateway`,
  `math_engine`, `ai_engine`) — chạy chung một lệnh sẽ lỗi trùng tên module
  `conftest`/`crawl_tasks`.
- Thêm job `frontend-unit` (Node 24, `npm run test:unit`) chạy test đơn vị
  frontend bằng test runner có sẵn của Node — **không cần dependency mới**.

**Sửa — mypy (pyproject.toml):**
- Thay `exclude` cũ (regex `/` không khớp trên Windows) bằng regex literal-string
  separator-agnostic `[/\\]`: bỏ qua code sinh tự động (`clients/proto`,
  `grpc_services`, `math_engine/grpc_server.py` legacy), migration, và **mọi thư
  mục `tests`**.
- `[[tool.mypy.overrides]] ignore_errors = true` cho **baseline nợ cũ** (18 module
  backend + 7 module ai) — kèm chú thích "xóa dần, đừng thêm mới (TODO #16)". Nhờ
  vậy `mypy --strict` xanh ngay, đồng thời **mọi module khác (kể cả code mới) vẫn
  bị gác strict**.
- Sửa 4 lỗi mypy nguồn ở math_engine để module này **không cần baseline**:
  `penalty.py`/`compressor.py` thêm `-> None`; `risk_metrics.py` bọc `np.asarray`;
  `http_server.py` `-> dict[str, str]`.
- Thêm `apps/ai_engine/tasks/__init__.py` để cố định tên module `tasks.*`, hết lỗi
  "found twice under different module names".

**Sửa — ruff (24 lỗi sẵn có → 0):** `ruff --fix` cho I001/F401, còn lại sửa tay:
`company.py` bỏ alias `Decimal as _D` (N814), `challenge_service`/`leaderboard_service`/
`trade_snapshot`/`loadtest.py` xuống dòng E501, bỏ biến chết F841
(`trade_snapshot.py`, `test_corporate_asof.py`), `socratic_mentor._matches_bank`
trả thẳng biểu thức (SIM103). Lệnh ruff đúng như CI: **All checks passed**.

**Sửa — test:**
- Frontend: `apps/frontend/tests/utils.test.ts` (16 test, `node:test`) cho các hàm
  thuần `format.ts`/`trading.ts`/`roles.ts`/`contest.ts`/`priceSimulator.ts`.
  Thêm script `test:unit`; bật `allowImportingTsExtensions` trong `tsconfig.json`
  (import `.ts` chạy trực tiếp bằng Node). `tsc --noEmit`, `next lint`, `next build`
  đều xanh.
- Backend: `apps/backend_gateway/tests/test_integration_app.py` (5 test) dựng
  **app thật** `main.create_app()` qua `httpx.ASGITransport` — kiểm health, metrics
  ghi nhận traffic, CORS preflight, 404, openapi (dev). Không cần Postgres/Redis.

**Kiểm chứng:**
```
uv run mypy packages/database            # Success (1 file)
uv run mypy apps/backend_gateway         # Success (97 files)
uv run mypy apps/math_engine             # Success (11 files)
uv run mypy apps/ai_engine               # Success (23 files)
ruff check <đúng phạm vi CI>             # All checks passed
apps/backend_gateway: pytest -q          # 324 passed, 2 failed (2 đỏ sẵn có)
apps/math_engine:     pytest -q          # 110 passed
apps/ai_engine:       pytest -q          # 178 passed
apps/frontend: npm run test:unit         # 16 passed
apps/frontend: tsc --noEmit / next lint / next build   # xanh
```

**Ghi chú:** `aiosqlite` không cài được (sandbox không mạng) nên test integration
dùng app thật + ASGITransport thay vì DB SQLite. Baseline mypy là tạm thời — dọn
nợ và xóa tên khỏi danh sách (đã gắn TODO #16).

---

## ✅ #14 — `render.yaml` / env mẫu thiếu biến nối nội bộ (2026-10-13)

**Hiện trạng:** `render.yaml` đã được #6 thêm `INTERNAL_API_KEY` cho cả 3 service
và `BACKEND_GATEWAY_URL` cho `ai-engine-api` + `FORWARDED_ALLOW_IPS` (#12). Nhưng
**tài liệu env** (`.env.production.example`, `.env.example`) vẫn KHÔNG liệt kê các
biến nối nội bộ, và `.env.example` còn giữ biến chết `MATH_ENGINE_GRPC_HOST/PORT`
(gRPC đã bỏ, chuyển sang HTTP `MATH_ENGINE_URL`) → người deploy theo mẫu sẽ thiếu
khoá `INTERNAL_API_KEY`/`BACKEND_GATEWAY_URL`, dẫn tới Math/AI Engine từ chối
request (fail-closed) mà không rõ nguyên nhân.

**Sửa:**
- `.env.example`: bỏ `MATH_ENGINE_GRPC_HOST/PORT`; thêm `MATH_ENGINE_URL`, `AI_ENGINE_URL`,
  `MENTOR_LLM_MODE`, `BACKEND_GATEWAY_URL`, `INTERNAL_API_KEY` (kèm chú thích shared-secret
  fail-closed); bổ sung các biến này vào khối "Production" comment.
- `.env.production.example`: thêm mục `AI_ENGINE_URL`, `BACKEND_GATEWAY_URL`,
  `INTERNAL_API_KEY` (kèm giải thích CÙNG giá trị ở 3 service), `MENTOR_LLM_MODE`.
- Thêm test hồi quy `apps/backend_gateway/tests/test_deploy_env.py` (7 test): parse
  `render.yaml`, bắt buộc mỗi service khai báo đủ biến tối thiểu; `INTERNAL_API_KEY`
  có ở cả 3 service; hai file env mẫu tài liệu hoá đủ biến nội bộ; `.env.example`
  không còn tham chiếu `MATH_ENGINE_GRPC`.

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest tests/test_deploy_env.py -q   # 7 passed
.venv\Scripts\python.exe -m pytest -q   # 319 passed, 2 failed (2 đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check tests/test_deploy_env.py  # All checks passed
```

---

## ✅ #13 — Bộ lọc policy mentor bị lách (Việt + Anh) (2026-10-13)

**Lỗ hổng (P1):** `agents/policy.py` chỉ có pattern TIẾNG VIỆT; khi user hỏi tiếng
Anh, LLM trả lời tiếng Anh và mọi câu khuyên mua/bán ("You should buy now.",
"I recommend selling.", "This is a great time to buy.") hoặc phán xét đúng/sai
("You were right.", "That was a bad decision.") đều LỌT. Một số slang Việt cũng
lọt: "kèo thơm", "lên/xuống tàu", "lướt sóng", "tất tay", "full hàng",
"mua/bán sạch", và động từ "khuyên" (khác "khuyến nghị").

**Sửa (`apps/ai_engine/agents/policy.py`):**
- Thêm nhóm pattern ADVICE tiếng Anh: `should buy/sell/...`, `(I|we) recommend/
  suggest/advise ... buy/sell`, `recommend buying/selling`, `good time/opportunity
  to buy/sell`, `it is a good buy`, `buy/sell now/dip`, `worth buying`, `go long/
  short`, `all-in`/`load up`, `put money into`, `take/lock in profit/gains`,
  `cut losses`, `definitely buy`, `buy the dip`, `(strong|clear|good) buy signal`.
- Thêm nhóm pattern JUDGMENT tiếng Anh: `you are/were right/wrong`,
  `(your|that) decision/choice/call/move is/was ...`, `good/bad decision`,
  `that was a bad move`, `I agree/disagree with your ...`.
- Thêm slang Việt: `lên/xuống tàu`, `lướt sóng`, `tất tay`, `full (cổ phiếu/hàng/
  vốn/margin/tiền)`, `(mua|bán|gom) sạch/hết/toàn bộ`, `(vào|mở) hàng`, `kèo thơm`,
  `buy/sell ngay/luôn` (trộn Việt–Anh), `khuyên ... mua/bán` và "bạn đã làm đúng/sai".
- **Chống báo nhầm quan trọng:** "khuyên" dùng negative lookbehind `(?<!loi\s)` để
  KHÔNG chặn disclaimer hợp lệ "không đưa ra **lời khuyên** mua bán" (câu safe bắt
  buộc phải đi qua). Vì advice thật thường kèm "nên mua/mua ngay" nên vẫn bị bắt.
- Cập nhật docstring mô tả phạm vi Việt + Anh.

**Test (`apps/ai_engine/tests/test_policy_golden.py`):**
- `EVASION_SENTENCES` 36→45 (thêm slang + "khuyên" + "bạn làm đúng/sai").
- Thêm `ENGLISH_EVASION_SENTENCES` (18 câu, gồm 2 câu trộn Việt–Anh).
- Thêm `LEGITIMATE_ENGLISH_TEXTS` (5 câu hợp lệ) + test `test_english_evasion_
  golden_set_all_blocked`, `test_legitimate_english_text_passes`.

**Kiểm chứng:**
```
cd apps/ai_engine
.venv\Scripts\python.exe -m pytest tests/test_policy_golden.py tests/test_socratic_mentor.py tests/test_golden_mentor.py tests/test_judge_pipeline.py -q  # 98 passed
.venv\Scripts\python.exe -m pytest -q   # 178 passed (trước là 176)
.venv\Scripts\python.exe -m ruff check agents/policy.py tests/test_policy_golden.py  # All checks passed
```

**Ghi chú:** Vẫn là lá chắn heuristic. Loại trừ hậu tố "lời khuyên" là đánh đổi có
chủ đích để bảo toàn disclaimer; các câu đó nếu thực sự khuyên mua/bán vẫn trúng
pattern "nên mua/mua ngay/khuyến nghị". Bộ golden-set chỉ được THÊM câu bị chặn.

---

## ✅ #12 — Rate limit đăng nhập: đếm sai + `FORWARDED_ALLOW_IPS` + email hoa/thường (2026-10-13)

Ba lỗi con:

**1) Đếm sai (đếm cả lần thành công).** `_rate_limit_or_429` gọi `check_rate` (vừa
INCR vừa kiểm tra) cho *mọi* lượt login, kể cả lượt ĐÚNG. Người dùng hợp lệ đăng
nhập quá ngưỡng (mặc định 10 lần/phút) trong một phút bị khoá oan; brute-force thì
lại dùng chung ngân sách với login hợp lệ.
- `core/ratelimit.py`: thêm `peek_rate` (chỉ đọc bộ đếm, KHÔNG tăng), `record_rate`
  (tăng + trả count), `reset_rate` (xoá bộ đếm). Giữ nguyên `check_rate` cho mentor
  WS. Redis-path có `get`/`delete`; fallback RAM tách `_mem_count`/`_mem_record`.
- `api/v1/auth.py`: tách `_login_keys`; `_rate_limit_or_429` chỉ **peek** (đọc) →
  429 nếu vượt; `_record_login_failure` chỉ ghi cả **tài khoản + IP** khi xác thực
  **thất bại**; login thành công → `reset_rate(login:identifier:…)` (xoá bộ đếm tài
  khoản, GIỮ bộ đếm IP để kẻ spam không "rửa" hạn mức IP bằng 1 tài khoản hợp lệ).

**2) Thiếu `FORWARDED_ALLOW_IPS`.** `main.py` bật `proxy_headers=True` nhưng uvicorn
mặc định chỉ tin `X-Forwarded-For` từ `127.0.0.1`; sau proxy Render/Fly (IP nội bộ
không cố định) `request.client.host` là IP proxy → mọi người dùng chung một bucket
IP (một kẻ tấn công khoá được toàn bộ IP).
- `render.yaml` (backend-gateway) + `apps/backend_gateway/fly.toml`: thêm
  `FORWARDED_ALLOW_IPS="*"`. Uvicorn đọc env này khi `forwarded_allow_ips` không được
  truyền (đã xác nhận trong `uvicorn.config.Config.__init__`).
- `.env.example` / `.env.production.example`: bổ sung biến + chú thích.

**3) Email hoa/thường.** `EmailStr` chỉ hạ chữ domain, không hạ phần local; register
lưu nguyên case, login so khớp `User.email == body.email` → `User@x.com` là tài khoản
khác `user@x.com`, đăng nhập sai case thất bại và đăng ký trùng chỉ khác case.
- `schemas/user.py`: thêm `field_validator("email", mode="after")` hạ chữ thường cho
  cả `RegisterRequest` và `LoginRequest`.
- `api/v1/auth.py`: register/login tra `func.lower(User.email) == body.email` (khớp
  cả dữ liệu cũ lưu case hỗn hợp).

**Test mới (6):**
- `tests/test_auth_hardening.py`: `test_peek_rate_does_not_increment`,
  `test_record_then_peek_blocks_and_reset_clears`,
  `test_login_success_does_not_consume_rate_limit` (max=1, 5 lần login đúng đều 200),
  `test_login_success_resets_account_counter`,
  `test_register_request_lowercases_email`, `test_login_request_lowercases_email`.

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest tests/test_auth_hardening.py tests/test_auth.py tests/test_roles.py -q  # 36 passed
.venv\Scripts\python.exe -m pytest -q   # 312 passed, 2 failed (đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check <các file đã sửa>   # All checks passed
```

**Ghi chú:** Uvicorn nhận `FORWARDED_ALLOW_IPS` qua biến môi trường (không cần truyền
CLI). Test tích hợp "email hoa/thường" chỉ chạy ở tầng schema + nhánh login (bộ test
dùng fake DB, không có Postgres thật); câu truy vấn `func.lower` là phòng vệ cho dữ
liệu cũ lưu case hỗn hợp.

---

## ✅ #11 — `_apply_sell_fill` sinh tiền từ hư không khi thiếu portfolio (2026-10-13)

**Lỗ hổng (P1):** `_apply_sell_fill` cộng `net_proceeds` vào `user.settling_cash`
**trước khi** kiểm tra portfolio. Nếu `Portfolio` không tồn tại (dữ liệu lệch), hàm
vẫn `return fee, tax` sau khi đã cộng tiền → user nhận tiền bán mà không sở hữu CP
("sinh tiền từ hư không"); caller lại tạo `Transaction` BÁN đối ứng.

**Sửa (`apps/backend_gateway/services/trading_service.py`):**
- Thêm domain exception `InsufficientHoldingError`.
- `_apply_sell_fill` đảo thứ tự: **tra portfolio trước** (khoá `with_for_update`);
  nếu `pf is None` hoặc `pf.frozen_quantity < fill_qty` hoặc `pf.quantity < fill_qty`
  → ném `InsufficientHoldingError` **trước khi** động tới `settling_cash`/`realized_pnl`.
- `_fill_against_market` (market-maker pass): bọc `_apply_sell_fill` trong
  `try/except InsufficientHoldingError` → `logger.warning` + `await db.rollback()` +
  `return None` (hủy lượt khớp, không tạo Transaction).
- `match_orders` (khớp user↔user): bọc tương tự; khi lỗi → rollback (gỡ cả phần mua
  đã ghi chưa commit) + đánh dấu `skip_buy_ids`/`skip_sell_ids` + `continue`, tránh
  lặp vô hạn trong nhịp.

**Test:**
- Đổi test cũ `test_sell_fill_without_portfolio_still_credits_settling_cash` (đã
  khẳng định hành vi lỗi) → `test_sell_fill_without_portfolio_raises_and_mints_no_cash`
  (kỳ vọng `InsufficientHoldingError`, `settling_cash == 0`).
- Thêm `test_sell_fill_with_insufficient_frozen_raises` (đủ CP nhưng frozen thiếu →
  ném lỗi, portfolio không đổi).
- Thêm `test_market_maker_skips_sell_without_holding` (`_fill_against_market` trả
  `None`, rollback 1 lần, commit 0, không thêm Transaction, không cộng tiền).

**Kiểm chứng:**
```
cd apps/backend_gateway
.venv\Scripts\python.exe -m pytest tests/test_trade_costs.py tests/test_trading_service.py tests/test_order_band_api.py -q  # 31 passed
.venv\Scripts\python.exe -m pytest -q   # 306 passed, 2 failed (đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check services/trading_service.py tests/test_trade_costs.py  # All checks passed
```

**Ghi chú:** `create_order` (sell) đã bắt buộc có portfolio + đủ CP khả dụng lúc đặt
lệnh, nên lỗi này là phòng vệ sâu cho dữ liệu lệch/xoá portfolio ngoài luồng. Đường
khớp user↔user chưa có test tích hợp DB thật (bộ test dùng fake, không có `async_session`
fixture) — đã test ở tầng `_apply_sell_fill` + `_fill_against_market`.

---

## ✅ #10 — Biên ±7% không có hiệu lực do neo sai mốc (2026-10-13)

**Lỗ hổng (P1):** `PriceGenerator.generate_price_path` neo biên trần/sàn vào `S[0]`
(giá bắt đầu của path). Backend mỗi nhịp gọi `/api/v1/prices/generate` với
`start_price = current_price` và `n_steps=1`, nên biên **trôi theo giá đang chạy**:
mỗi nhịp giá được phép đi ±7% so với chính nó → trong một ngày mô phỏng (~20 nhịp,
60 giây thực) giá có thể vượt xa ±7% so với giá tham chiếu. Biên "giá trần/sàn theo
luật VN" vì thế **không có tác dụng** như giới hạn trong ngày. Đúng ngữ nghĩa VN:
trần/sàn neo vào **giá tham chiếu = giá đóng cửa phiên trước**, cố định trong ngày.

**Sửa:**
- `apps/math_engine/engine/pricing/price_generator.py`:
  - `generate_price_path(..., reference_price=None)`: neo biên vào `reference_price`
    khi có; mặc định `start_price` (tương thích ngược).
  - `generate_price_path_batch(..., reference_prices=None)`: neo biên riêng cho từng
    tài sản; mặc định `S[:,0]`.
- `apps/math_engine/http_server.py`: `GenerateNextPricesRequest` thêm
  `reference_price: float | None = None`; truyền vào `generate_price_path`.
- `apps/backend_gateway/clients/math_client.py`: `generate_next_prices(...,
  reference_price=None)` — chỉ đưa vào payload khi có giá trị.
- `apps/backend_gateway/services/market_service.py`: cache giá tham chiếu theo NGÀY
  MÔ PHỎNG (`_DAY_REFERENCE: company_id -> (sim_day, giá)`); `_current_sim_day()` tính
  bằng đồng hồ nén (`realtime.simtime`, neo `ws_sim_anchor_epoch` như `price_ws`).
  Trong cùng ngày luôn trả mốc đã chốt; sang ngày mới chốt mốc mới = giá hiện tại.
  `update_all_prices`, `_fetch_price` đều truyền reference cho Math Engine. Chỉ leader
  cập nhật giá nên cache RAM nhất quán; failover → khởi tạo lại (coi như mở phiên mới).

**Thiết kế & đánh đổi:** neo vào **giá mở đầu ngày mô phỏng** (≈ đóng cửa phiên trước
vì nhịp ranh giới chưa di chuyển giá). Không cần migration/Redis: cache trong RAM của
leader. Leader mới khởi động giữa ngày sẽ lấy giá hiện tại làm tham chiếu (bắt đầu
một "phiên" mới) — chấp nhận được và có ghi chú.

**Test (mới 6 ca):**
- `apps/math_engine/tests/test_pricing.py` (+3): path neo biên vào reference (start 100,
  ref 50 → kẹp ≤53.5); `reference=None` giữ nguyên hành vi cũ; batch neo biên riêng
  từng tài sản.
- `apps/math_engine/tests/test_http_server.py` (+1): endpoint tôn trọng `reference_price`.
- `apps/backend_gateway/tests/test_market_service.py` (+2): `_reference_price` ổn định
  trong ngày, đổi mốc khi sang ngày; `_fetch_price_values` chuyển tiếp `reference_price`.

**Kiểm chứng:**
```
cd apps/math_engine;    .venv\Scripts\python.exe -m pytest -q   # 110 passed
cd apps/backend_gateway; .venv\Scripts\python.exe -m pytest -q   # 304 passed, 2 failed (đỏ sẵn có)
.venv\Scripts\python.exe -m ruff check <các file đã sửa>          # All checks passed
```

---

## ✅ #16 — Vệ sinh repo + frontend (2026-10-13)

Ba vấn đề vệ sinh độc lập, gộp một việc:

**1. `.opencode/` bị commit vào repo sản phẩm.** Thư mục skill của công cụ AI (`opencode`)
được commit ở commit `107af51` (147 file, toàn bộ nằm trong `.opencode/skills/impeccable/`;
`.opencode/node_modules/` vốn đã bị `.opencode/.gitignore` bỏ qua). Đây là rác repo — không
liên quan sản phẩm, làm nặng mọi clone/checkout.
- `.gitignore`: thêm mục `.opencode/` (chỉ dùng cục bộ).
- `git rm -r --cached .opencode` → bỏ khỏi git nhưng **giữ file trên đĩa** để skill vẫn chạy.
- Kiểm chứng: `git check-ignore .opencode` → `.opencode`; `git ls-files .opencode` → 0; file
  `.opencode/skills/impeccable/SKILL.md` vẫn tồn tại cục bộ.

**2. `/metrics` mở công khai.** `main.py` gắn route `/metrics` không xác thực, để lộ số liệu
lưu lượng (đường dẫn, mã trạng thái, latency, uptime) ra internet — bề mặt dò quét.
- `apps/backend_gateway/main.py`: `/metrics` thêm `dependencies=[Depends(require_internal_api_key)]`
  (shared-secret `X-Internal-Api-Key`). **Fail-closed**: `INTERNAL_API_KEY` chưa cấu hình →
  403. Production đã set biến này (render.yaml, #14) nên scraper nội bộ chỉ cần gửi header.
- Tái dùng đúng dependency của #6/#12 (`core/dependencies.py`), không thêm cơ chế mới.

**3. `remotePatterns: ["**"]` trong `next.config.js`.** Cho phép `next/image` tải ảnh từ
**mọi** hostname HTTPS → vector SSRF/hotlink/DoS ảnh. Toàn bộ frontend chỉ dùng ảnh nội bộ
`/logo.png` (grep `next/image` = 0); không có ảnh remote nào.
- `apps/frontend/next.config.js`: **xóa cả khối `images.remotePatterns`** → Next trả về hành
  vi mặc định (chặn ảnh remote, ảnh nội bộ vẫn chạy). Khi nào thật cần remote, khai báo lại
  allowlist hostname cụ thể.

**Test (mới 2 ca):**
- `apps/backend_gateway/tests/test_integration_app.py`: fixture `internal_key` (monkeypatch
  `settings.internal_api_key`); `test_metrics_records_traffic` gửi kèm header → 200;
  `test_metrics_requires_internal_key` (có key, thiếu header) → 403;
  `test_metrics_locked_when_key_unconfigured` (key trống, có header) → 403 (fail-closed).

**Kiểm chứng:**
```
cd apps/backend_gateway; .venv\Scripts\python.exe -m pytest -q   # 326 passed, 2 failed (đỏ sẵn có)
cd apps/backend_gateway; .venv\Scripts\python.exe -m pytest tests/test_integration_app.py tests/test_metrics.py -q  # 10 passed
.venv\Scripts\python.exe -m ruff check apps/backend_gateway/main.py apps/backend_gateway/tests/test_integration_app.py  # All checks passed
.venv\Scripts\python.exe -m mypy apps/backend_gateway --no-incremental  # Success (97 files)
cd apps/frontend; npm run lint   # No ESLint warnings or errors
cd apps/frontend; npm run typecheck  # OK
```

---

## ✅ #3 — Cơ chế "tin tức → giá" (2026-10-13)

**Thiếu hụt (P0):** tin tức (news) sinh ra từ AI Engine được persist vào bảng
`news` (kèm `sentiment` + `impact_score` + `simulated_at`) nhưng **không bao giờ ảnh
hưởng tới giá**: `_fetch_price_values` gọi Math Engine GBM với `mu=0.0` cứng. Người
dùng đọc tin P/E hay tin doanh nghiệp âm nhưng giá cứ GBM trần — vòng lõi sản phẩm
"tin tức → thị trường" không tồn tại.

**Thiết kế:** tin tức trong cửa sổ (ngày mô phỏng) bẻ drift GBM (`mu`) theo hướng
`sentiment × impact`, phân rã theo độ tuổi; `tanh` chặn mềm giữ momentum trong [-1, 1].
Không tin → momentum = 0 → `mu = 0.0` (hành vi cũ giữ nguyên).

**Sửa — `apps/backend_gateway/services/market_service.py`:**
- Hằng số: `_NEWS_WINDOW_SIM_DAYS = 7`, `_NEWS_HALF_LIFE_SIM_DAYS = 3.0`,
  `_NEWS_DRIFT_SCALE = 2.0` (mu annualized tối đa khi momentum bão hoà ±1).
- `_sentiment_sign(...)`: positive → +1, negative → -1, neutral/khác → 0.
- `_news_weight(sentiment, impact_score, age_seconds)`: hướng × (impact/10) ×
  `exp(-age_sim_days / HALF_LIFE)`; `age_sim_days = age_giây / REAL_SECONDS_PER_SIM_DAY`
  (60 giây thực = 1 ngày mô phỏng, tái dùng hằng số của `realtime.simtime`).
- `_aggregate_news_momentum(entries)`: `tanh(Σ weight)` chặn mềm — tràng tin cùng
  hướng bão hoà dần, không dính trần/sàn trong nhiều phiên.
- `_fetch_news_momentum_map(db, company_ids, contest_id)`: một truy vấn lấy tin trong
  cửa sổ → momentum mỗi công ty = **tin riêng của công ty + tin vĩ mô cùng scope**
  (macro = `company_id IS NULL` và `contest_id` khớp scope — contest không bị nhiễu bởi
  tin vĩ mô thị trường chính). Lọc `simulated_at <= sim_now()` chống look-ahead (tin
  chưa phát hành không dịch chuyển giá).
- `_fetch_price_values` / `_fallback_price` / `_fetch_price` thêm tham số `mu`
  (mặc định 0.0, tương thích ngược) — fallback GBM nội bộ cũng dùng mu cho nhất quán.
- `update_all_prices`: tính `math.tanh`-momentum một lần cho cả lượt rồi truyền
  `mu = _NEWS_DRIFT_SCALE × momentum` vào từng công ty (kể cả scope contest).
- `update_company_price`: truyền `mu` tương tự cho cập nhật đơn lẻ.

**Đánh đổi:** `mu` là drift annualized; với `dt = 1/252` mỗi nhịp ≈ 1 phiên, một tin
impact-8 mới sẽ dịch kỳ vọng ~0.5% mỗi phiên và tàn phai sau vài ngày sim — đủ để
người dùng thấy "tin kéo giá", không đủ làm GBM mất ý nghĩa. Math Engine đã nhận `mu`
per-request (không đổi engine).

**Test (mới 13 ca — `apps/backend_gateway/tests/test_news_price.py`):**
- sign: positive/negative/neutral/hoa/thiếu → đúng hướng.
- momentum: rỗng = 0; positive > 0; negative < 0; neutral = 0 (impact mạnh vẫn 0);
  tin cũ (5 ngày sim) phân rã nhỏ hơn tin mới; nhiều tin cùng hướng bão hoà < 1.
- map (fake db): tin riêng + macro scope gộp đúng `tanh`; công ty ngoài set bị bỏ qua;
  không tin → `{}`.
- lan truyền `mu`: `_fetch_price_values` chuyển `mu` đúng cho Math Engine; fallback
  nội bộ nhận đúng `mu`; `_fetch_price` (đường đơn) chuyển `mu` + `reference_price`.

**Kiểm chứng:**
```
cd apps/backend_gateway; .venv\Scripts\python.exe -m pytest -q   # 339 passed, 2 failed (đỏ sẵn có)
cd apps/backend_gateway; .venv\Scripts\python.exe -m pytest tests/test_news_price.py tests/test_market_service.py -q  # 17 passed
.venv\Scripts\python.exe -m mypy apps/backend_gateway --no-incremental   # Success (97 files)
<lệnh ruff đúng như CI>                                                      # All checks passed
```

---

## ✅ #8 — Frontend bịa giá và lịch sử giá (2026-10-13)

**Vấn đề (P0):** UI tin vào **giá tự sinh phía client**:
- `PriceChart.tsx` fallback vẽ **90 ngày OHLC giả** bằng `generateHistoricalPrices` khi chưa có
  tick (nến nhìn "đầy đủ" nhưng không tồn tại — gây nhầm là có lịch sử thật).
- `usePriceStream.ts` tự ý **bịa tick**: (a) demo mode dùng `nextSimulatedPrice` + polling, và
  (b) khi WebSocket im lặng quá ngưỡng thì "mô phỏng tiếp" giá từ tick cuối + `computeChange`.

**Sửa — dữ liệu chỉ từ backend, không còn mã sinh giá phía client:**
- Xoá hẳn `apps/frontend/src/utils/priceSimulator.ts` (`generateHistoricalPrices`,
  `nextSimulatedPrice`, `computeChange` + helper RNG) — không còn chỗ nào dùng.
- `usePriceStream.ts` viết lại: `snapshot` chỉ được set bởi **tick thật** qua WS
  (`price_tick`/`price_snapshot`); bỏ toàn bộ nhánh simulation-fallback, bỏ ref
  `baseReady/simBase/simStep/lastLive/lastSimulated`; thêm trường `source:
  "live" | "poll" | "none"`.
  - Demo mode: backend Apps Script **không có WebSocket** → poll REST `/companies` lấy
    `current_price` **thật** (backend demo tự mô phỏng giá phía máy chủ), chu kỳ `DEMO_POLL_MS
    = 5000` để không hụt quota Apps Script; `source = "poll"` và snapshot không chứa tick.
  - Chưa có dữ liệu thật → `snapshot = null` (UI hiện "Chờ dữ liệu giá real-time…").
- `PriceChart.tsx`: `candles = buildCandles(ticks, bucketSeconds)` — nến **chỉ từ tick thật**;
  thêm `noCandlesNotice` cho trường hợp "có giá nhưng chưa đủ tick vẽ nến".
- `trade/page.tsx`: nhãn **Live** chỉ hiện khi `source === "live"`; demo hiện nhãn **Demo**
  (thay vì nhấp nháy "Live"); truyền `noCandlesNotice` theo mode.

**Kiểm chứng (frontend):**
```
cd apps/frontend; npm run typecheck     # ✔
cd apps/frontend; npm run lint          # ✔ No ESLint warnings or errors
cd apps/frontend; npm run test:unit     # 13 passed (bỏ 3 test priceSimulator)
```

---

## Ghi chú kiểm thử (quan trọng, tránh nhầm nhân quả)

Tại thời điểm 2026-10-13, chạy toàn bộ suite backend có **2 test đỏ sẵn có** (không liên quan
đến các sửa lỗi trong file này — đã xác nhận bằng `git stash`):

- `tests/test_corporate_asof.py::test_apply_due_does_not_touch_future_event`
- `tests/test_tasks_api.py::test_list_tasks_contract` (schema task trả thêm `next_reset_at`,
  test chưa cập nhật)

**Lưu ý:** ngoài 2 test đỏ trên, từng có 1 test **flaky** sẵn có
(`test_market_service.py::test_fetch_price_values_falls_back_when_unavailable`, RNG không
seed) đã được **sửa** ở #9 (seed cố định) — không còn tính vào số đỏ.

Kết quả toàn suite backend sau #4: **301 passed, 2 failed (đỏ sẵn có)**. Sau #9 + sửa flaky:
**302 passed, 2 failed (đỏ sẵn có), 3 warnings**. Sau #10: **304 passed, 2 failed (đỏ sẵn có)**.
Sau #11: **306 passed, 2 failed (đỏ sẵn có)**. Sau #12: **312 passed, 2 failed (đỏ sẵn có)**.
Sau #14: **319 passed, 2 failed (đỏ sẵn có)**. Sau #15: **324 passed, 2 failed (đỏ sẵn có)**.
Sau #16: **326 passed, 2 failed (đỏ sẵn có)**. Sau #3: **339 passed, 2 failed (đỏ sẵn có)**.
Math Engine: **110 passed** (sau #6 là 106). AI Engine: **178 passed** (sau #13 là 178).
Frontend: **13 unit test passed** (node:test) — sau #8 là 13 (sau #15 là 16; bỏ 3 test priceSimulator).
mypy strict: 4/4 target xanh (đã baseline nợ cũ).
