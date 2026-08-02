Hãy đóng vai một Chuyên gia Senior Full-Stack & DevOps Engineer. Tôi cần bạn thực hiện một đợt Dọn dẹp Codebase (Code Clean-up) & Kiểm tra độ sẵn sàng Deploy (Pre-deployment Audit) cho toàn bộ dự án Monorepo "FinSimAI" trước khi tôi đưa ứng dụng lên môi trường Production (Vercel cho Frontend & Render/Docker cho Backend).

Dưới đây là cấu trúc dự án và danh sách kiểm tra chi tiết công việc bạn cần làm:

---

### 1. CẤU TRÚC DỰ ÁN (FinSimAI Monorepo)
- Apps:
  + apps/frontend (Next.js 14, TypeScript, TailwindCSS, Zustand)
  + apps/backend_gateway (FastAPI Python, Realtime WebSocket, SQLAlchemy/Alembic)
  + apps/ai_engine (Python, Agents, Gemini Integrations)
  + apps/math_engine (Python, gRPC Server)
- Packages & Configs:
  + packages/database, packages/shared-types, packages/proto
  + turbo.json, pyproject.toml, package.json, docker-compose.yml

---

### 2. NHIỆM VỤ DỌN DẸP VÀ CHUẨN HÓA (Thực hiện từng bước)

PHẦN A: BẢO MẬT & BẢO MẬT BIẾN MÔI TRƯỜNG (SECURITY & SECRETS)
1. Rà soát toàn bộ dự án (đặc biệt trong apps/ai_engine/prompts, apps/backend_gateway/core, apps/frontend/src):
   - Xóa bỏ hoặc cảnh báo nếu có bất kỳ API Key, Password, Secret Token hoặc URL Database bị hardcode cứng trong file code/config.
   - Kiểm tra file .gitignore: Đảm bảo đã chặn các file nhạy cảm (.env, .env.local, .turbo, __pycache__, node_modules, build outputs).
   - Kiểm tra file `.env.example` ở cả thư mục gốc và `apps/frontend/.env.example`: Đảm bảo liệt kê đầy đủ tất cả các biến môi trường cần thiết mà không chứa giá trị thực.

PHẦN B: DỌN DẸP CODE VÀ ĐẠO ĐỨC LẬP TRÌNH (CODE CLEAN-UP & DEAD CODE)
1. Thư mục Frontend (apps/frontend):
   - Xóa bỏ toàn bộ các câu lệnh `console.log`, `console.error` thừa hoặc comment rác dùng cho mục đích debug cá nhân (chỉ giữ lại logger chuẩn nếu có).
   - Xóa các `import` thừa không sử dụng (Unused Imports) và file/component rác không được gọi.
   - Kiểm tra TypeScript Type: Đảm bảo không còn bất kỳ lỗi Type (`any` không rõ ràng hoặc type mismatch) có thể gây dừng tiến trình `next build`.
2. Thư mục Backend Python (apps/backend_gateway, ai_engine, math_engine):
   - Thay thế các lệnh `print()` thừa bằng hệ thống Logging chuẩn của Python.
   - Xóa bỏ các hàm/file thử nghiệm không dùng tới trong thư mục `tests/` hoặc `tools/`.

PHẦN C: CẤU HÌNH KẾT NỐI BROWSERS & CROSS-ORIGIN (CORS & WEBSOCKET)
1. Kiểm tra CORS tại Backend (`apps/backend_gateway/core/middleware.py` hoặc `main.py`):
   - Đảm bảo `CORSMiddleware` chấp nhận domain Production từ Vercel (`https://*.vercel.app`) hoặc cấu hình linh hoạt cho phép API call từ môi trường Cloud.
2. Kiểm tra kết nối Frontend (`apps/frontend/src/services/api.ts` & `hooks/useWebSocket.ts`):
   - Đảm bảo toàn bộ các đường dẫn API HTTP đều dùng `process.env.NEXT_PUBLIC_API_URL`.
   - Đảm bảo các kết nối WebSocket đều chuyển đổi linh hoạt protocol giữa `ws://` (Local) và `wss://` (Production HTTPS) dựa trên `process.env.NEXT_PUBLIC_WS_URL`.

PHẦN D: KIỂM TRA BUILD VÀ TỰ ĐỘNG HÓA (BUILD & DEPLOYMENT CHECK)
1. Kiểm tra file `turbo.json` & `package.json` ở root:
   - Đảm bảo câu lệnh `npm run build` hoặc `turbo run build` chạy thành công mà không bị gãy giữa chừng.
2. Kiểm tra file cấu hình Deploy (`apps/backend_gateway/Dockerfile`, `render.yaml`):
   - Đảm bảo đường dẫn `COPY` trong Dockerfile / render.yaml khớp chính xác với cấu trúc thư mục Monorepo khi Render thực hiện build context từ repo root.

---

### 3. ĐẦU RA YÊU CẦU

Hãy tiến hành quét dự án, chỉnh sửa trực tiếp các file cần dọn dẹp hoặc liệt kê cho tôi danh sách:
1. Các file đã được dọn dẹp (Xóa console.log, import thừa, fix bug).
2. Các file cấu hình biến môi trường đã chuẩn hóa (.env.example).
3. Các câu lệnh Terminal tôi cần chạy để kiểm tra lại Build toàn bộ hệ thống (`turbo build`, `tsc`, `pytest`).