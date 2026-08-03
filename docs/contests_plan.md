# Kế hoạch: Hệ thống cuộc thi (Contests) & Phân quyền Admin/Host

> Mục tiêu: biến FinSimAI từ "một sàn mô phỏng duy nhất" thành "nền tảng đa cuộc thi".
> Mỗi Host tạo được một cuộc thi = một bản web thu nhỏ (tin tức, bài viết, danh sách công ty, bảng giá...)
> thông qua **form/UI trên web, KHÔNG cần viết code**. Admin là người duy nhất quản trị toàn hệ thống.

---

## 1. Yêu cầu & phạm vi (được đánh giá nghiêm khắc)

### 1.1 Yêu cầu chức năng (hợp đồng — vi phạm là bug)
| ID | Yêu cầu | Tiêu chí chấp nhận |
|----|---------|--------------------|
| FR-1 | Đúng 1 Admin toàn hệ thống | Có biến cấu hình chỉ định admin (e.g. `ADMIN_EMAILS`). Người không trong danh sách không bao giờ nhận role `admin`. |
| FR-2 | Admin thấy toàn bộ users/news/posts/companies của **mọi cuộc thi** | Các endpoint `/api/v1/admin/*` trả về đủ dữ liệu, có phân trang. Không bị lọc theo contest. |
| FR-3 | Admin cấp/thu hồi quyền `host` | Chỉ admin mới gọi được `POST /admin/users/{id}/role`. Không host nào tự nâng quyền. |
| FR-4 | Host tạo cuộc thi bằng cách **chọn vài lựa chọn trên web**, hệ thống tự sinh dữ liệu | Host chỉ chọn: khuôn, lĩnh vực, số công ty, độ khó, bật/tắt tự sinh tin & social. Hệ thống tự phân tích và chạy dữ liệu tạo công ty/tin/bài viết/giá. Không nhập nội dung tay, không chạy script, không sửa file. |
| FR-5 | Cuộc thi là bản web thu nhỏ độc lập | Mỗi contest có danh sách công ty, tin tức, bài viết, bảng giá **riêng**. Người dùng chỉ thấy nội dung của contest mình tham gia. |
| FR-6 | User tham gia contest | Flow mời/đăng ký contest, tách biệt tài khoản (cùng 1 user có thể chơi nhiều contest với portfolio riêng). |
| FR-7 | Toàn bộ hoạt động qua web UI | Admin + Host không cần terminal. API dựng sẵn là nền cho UI. |
| FR-8 | **1 form đăng nhập chung cho mọi role** | Admin/Host/User cùng đăng nhập ở trang `/login` hiện tại. Không có trang đăng nhập riêng cho admin. Sau khi đăng nhập, hệ thống tự điều hướng theo role. |
| FR-9 | **Giao diện riêng theo role** | Admin → giao diện quản trị riêng; Host → giao diện host (có thêm màn tạo cuộc thi); User → giao diện sàn giao dịch như hiện tại. 3 giao diện tách biệt, không trộn. |
| FR-10 | **Admin dùng giao diện riêng, KHÔNG giao dịch trên sàn** | Admin không cần xem dashboard giao dịch; giao diện admin chỉ phục vụ quản trị (users/contests/nội dung toàn cục). |

### 1.2 Yêu cầu phi chức năng
- **NFR-1 Không phá vỡ luồng hiện tại**: mọi endpoint public hiện có vẫn hoạt động với contest mặc định ("thị trường chính").
- **NFR-2 Đơn giản**: tổng số bảng mới ≤ 4, không đụng schema của orders/transactions/portfolios.
- **NFR-3 An toàn**: mọi endpoint viết mới đều có `require_roles`, kiểm tra bằng test + review.
- **NFR-4 Không trùng lặp logic**: CRUD content dùng chung 1 service, không copy-paste giữa admin/host/public.

---

## 2. Thiết kế dữ liệu (Migration `0005`)

> Nguyên tắc: **contest_id nullable** — dữ liệu hiện có (cột NULL) thuộc "thị trường chính" (main market),
> được biểu diễn như một contest mặc định ảo. Không cần backfill dữ liệu.

