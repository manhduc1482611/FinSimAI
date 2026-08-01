"""Prompt Store tập trung — nạp và render mọi prompt YAML của AI Engine.

Nguyên tắc thiết kế:
- Template dùng placeholder ``{{ten_bien}}`` (double curly braces) THAY VÌ
  ``str.format``/``string.Template``, vì nội dung prompt thường chứa JSON ``{...}``
  (ví dụ ví dụ schema) — dùng ``str.format`` sẽ vỡ cấu trúc ngay lập tức.
- Chỉ những token được khai báo trong kwargs mới được thay thế; token lạ được
  giữ NGUYÊN để phát hiện lỗi render (test sẽ chặn token sót lại).
- File YAML phải luôn là một mapping ở gốc; nạp bằng ``yaml.safe_load``.

Báo lỗi khi:
- Tên file chứa ký tự bất thường (chống path traversal).
- File không tồn tại hoặc YAML hỏng.
- Thiếu khoá bắt buộc khi ``require``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"\{\{(\w+)\}\}")
_SAFE_FILENAME = re.compile(r"^[a-z0-9_]+\.ya?ml$")


class PromptStoreError(RuntimeError):
    """Lỗi nạp/render prompt từ kho YAML tập trung."""


class PromptStore:
    """Kho prompt trong bộ nhớ có cache, đọc từ thư mục ``prompts/``."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path(__file__).resolve().parent
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Nạp một file YAML (có cache) và kiểm tra cấu trúc mapping."""
        if not _SAFE_FILENAME.fullmatch(name):
            raise PromptStoreError(f"Tên prompt không hợp lệ: {name!r}")
        if name in self._cache:
            return self._cache[name]
        path = self._base_dir / name
        if not path.is_file():
            raise PromptStoreError(f"Không tìm thấy file prompt: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise PromptStoreError(f"File YAML hỏng ({path}): {exc}") from exc
        if not isinstance(data, dict):
            raise PromptStoreError(f"File YAML phải là mapping ở gốc ({path})")
        self._cache[name] = data
        logger.debug("Đã nạp prompt store: %s", name)
        return data

    def require(self, name: str, *keys: str) -> Any:
        """Lấy node sâu theo chuỗi khoá, báo lỗi nếu thiếu bất kỳ khoá nào."""
        node: Any = self.load(name)
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                raise PromptStoreError(f"Thiếu khoá {'.'.join(keys)} trong {name}")
            node = node[key]
        return node

    @staticmethod
    def render(template: str, **kwargs: Any) -> str:
        """Thay ``{{ten_bien}}`` bằng giá trị tương ứng; token lạ giữ nguyên."""

        def _sub(match: re.Match[str]) -> str:
            key = match.group(1)
            return str(kwargs[key]) if key in kwargs else match.group(0)

        return _TOKEN_PATTERN.sub(_sub, template)

    @staticmethod
    def render_value(value: Any, **kwargs: Any) -> Any:
        """Render đệ quy qua chuỗi/dict/list (cho fallback dữ liệu YAML)."""
        if isinstance(value, str):
            return PromptStore.render(value, **kwargs)
        if isinstance(value, list):
            return [PromptStore.render_value(item, **kwargs) for item in value]
        if isinstance(value, dict):
            return {key: PromptStore.render_value(item, **kwargs) for key, item in value.items()}
        return value

    def render_template(self, name: str, template_key: str, **kwargs: Any) -> str:
        """Render một template nằm dưới ``templates.<template_key>``."""
        template = self.require(name, "templates", template_key)
        if not isinstance(template, str):
            raise PromptStoreError(
                f"Template {template_key} trong {name} phải là chuỗi"
            )
        return self.render(template, **kwargs)

    @staticmethod
    def leftover_tokens(rendered: str) -> list[str]:
        """Trả về các ``{{token}}`` còn sót lại sau render (dùng cho test)."""
        return _TOKEN_PATTERN.findall(rendered)
