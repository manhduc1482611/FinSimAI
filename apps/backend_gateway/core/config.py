from pathlib import Path
from typing import Annotated, Union, cast

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    # Ưu tiên thư mục có `.env` thật sự (monorepo: apps/backend_gateway cũng có
    # pyproject.toml nhưng không có .env — nếu dừng ở đó sẽ bỏ qua `.env` root).
    for parent in current.parents:
        if (parent / ".env").exists():
            return parent
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent  # fallback harmless — pydantic-settings ignores missing .env


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://finsim:finsim_secret@localhost:5432/finsimai"
    database_url_sync: str = "postgresql://finsim:finsim_secret@localhost:5432/finsimai"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Refresh token: số ngày hiệu lực. Access token ngắn (60m) + refresh dài ngày
    # giúp user khỏi phải đăng nhập lại thường xuyên mà vẫn thu hồi được phiên.
    refresh_token_expire_days: int = 30
    # Chống brute-force đăng nhập: tối đa số lần thất bại trong cửa sổ (giây)
    # tính theo identifier (email/username) VÀ theo IP — cái nào vượt trước là chặn.
    login_rate_limit_max: int = 10
    login_rate_limit_window_seconds: int = 60
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    # Regex bổ sung cho origin — hữu ích với Vercel Preview (`https://*.vercel.app`)
    # hoặc nhiều môi trường cloud có subdomain thay đổi. Ví dụ:
    # CORS_ORIGIN_REGEX=https://.*\.vercel\.app
    cors_origin_regex: str | None = None
    environment: str = "development"
    debug: bool = False
    frontend_url: str = "http://localhost:3000"

    # Múi giờ của người dùng cho việc tính "ngày hôm nay" của nhiệm vụ hằng ngày
    # và chuỗi ngày (streak). Không dùng UTC để tránh reset lệch so với thói quen
    # của người dùng Việt Nam (check-in tối muộn vẫn tính cùng ngày).
    app_timezone: str = "Asia/Ho_Chi_Minh"

    math_engine_url: str = "http://localhost:8000"

    # ─── Mentor ────────────────────────────────────────────────────────────
    # AI Engine (ai-engine-api). Mentor mặc định chạy deterministic question-bank
    # (0 token Gemini); chỉ khi MENTOR_LLM_MODE=on VÀ AI_ENGINE_URL có giá trị mới
    # gọi Gemini — vẫn bị giới hạn lượt bởi token bucket phía ai_engine.
    ai_engine_url: str = ""
    mentor_llm_mode: str = "off"
    ai_engine_timeout_seconds: float = 25.0

    # Khoá nội bộ để service khác (AI Engine) ghi nội dung vào DB qua
    # ``/api/v1/ai/content``. Khi để trống endpoint bị khoá (403) — fail-closed.
    internal_api_key: str = ""

    health_check_timeout: float = 2.0

    # Admin toàn hệ thống — danh sách email được phép mang role "admin"
    # (env: ADMIN_EMAILS, phân tách bằng dấu phẩy). Kẻ ra ngoài danh sách này
    # không bao giờ được coi là admin, kể cả khi role trong DB bị set thủ công.
    admin_emails: Annotated[list[str], NoDecode] = []

    # Seed dữ liệu idempotent lúc boot (companies/knowledge/scenarios + mẫu news/social
    # khi bảng rỗng). Chạy trong mạng Render để reach được Postgres free-tier.
    seed_on_startup: bool = True

    # ─── WebSocket Real-time ────────────────────────────────────────
    ws_price_tick_seconds: float = 2.0
    # Chu kỳ ticker thị trường mô phỏng (giây): mỗi nhịp dịch chuyển giá qua
    # Math Engine rồi khớp lệnh pending/partially_filled. Chỉ leader chạy.
    ws_market_tick_seconds: float = 3.0
    ws_trade_poll_seconds: float = 1.0
    ws_heartbeat_seconds: float = 30.0
    ws_max_queue_size: int = 256
    # Timeout cứng (giây) cho mỗi lần ghi dữ liệu ra socket WebSocket. Chống
    # Slowloris / TCP zero-window: ``send_text`` có thể treo rất lâu khi client mạng
    # yếu hoặc cố tình không nhận ACK; quá hạn → đóng kết nối, không để writer
    # thành zombie giữ RAM.
    ws_write_timeout_seconds: float = 10.0
    # Chạy WS layer như 1 instance duy nhất (dev / test / 1 replica): worker luôn tự
    # nhận leader, không phụ thuộc Redis cho leader election. Mặc định False — an
    # toàn multi-worker (fail-closed): mất Redis → KHÔNG tự xưng leader, tránh
    # split-brain (N worker cùng poll DB + phát trùng tin).
    ws_local_mode: bool = False
    # TTL (giây) của cache revalidation JWT giữa phiên: tránh query Postgres trên
    # từng nhịp heartbeat của từng kết nối (10k client × 1 SELECT/30s → nghẽn pool).
    ws_revalidate_cache_ttl_seconds: float = 60.0
    # TTL (giây) của single-use ticket cho WS handshake. Rất ngắn vì client chỉ cần
    # thời gian nhận ticket từ REST rồi mở socket; dù ticket lộ trong access log /
    # APM trace cũng chỉ dùng được 1 lần trong vài giây.
    ws_ticket_ttl_seconds: float = 15.0
    # TTL (giây) của cache snapshot giá trong RAM của worker phụ (không phải leader).
    # Worker phụ nạp snapshot từ Redis HGETALL rồi giữ 1s: 1.000 client kết nối mới
    # trong cùng giây → 1 lệnh HGETALL thay vì 1.000 (tránh Thundering Herd Redis).
    ws_snapshot_local_cache_ttl_seconds: float = 1.0
    # Cửa sổ lookback (giây) của watermark poll bù phát khớp lệnh. Postgres `now()`
    # trả thời điểm START transaction, không phải COMMIT — một transaction khớp lệnh
    # bắt đầu TRƯỚC watermark nhưng commit SAU khi poll sẽ bị watermark bỏ sót vĩnh
    # viễn nếu poll chỉ đọc `created_at > watermark`. Poll đọc từ `watermark - lookback`
    # để bắt những giao dịch "commit lệch thời gian" này; dedupe (SETNX + seen) đảm bảo
    # tin đã phát không bị đẩy trùng.
    ws_trade_lookback_seconds: float = 5.0
    # TTL (giây) của cache user nạp tại bắt tay WS (giảm Thundering Herd Postgres khi
    # hàng nghìn client reconnect cùng lúc sau rolling restart). User vừa bị khoá sẽ
    # được bắt trong tối đa TTL này — revalidation heartbeat vẫn kiểm tra lại giữa phiên.
    ws_user_cache_ttl_seconds: float = 30.0
    # 2026-01-01 00:00:00 UTC — mốc thời gian thực cho chu kỳ mô phỏng
    ws_sim_anchor_epoch: float = 1767225600.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return cast(list[str], v)

    @field_validator("admin_emails", mode="before")
    @classmethod
    def assemble_admin_emails(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip().lower() for i in v.split(",") if i.strip()]
        return cast(list[str], v)

    model_config = SettingsConfigDict(
        env_file=_find_project_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