### 2.1 Role
- `users.role` hiện là `String(20)` (mặc định `'user'`). Thêm giá trị `'host'`.
- Giá trị hợp lệ: `user | host | admin`. Kẻ ra ngay sau này muốn thêm (bot) — giữ nguyên như cũ.

### 2.2 Bảng mới
```text
contests
  id            UUID PK (gen_random_uuid)
  slug          String(60) UNIQUE            -- URL định danh, host tự đặt
  name          String(200) NOT NULL
  description   Text NULL
  status        String(20) DEFAULT 'draft'   -- draft | active | ended
  config        JSONB NOT NULL DEFAULT '{}'  -- khuôn (template) — xem §4
  owner_id      UUID FK users.id (SET NULL)  -- host sở hữu
  starts_at     DateTime(tz) NULL
  ends_at       DateTime(tz) NULL
  is_active     Bool DEFAULT true
  created_at / updated_at

contest_members
  id            UUID PK
  contest_id    UUID FK contests.id (CASCADE)
  user_id       UUID FK users.id (CASCADE)
  joined_at     DateTime(tz) DEFAULT now()
  UNIQUE (contest_id, user_id)

contest_portfolios   -- BẢNG ẨN: không tạo. Dùng lại portfolios hiện có.
```
**Quyết định (đã chốt):** KHÔNG tạo bảng portfolio riêng cho contest. Thêm cột `contest_id` vào `portfolios` để lọc. (Xem §3.4)

### 2.3 Thêm cột `contest_id` vào các bảng nội dung
| Bảng | Cột mới | Giá trị NULL nghĩa là |
|------|---------|------------------------|
| `companies` | `contest_id` UUID NULL, FK contests (CASCADE), + index `(contest_id, symbol)` | thị trường chính |
| `news` | `contest_id` UUID NULL, FK contests (CASCADE), + index `(contest_id, company_id, simulated_at)` | thị trường chính |
| `social_posts` | `contest_id` UUID NULL, FK contests (CASCADE) | thị trường chính |
| `portfolios` | `contest_id` UUID NULL, FK contests (CASCADE), + index `(user_id, contest_id)` | thị trường chính |

- `Company.symbol` UNIQUE toàn cục sẽ xung đột giữa 2 contest. **Đã chốt:** bỏ unique toàn cục, thay bằng **partial unique index `(contest_id, symbol) WHERE contest_id IS NOT NULL`** + giữ unique hiện có cho dòng NULL (2 contest dùng chung symbol được, cùng contest thì không). Cách làm: drop constraint unique cũ, tạo 2 partial index (đảm bảo dữ liệu hiện có không trùng trước khi drop).
- `orders` / `transactions` / `knowledge` / `trap_events`: **giữ nguyên**. Truy vết theo portfolio → portfolio đã có contest_id.

### 2.4 Migration
- File mới `packages/database/migrations/versions/0005_contests_and_roles.py`.
- `downgrade`: drop `contest_id` columns + drop `contests`, `contest_members`; xoá giá trị `'host'` không cần thiết.
- Sau khi chạy: `scripts/generate_ts_types.py` sẽ tự lấy schema mới từ Pydantic (thêm module `contest`, `admin` vào `SCHEMA_MODULES`).

---

## 3. Backend

### 3.1 Phân quyền (nền tảng)
- `core/dependencies.py`: thêm `require_roles(*roles: str)` → trả về dependency trả `User` và ném `403` nếu `user.role not in roles`.
  ```python
  def require_roles(*roles):
      async def _dep(user: User = Depends(get_current_user)) -> User:
          if user.role not in roles:
              raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này")
          return user
      return _dep
  ```
- `core/config.py`: thêm `admin_emails: list[str]` (parse từ env `ADMIN_EMAILS`, mặc định `[]`).
- **Admin chỉ định 2 chiều**: (1) migration 0005 `INSERT` admin user nếu email nằm trong config; (2) `require_roles('admin')` đồng thời kiểm tra email thuộc `settings.admin_emails` — để tụt role admin khi đổi config (defense in depth).
- Sinh token sau đăng nhập: không thay đổi. Role đọc live từ DB ở mỗi request (đã đúng cách — `get_current_user` query DB mỗi lần).

