# 🚀 Hướng dẫn Deploy FinSimAI — Vercel (Frontend) + Render (Backend)

> Tài liệu này chỉ dẫn **4 bước thao tác trên Dashboard** — phần cấu hình code
> (build, migration, health check, CORS) đã được tự động hoá trong repo:
>
> - `vercel.json` (root + `apps/frontend/vercel.json`) → Vercel tự nhận diện
>   Root Directory, Install Command, Build Command.
> - `render.yaml` → khai báo sẵn 4 service (math-engine, ai-engine-worker,
>   ai-engine-api, backend-gateway) với đúng `dockerContext` monorepo.
> - `backend_gateway` chạy **`alembic upgrade head` tự động lúc khởi động**
>   (`run_migrations.py`) trước khi bật server.
> - Health check: `/health/live` (backend_gateway & ai-engine-api), `/health`,
>   `/health/ready`.

---

## ✅ Bước 1 — Tạo PostgreSQL miễn phí

### Lựa chọn A: Supabase (khuyên dùng — ổn định, free lâu dài)
1. Tạo tài khoản/truy cập [supabase.com](https://supabase.com) → **New Project**.
2. Vào **Project Settings → Database → Connection string**.
3. Lấy 3 biến từ connection string (thay `[YOUR-PASSWORD]` bằng mật khẩu DB,
   nhớ **URL-encode** mật khẩu nếu chứa ký tự đặc biệt: `@` → `%40`, `#` → `%23`):

| Biến môi trường   | Giá trị (ví dụ) |
|---|---|
| `DATABASE_URL` (async, cho app) | `postgresql+asyncpg://postgres.xlvffuabc:${PW}@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres` |
| `DATABASE_URL_SYNC` (sync, cho Alembic) | `postgresql://postgres.xlvffuabc:${PW}@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres` |

> ⚠️ **DB phải TRỐNG** — đừng chạy `schema.sql` trước. Alembic tự tạo toàn bộ
> schema khi backend-gateway khởi động lần đầu.

### Lựa chọn B: Render PostgreSQL (free, nhanh nhưng **hết hạn sau 30 ngày**)
1. Render Dashboard → **New → PostgreSQL** → chọn region **Oregon** (cùng region services).
2. Sau khi tạo, copy **Internal Database URL**:
   - `DATABASE_URL_SYNC` = chuỗi `postgresql://...` gốc.
   - `DATABASE_URL` = cùng chuỗi đó, đổi scheme `postgresql://` → `postgresql+asyncpg://`.

---

## ✅ Bước 2 — Tạo Redis miễn phí trên Upstash

1. [upstash.com](https://upstash.com) → **Create Database**.
2. Region chọn gần Render nhất (Oregon / `us-west-1`) để giảm latency.
3. Copy **REST URL** dạng:
   ```
   redis://default:AVNS_xxxx@us-west-1-xxxx.upstash.io:6379
   ```
   (nếu có tùy chọn TLS, chọn bản **không TLS** `redis://` — app dùng driver redis sync).

> Dùng chung `REDIS_URL` cho cả 3 service cần Redis (backend-gateway,
> ai-engine-worker, ai-engine-api).

---

## ✅ Bước 3 — Render Dashboard: tạo 4 service + điền Env Vars

1. Render Dashboard → **New → Blueprint Instance** → connect repo FinSimAI.
   Render đọc `render.yaml` và tạo sẵn 4 service (tự nạp `dockerContext: .`).
2. Chờ build xong, vào **từng service → Environment** và điền các biến `sync: false`:

### 🔹 backend-gateway (Web Service)
| Env Var | Giá trị |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` (Bước 1) |
| `DATABASE_URL_SYNC` | `postgresql://...` (Bước 1) |
| `REDIS_URL` | `redis://...` (Bước 2) |
| `JWT_SECRET` | chuỗi ngẫu nhiên ≥ 32 ký tự (vd: `openssl rand -hex 32`) |
| `CORS_ORIGINS` | `https://finsimai.vercel.app,https://www.finsimai.vercel.app` |
| `FRONTEND_URL` | `https://finsimai.vercel.app` |
| `AI_ENGINE_URL` | `https://ai-engine-api.onrender.com` |

*(Đã set sẵn trong render.yaml: `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=60`,
`ENVIRONMENT=production`, `DEBUG=false`, `MATH_ENGINE_GRPC_HOST=math-engine`.)*

### 🔹 ai-engine-worker (Background Worker) & ai-engine-api (Web Service)
| Env Var | Giá trị |
|---|---|
| `REDIS_URL` | `redis://...` (Bước 2) |
| `GEMINI_API_KEY` | key Google AI Studio |

### 🔹 math-engine (Private Service)
- Không cần env. Backend-gateway gọi qua host nội bộ `math-engine:50051`.

> **Kiểm tra:** sau khi backend-gateway lên, migration tự chạy (xem log có dòng
> *"Migration database hoàn tất"*). Health check Render dùng `/health/live`
> (không phụ thuộc DB → tránh vòng lặp restart khi DB chưa sẵn sàng).

---

## ✅ Bước 4 — Vercel Dashboard: deploy Frontend

1. Vercel → **Add New Project** → Import repo FinSimAI.
2. Vercel đọc `vercel.json` và tự đặt:
   - **Root Directory** = `apps/frontend`
   - **Install Command** = `npm install`
   - **Build Command** = `npm run build` (→ `next build`)
   > Nếu Vercel dùng Framework Preset không tự đọc, chỉ cần đặt lại
   > Root Directory = `apps/frontend` trong Settings → General.
3. Vào **Settings → Environment Variables** thêm:
   | Env Var | Giá trị |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://backend-gateway.onrender.com` |
   | `NEXT_PUBLIC_WS_URL` | `wss://backend-gateway.onrender.com` |
4. **Deploy**. Nếu thiếu 2 biến trên, app vẫn build nhưng in **cảnh báo rõ ràng**
   ở console và fallback về `localhost:8000` (để tránh sai địa chỉ production).

> 💡 Gợi ý: tạo biến `NEXT_PUBLIC_*` cho cả **Production** lẫn **Preview**
> (Vercel Preview dùng domain `*.vercel.app`). Backend đã hỗ trợ sẵn
> `CORS_ORIGIN_REGEX=https://.*\.vercel\.app` để chấp nhận mọi bản preview.

---

## 🔍 Kiểm tra sau khi deploy

```bash
# Backend (thay URL bằng domain Render)
curl https://backend-gateway.onrender.com/health/live      # {"status":"ok",...}
curl https://backend-gateway.onrender.com/health/ready     # kiểm tra db/redis/math-engine
curl https://backend-gateway.onrender.com/health           # alias của /health/ready

# Frontend
curl -I https://finsimai.vercel.app
```

Gỡ rối nhanh:
- **Backend 503 / Restart loop** → xem **Logs** của service; thường do
  `DATABASE_URL`/`REDIS_URL` sai hoặc CORS chưa gồm domain Vercel.
- **Migration không chạy** → kiểm tra `DATABASE_URL_SYNC` đã đặt đúng (sync DSN).
- **Free tier** → service ngủ sau ~15 phút không truy cập, cold start 30–60s.
  Muốn giữ ấm: chạy cron ping `/health/live` mỗi 5 phút (UptimeRobot / GitHub Action).

---

## 📦 Nguồn tham khảo

- Env mẫu đầy đủ: `.env.production.example` (root).
- Blueprint Render: `render.yaml`.  Cấu hình Vercel: `vercel.json` + `apps/frontend/vercel.json`.
- Auto-migration: `apps/backend_gateway/run_migrations.py` (gọi trong `main.py` lifespan).
- Schema/migrations: `packages/database/migrations` (Alembic), seed: `scripts/seed_db.py`.
