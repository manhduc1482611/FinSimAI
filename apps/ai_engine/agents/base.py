"""Lớp nền chung cho các AI Agent.

Mỗi Agent:
- Sở hữu một :class:`prompts.loader.PromptStore` để đọc prompt YAML tập trung.
- Sở hữu một :class:`integrations.gemini.GeminiClient` để gọi Gemini có ép JSON.
- Có logic fallback DETERMINISTIC (0 token) riêng, được gọi khi Gemini không
  khả dụng hoặc thất bại — đảm bảo hệ thống luôn trả về kết quả an toàn.
"""

from __future__ import annotations

from typing import Any

from integrations.gemini import GeminiClient
from prompts.loader import PromptStore


class BaseAgent:
    prompt_file: str = ""

    def __init__(
        self,
        *,
        gemini: GeminiClient | None = None,
        prompt_store: PromptStore | None = None,
    ) -> None:
        self.gemini = gemini or GeminiClient()
        self.store = prompt_store or PromptStore()

    def _require_prompt(self, *keys: str) -> Any:
        return self.store.require(self.prompt_file, *keys)
