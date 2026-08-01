"""Gemini integration wrapper của AI Engine.

Mục tiêu:
- Ép Gemini trả về JSON ĐÚNG SCHEMA bằng Pydantic Output Parser:
  ``response_schema=<Pydantic model>`` + ``response_mime_type="application/json"``.
- Vòng lặp retry có PHẢN HỒI LỖI: nếu JSON sai schema, vi phạm policy hoặc
  lỗi mạng → gửi lại thông báo cho model, thử lại tối đa N lần.
- Không có ``GEMINI_API_KEY`` hoặc mọi lần thử đều thất bại → raise lỗi rõ ràng;
  Agent sẽ tự rơi về fallback deterministic (0 token) để luôn an toàn.

Lưu ý bảo mật: key chỉ đọc từ env ``GEMINI_API_KEY`` (hoặc ``.env`` ở gốc repo),
không bao giờ được log, không được nhúng vào code.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

try:
    from google import genai as _genai
    from google.genai import types as _genai_types

    _GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - phụ thuộc môi trường cài đặt
    _genai: Any = None  # type: ignore[no-redef]
    _genai_types: Any = None  # type: ignore[no-redef]
    _GENAI_AVAILABLE = False


def _find_env_file() -> Path:
    """Tìm file ``.env``: ưu tiên gần nhất, fallback về gốc repo (cạnh uv.lock)."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    for parent in current.parents:
        if (parent / "uv.lock").is_file():
            return parent / ".env"
    return current.parent / ".env"


class GeminiConfig(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_retries: int = 2
    gemini_temperature: float = 0.6
    gemini_max_output_tokens: int = 2048
    gemini_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


class GeminiError(RuntimeError):
    """Lỗi cơ bản của tầng Gemini."""


class GeminiUnavailableError(GeminiError):
    """Gemini chưa sẵn sàng (thiếu key / thiếu package) — Agent phải fallback."""


class GeminiCallError(GeminiError):
    """Lỗi khi gọi API (mạng, quota, 4xx/5xx)."""


class StructuredOutputError(GeminiError):
    """Không nhận được output hợp lệ sau nhiều lần thử."""


class PolicyViolationError(GeminiError):
    """Output hợp lệ về cấu trúc nhưng VI PHẠM chính sách (ví dụ lời khuyên mua/bán)."""

    def __init__(self, violations: list[str], *args: Any) -> None:
        self.violations = violations
        super().__init__(*args or ("; ".join(violations) or "Vi phạm chính sách nội dung"))


ModelT = TypeVar("ModelT", bound=BaseModel)


class GeminiClient:
    """Client Gemini có ép kiểu JSON bằng Pydantic + retry có feedback."""

    def __init__(self, config: GeminiConfig | None = None) -> None:
        self.config = config or GeminiConfig()
        self._client: Any | None = None

    @property
    def available(self) -> bool:
        return _GENAI_AVAILABLE and bool(self.config.gemini_api_key)

    def _ensure_client(self) -> Any:
        if not self.available:
            raise GeminiUnavailableError(
                "Gemini chưa sẵn sàng: thiếu GEMINI_API_KEY hoặc package google-genai. "
                "Agent sẽ dùng fallback deterministic (0 token)."
            )
        if self._client is None:
            self._client = _genai.Client(api_key=self.config.gemini_api_key)
        return self._client

    # ── API chính ──────────────────────────────────────────────────────────
    def generate_structured(
        self,
        model_type: type[ModelT],
        *,
        system_instruction: str,
        user_content: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        validator: Callable[[BaseModel], None] | None = None,
    ) -> ModelT:
        """Sinh output ép đúng schema ``model_type``.

        ``validator`` (tuỳ chọn): hàm kiểm tra chính sách sau khi parse — ném
        :class:`PolicyViolationError` nếu nội dung vi phạm (vd: khuyên mua/bán).
        Vi phạm sẽ được đưa vào vòng retry feedback.
        """
        client = self._ensure_client()
        cfg = self.config
        max_retries = cfg.gemini_max_retries
        content = user_content
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=cfg.gemini_model,
                    contents=content,
                    config=_genai_types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=model_type,
                        temperature=cfg.gemini_temperature if temperature is None else temperature,
                        max_output_tokens=(
                            cfg.gemini_max_output_tokens
                            if max_output_tokens is None
                            else max_output_tokens
                        ),
                    ),
                )
                reply = self._coerce(model_type, response)
                if validator is not None:
                    validator(reply)
                return reply
            except PolicyViolationError as exc:
                last_error = exc
                if attempt < max_retries:
                    content = self._with_feedback(content, exc, attempt + 1)
                    continue
            except (ValidationError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt < max_retries:
                    content = self._with_feedback(content, exc, attempt + 1)
                    continue
            except GeminiError:
                raise
            except Exception as exc:  # noqa: BLE001 - lỗi mạng/API không đoán trước
                last_error = exc
                if attempt < max_retries:
                    self._backoff(attempt)
                    continue

        if isinstance(last_error, GeminiError):
            raise last_error
        raise StructuredOutputError(
            f"Không nhận được output hợp lệ sau {max_retries + 1} lần thử: {last_error}"
        ) from last_error

    # ── Trợ giúp ───────────────────────────────────────────────────────────
    def _coerce(self, model_type: type[ModelT], response: Any) -> ModelT:
        """Parse response về ``model_type`` theo nhiều nguồn khả dụng."""
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, model_type):
            return model_type.model_validate(parsed.model_dump())
        if isinstance(parsed, dict):
            return model_type.model_validate(parsed)
        text = getattr(response, "text", None)
        if text:
            return model_type.model_validate_json(text.strip())
        raise StructuredOutputError("Gemini không trả về nội dung có thể parse.")

    @staticmethod
    def _with_feedback(content: str, error: Exception, attempt: int) -> str:
        feedback = str(error).strip() or error.__class__.__name__
        return (
            f"{content}\n\n"
            f"── PHẢN HỒI LỖI TỪ HỆ THỐNG (lần sửa thứ {attempt}) ──\n"
            f"Phản hồi trước của bạn không hợp lệ: {feedback}\n"
            "Hãy trả lời lại TOÀN BỘ, đúng schema JSON, tuân thủ mọi quy tắc đã nêu. "
            "Chỉ trả về JSON."
        )

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(0.5 * (attempt + 1), 2.0))