### 3.2 Module `api/v1/admin/*` — chỉ admin
Router prefix `/admin`, dependency `require_roles("admin")` cấp router:
- `GET  /admin/users` — toàn bộ user, filter `role`, `search`, phân trang.
- `PATCH /admin/users/{id}/role` — body `{role: "user"|"host"|"admin"}`. Chỉ nhận role nằm trong `ADMIN_EMAILS` (nếu role=admin). Không cho tự sửa role của chính mình.
- `PATCH /admin/users/{id}/status` — khóa/mở khóa (`is_active`).
- `GET  /admin/contests` — danh sách contest + số member.
- `PATCH /admin/contests/{id}/status` — chuyển `active`/`ended`/`draft` (admin can can thiệp mọi contest).
- `GET  /admin/news`, `GET /admin/social-posts`, `GET /admin/companies` — view toàn cục (không lọc contest), có `?contest_id` để lọc nếu muốn.

### 3.3 Module `api/v1/contests/*` — host & user
- `POST /contests` — `require_roles("host","admin")`: tạo contest từ **vài lựa chọn** (template, tên/slug, lĩnh vực, số công ty, độ khó, auto_news/auto_social, theme). Sinh slug tự động nếu bỏ trống.
- `POST /contests/{slug}/activate` — host sở hữu (hoặc admin): chạy **pipeline tự sinh** §4.3 rồi chuyển `status='active'` (giá bắt đầu chạy, nhận user join). Đây là bước "hệ thống tự phân tích và chạy dữ liệu".
- `GET  /contests` — public có auth: liệt kê contest `active` (host thấy thêm contest của mình kể cả `draft`).
- `GET  /contests/{slug}` — chi tiết + config đã parse.
- `PATCH /contests/{slug}` — host sở hữu (hoặc admin): sửa thông tin + config.
- `DELETE /contests/{slug}` — chỉ host sở hữu: xóa mềm (`status='ended'`, không hard-delete).
- `POST /contests/{slug}/join` — user tham gia (tạo `contest_members`, kiểm tra chưa join + contest `active`).
- Host nội dung (tùy chọn, khi cần tinh chỉnh sau khi tự sinh) — `require_roles("host","admin")` + xác minh `owner_id == user.id` (hoặc admin):
  - `POST/GET /contests/{slug}/companies`
  - `POST/GET /contests/{slug}/news`
  - `POST/GET /contests/{slug}/social-posts`
  - `POST/GET /contests/{slug}/articles` — **bài viết** (`is_ai_generated=False`, host tự viết, đính kèm vào contest).

### 3.4 Tách thị trường khi giao dịch
- Hiện `trades` dùng `company.symbol` để lookup. Đổi lookup sang `(contest_id, symbol)` khi user chơi trong contest.
- Xác định contest của user: qua `contest_portfolios` — user chọn contest khi vào sàn (UI), backend xác minh membership rồi thao tác trên portfolio thuộc `(user_id, contest_id)` đó.
- `orders`/`transactions` gắn `portfolio_id` → vốn đã cô lập. Không thay đổi schema giao dịch.

### 3.5 Realtime & sinh giá
- `realtime/price_ws.py` hiện broadcast `prices:{SYMBOL}`. Khi contest chơi, room phải thành `prices:{contest_id}:{SYMBOL}` để 2 contest có cùng symbol không nhiễu.
- `services/market_service.py` (`update_all_prices`): chạy theo từng contest (lọc `companies.contest_id`), gọi `math_client` cho từng nhóm. Contest `draft`/`ended` không sinh giá.
- News/social sinh AI (`apps/ai_engine/tasks/scenario_tasks.py`): thêm tham số `contest_id`, fallback deterministic giữ nguyên. Contest draft có thể sinh "bản nháp" trước khi publish.

---

## 4. "Khuôn" (Template) tạo cuộc thi — phần lõi, không code

