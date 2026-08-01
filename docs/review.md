# Báo cáo review hệ thống

Ngày kiểm tra: 2026-08-01

## Tổng kết
- Các module backend, AI engine và math engine riêng lẻ đều có test pass khi chạy riêng từng module.
- Tuy nhiên, hệ thống vẫn còn một số lỗi/issue cần lưu ý, bao gồm lỗi test infrastructure, cảnh báo lint/code quality và mộ
t vấn đề diagnostics trong frontend.

## Các lỗi đã xác nhận

### 1. Test suite tổng hợp bị lỗi do vấn đề async test infrastructure
- Thực hiện lệnh:
  - .\.venv\Scripts\python.exe -m pytest apps/backend_gateway/tests apps/ai_engine/tests apps/math_engine/tests -q
- Kết quả:
  - Nhiều test thất bại với lỗi: "async def functions are not natively supported"
  - Một số test khác báo lỗi từ pytest-asyncio setup: "AssertionError" trong quá trình khởi tạo fixture async.
- Đây là lỗi ở môi trường test/plug-in, không phải lỗi business logic đơn lẻ.

### 2. Frontend có diagnostic lỗi từ editor
- File: apps/frontend/src/components/common/AuthProvider.tsx
- Vấn đề: component props bị báo lỗi "Mark the props of the component as read-only."
- Đây là một lỗi/static analysis rõ ràng trong frontend code.

### 3. Ruff phát hiện nhiều vấn đề code quality / lint
- Backend:
  - apps/backend_gateway/api/v1/companies.py: import không dùng (re)
  - apps/backend_gateway/api/v1/social.py: import block không đúng định dạng/thứ tự
  - apps/backend_gateway/core/security.py: import không dùng
  - apps/backend_gateway/services/market_service.py: so sánh với True thay vì dùng giá trị boolean trực tiếp; dòng quá dài vượt quá giới hạn 100 ký tự
- Math engine:
  - apps/math_engine/engine/penalty_calc/__init__.py: import block và thứ tự __all__ chưa đúng
  - apps/math_engine/engine/portfolio/__init__.py: import block và thứ tự __all__ chưa đúng
  - apps/math_engine/engine/pricing/price_generator.py: import block chưa đúng thứ tự
  - apps/math_engine/engine/time_compression/__init__.py: import block và __all__ cần sắp xếp lại
- Những lỗi này không làm crash hệ thống ngay nhưng làm code khó duy trì và tăng rủi ro phát sinh vấn đề sau này.

### 4. Frontend build có warning liên quan đến path/TypeScript resolution
- Thực hiện lệnh:
  - cd apps/frontend && npx next build
- Kết quả:
  - Build vẫn tiếp tục nhưng xuất hiện warning từ webpack về việc resolve TypeScript path "typescript/lib/typescript" với mismatch về case/path.
- Warning này cho thấy có vấn đề về môi trường hoặc cấu hình dependency resolution trong build pipeline.
