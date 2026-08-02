from pathlib import Path
from typing import Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".env").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current.parent  # fallback harmless — pydantic-settings ignores missing .env


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://finsim:finsim_secret@localhost:5432/finsimai"
    database_url_sync: str = "postgresql://finsim:finsim_secret@localhost:5432/finsimai"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = [
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

    math_engine_grpc_host: str = "localhost"
    math_engine_grpc_port: int = 50051

    health_check_timeout: float = 2.0

    # ─── WebSocket Real-time ────────────────────────────────────────
    ws_price_tick_seconds: float = 2.0
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
        return v

    model_config = SettingsConfigDict(
        env_file=_find_project_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