### 4.1 Ý tưởng — Host chỉ cần chọn 1 số lựa chọn
Host KHÔNG cần nhập danh sách công ty, tin tức, hay bài viết. Host chỉ **chọn vài lựa chọn trên web**,
hệ thống **tự phân tích và chạy dữ liệu** để sinh ra toàn bộ cuộc thi:
```jsonc
// contests.config  (JSONB) — host chỉ điền phần này
{
  "template": "tech_news",                    // 1 trong các khuôn có sẵn (§4.2)
  "theme": { "primary_color": "#0ea5e9", "logo_url": "..." },   // tùy chọn thẩm mỹ
  "industry": "công nghệ",                    // lĩnh vực host muốn
  "company_count": 8,                         // số công ty (hệ thống tự chọn/sinh)
  "difficulty": "normal",                     // easy | normal | hard → volatility, cooldown, start_cash
  "auto_news": true,                          // tự sinh tin tức + bài viết
  "auto_social": true                         // tự sinh bài đăng mạng xã hội
}
```
- `config` validate bằng Pydantic schema (`schemas/contest.py`) → lỗi form rõ ràng ngay trên UI.
- Toàn bộ phần `content` (companies/news/articles/social/price_seed) do **hệ thống tự điền** khi host bấm "Kích hoạt" — xem §4.3.

### 4.2 Template có sẵn (hardcode trong `schemas/contest.py`)
| Template | Mô tả | Hệ thống tự làm |
|----------|-------|-----------------|
| `classic` | Mặc định, giống thị trường chính | sinh công ty + giá auto + tin tự động |
| `tech_news` | Trọng tâm tin tức & bài viết | sinh ít social, nhiều news/articles về lĩnh vực đã chọn |
| `fast_paced` | Giá biến động mạnh, cooldown ngắn | difficulty cao → volatility cao, rules khác |
| `micro` | Cuộc thi nhỏ gọn, nhanh | ít công ty (3–5), thời gian ngắn |

- Mỗi template định nghĩa **mặc định**: số công ty, tỷ lệ news/social, volatility, quy tắc giao dịch, thời gian.
- Host chỉ đổi lựa chọn mình muốn (lĩnh vực, số công ty, độ khó), phần còn lại dùng mặc định.

### 4.3 Cơ chế "tự phân tích và chạy dữ liệu" (contest generator)
Khi host chọn xong và bấm kích hoạt, hệ thống chạy **một pipeline tự động**:

1. **Chọn công ty** — `services/contest_service.generate_content(contest)`:
   - Có sẵn dữ liệu mẫu công ty theo ngành trong seed (mở rộng `seed_db.py`); nếu lĩnh vực có dữ liệu → lọc ra `company_count` công ty phù hợp nhất.
   - Nếu không đủ → **tự sinh** symbol/name theo mẫu khuôn (`SCEN_` prefix + sector), tạo bản ghi `companies` với `contest_id`.
2. **Gieo giá ban đầu** — dùng `math_client`/`market_service`: `price_seed` sinh từ `industry` + `difficulty` (base_price, volatility). Giá bắt đầu chạy từ lúc `active`.
3. **Sinh nội dung** — tái dùng `apps/ai_engine/tasks/scenario_tasks.py` (tin + social, có fallback deterministic sẵn):
   - Truyền `contest_id` + `industry` làm ngữ cảnh → sinh tin tức, bài viết, bài đăng social riêng cho contest.
   - Nếu AI không khả dụng → fallback deterministic đảm bảo contest vẫn có nội dung.
4. **Lưu config đã hoàn chỉnh** — `config.content` được điền xong và lưu lại JSONB (host có thể xem/sửa sau, không cần tạo lại).
5. **Bật realtime** — contest chuyển `active`, `market_service` bắt đầu cập nhật giá theo contest (room `prices:{contest_id}:{SYMBOL}`).

> Kết quả: host mất **chưa đầy 5 phút** — chọn khuôn + vài lựa chọn → hệ thống tự phân tích, chạy dữ liệu, tạo xong cuộc thi. Không nhập công ty, không viết nội dung, không đụng code.

### 4.4 Quy trình tạo contest (host, 100% trên web)
1. Vào **"Tạo cuộc thi"** ở giao diện host → chọn khuôn (template) + đặt tên/slug/logo/màu.
2. Chọn vài lựa chọn: **lĩnh vực, số công ty, độ khó, tự sinh tin/social** → `POST /contests`.
3. Bấm **"Kích hoạt"** → hệ thống chạy pipeline §4.3 (tự sinh công ty, giá, tin, bài viết, social).
4. "Xem trước" → xem bản web thu nhỏ của contest (không cần chạy thêm bước nào).
5. Contest `active`, nhận user join.
> Không có bước nào cần nhập nội dung tay, terminal, hay sửa file. Host chỉ chọn vài cái → hệ thống tự làm phần còn lại.

---

## 5. Frontend (Next.js, `apps/frontend`)

### 5.0 Đăng nhập & điều hướng theo role (FR-8, FR-9)
- **1 form đăng nhập chung** (trang `/login` hiện tại, không tạo trang riêng). Backend không đổi — `POST /auth/login` trả token, role đọc từ `UserResponse.role`.
- Sau khi đăng nhập, frontend **redirect theo role** (đặt trong `authStore.login()` hoặc một middleware guard):
  - `admin` → `/admin` (giao diện quản trị riêng).
  - `host` → `/host` (giao diện host, có màn tạo cuộc thi).
  - `user` → `/dashboard` (sàn giao dịch như hiện tại).
- Guard route: `(admin)` layout chỉ cho `role==='admin'`, `(host)` layout chỉ cho `role==='host'` — không đúng role thì redirect về trang của role mình hoặc `/login`.

### 5.1 Tách giao diện theo role (3 layout riêng)
Thay vì 1 dashboard chung, dùng Next.js route groups để tách hẳn:
```text
src/app/
  (dashboard)/          ← user: sàn giao dịch (hiện tại)
  (host)/               ← host: quản lý cuộc thi của mình
  (admin)/              ← admin: quản trị toàn hệ thống
  login/page.tsx        ← chung cho mọi role
```
- `(host)` và `(admin)` có **Sidebar/header riêng** (không dùng chung Sidebar sàn giao dịch của user).
- Host vẫn có thể vào trang public của contest để xem trước (nhưng quản lý ở giao diện host).

### 5.2 Trang theo từng giao diện
Giao diện `(admin)`:
- `admin/users/page.tsx` — bảng user + dropdown đổi role/khóa.
- `admin/contests/page.tsx` — mọi contest + đổi status.
- `admin/content/page.tsx` — tab news/posts/companies toàn cục (FR-2).

Giao diện `(host)`:
- `host/contests/page.tsx` — list contest của mình (status, số member, nút chỉnh sửa).
- `host/contests/new/page.tsx` — **contest-builder**: form theo template (§4), thao tác công ty/nội dung/xem trước/kích hoạt.

Giao diện `(dashboard)` (user — giữ nguyên):
- `contests/page.tsx` — public: browse + join.
- `contests/[slug]/page.tsx` — trang đích của một contest (theo theme từ config).
- Type: chạy `scripts/generate_ts_types.py` sau khi thêm schema `contest`, `admin` → `@finsim/shared-types`.

### 5.3 Auth store
- `authStore` đã lưu `user.role` → không đổi gì. Thêm logic redirect theo role trong `login()` + guard của từng route group.

---

## 6. Seed & cấu hình
- `apps/backend_gateway/seed_db.py` (boot-time): thêm seed idempotent — nếu không có contest nào → tự tạo 1 contest mẫu `classic` ("Thị trường chính ảo") bằng chính pipeline §4.3 để demo generator hoạt động.
- **Template hardcode trong `schemas/contest.py`** (quyết định đã chốt) — KHÔNG thêm bảng `contest_templates`. Migration 0005 chỉ tạo schema, không seed dữ liệu kinh doanh.

---

## 7. Kiểm thử & tiêu chí nghiệm thu

### 7.1 Kiểm thử bắt buộc (chạy trước khi coi là xong)
- `ruff check apps/backend_gateway` — sạch, kể cả lỗi E501/I001 cũ trong `seed_db.py` (đang tồn đọng, cần xử lý trong đợt này).
- `mypy apps/backend_gateway` — pass.
- Alembic: `upgrade head` + `downgrade -1` chạy sạch trên DB test.
- `scripts/generate_ts_types.py` sinh lại types không lỗi.

### 7.2 Testcase thủ công (kịch bản nghiệm thu)
1. Không ai ngoài `ADMIN_EMAILS` set được role admin (test API + bằng tay).
2. Host A không sửa được contest của Host B (403). Admin sửa được cả hai.
3. Hai contest cùng symbol `VNM` có giá/tin/portfolio độc lập, realtime không nhiễu.
4. User join contest → chỉ thấy content của contest đó, không thấy content contest khác.
5. Tạo contest hoàn toàn bằng UI, không nhập nội dung tay: chỉ chọn khuôn + lĩnh vực + số công ty + độ khó → bấm "Kích hoạt" → hệ thống tự sinh công ty/tin/giá, bảng giá chạy (FR-4).
6. User cũ (thị trường chính) vẫn giao dịch bình thường — không bị ảnh hưởng (NFR-1).
7. Login 1 form: đăng nhập bằng tài khoản admin → vào `/admin`; tài khoản host → vào `/host`; tài khoản user → vào `/dashboard` (FR-8, FR-9).
8. Admin không thấy menu sàn giao dịch; Host thấy nút "Tạo cuộc thi" ở giao diện host.
9. Bấm "Kích hoạt" 2 lần → contest chỉ generate 1 lần, không nhân đôi công ty/tin (idempotent).

### 7.3 Đánh giá nghiêm khắc — checklist review
- [ ] Không endpoint admin/host nào thiếu `require_roles`.
- [ ] Admin/Host/User đăng nhập chung 1 form `/login`; redirect đúng giao diện theo role (FR-8, FR-9).
- [ ] Admin không nhìn thấy/truy cập sàn giao dịch; Host quản lý contest qua giao diện host (có tạo cuộc thi).
- [ ] Không bảng mới nào dư (tối đa 2 bảng thực: `contests`, `contest_members`).
- [ ] `config` luôn qua Pydantic validate trước khi lưu.
- [ ] Không copy-paste CRUD giữa admin/host/public — dùng chung service + filter theo `contest_id`/role.
- [ ] Symbol unique không còn global — đã có partial index theo contest.
- [ ] Realtime room có namespace contest.
- [ ] `seed_db.py` idempotent — chạy lại không trùng dữ liệu.

---

## 8. Lộ trình triển khai (thứ tự commit)

| Phase | Nội dung | Deliverable |
|-------|----------|-------------|
| 0 | Sửa ruff tồn đọng `seed_db.py`; commit dọn dẹp đang staged | repo sạch, build pass |
| 1 | `core/dependencies.require_roles` + `ADMIN_EMAILS` config + test 403 | nền phân quyền |
| 2 | Migration 0005 (tables + `contest_id` columns + index) + downgrade | schema mới |
| 3 | `schemas/contest.py` (config + template) + `services/contest_service.py` + **generator §4.3** | lõi không code |
| 4 | `api/v1/contests.py` (CRUD + **activate/auto-generate** + join) + `api/v1/admin.py` | API |
| 5 | Scope `market_service` + `price_ws` theo contest | realtime |
| 6 | Frontend: 3 giao diện theo role + admin pages + host builder (chọn khuôn) + contests browse | UI |
| 7 | Seed mẫu + generate_ts_types + chạy checklist §7 | nghiệm thu |

## 9. Rủi ro & xử lý
- **Đổi unique symbol**: chạy migration trên DB thật phải kiểm tra dữ liệu trùng trước (script check rồi mới bọc transaction).
- **Admin duy nhất = single point of failure**: đưa `ADMIN_EMAILS` vào env của infra (deploy_guide.md), ghi rõ trong docs.
- **Phạm vi contest bị bỏ sót ở 1 endpoint**: về sau mọi query bảng nội dung phải qua `contest_service.get_contest_scope(user, slug)` — test checklist §7.2.3 bắt lỗi này.
- **Pipeline tự sinh thiếu dữ liệu**: nếu seed không có đủ công ty theo lĩnh vực → generator phải tự sinh symbol/name dựa trên khuôn (`SCEN_` prefix); validation chặn activate nếu không đủ công ty hoặc không có nguồn giá (cần ≥1 company + price_seed hợp lệ).
- **Auto-sinh bị trùng khi bấm kích hoạt 2 lần**: `activate` phải idempotent — nếu contest đã `active` hoặc đã generate content thì bỏ qua, không chạy pipeline lại.
