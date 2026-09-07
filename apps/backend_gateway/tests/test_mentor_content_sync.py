"""Đồng bộ question-bank gateway ↔ YAML ai_engine — improvement_plan A3.3.

``realtime/mentor_engine.py`` là bản mirror deterministic của
``apps/ai_engine/prompts/mentor_prompts.yaml`` (fallback section). Hai nguồn
trước đây được copy tay → drift chắc chắn xảy ra khi sửa một bên. Test này
assert nội dung hai bên GIỐNG HỆT nhau: sửa YAML mà quên sync sẽ đỏ test.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from realtime.mentor_engine import (
    _DETECTION,
    _DISCLAIMER,
    _PRIORITY_ORDER,
    _QUESTION_BANK,
)

_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "ai_engine" / "prompts" / "mentor_prompts.yaml"
)


def _load_fallback() -> dict:
    with _YAML_PATH.open(encoding="utf-8") as fh:
        store = yaml.safe_load(fh)
    return store["fallback"]


def test_priority_order_matches_yaml() -> None:
    assert _PRIORITY_ORDER == _load_fallback()["priority_order"]


def test_detection_keywords_match_yaml() -> None:
    yaml_detection: dict[str, list[str]] = _load_fallback()["detection"]
    assert set(_DETECTION) == set(yaml_detection)
    for focus, keywords in yaml_detection.items():
        assert _DETECTION[focus] == keywords, f"Keyword drift ở focus {focus!r}"


def test_question_bank_matches_yaml() -> None:
    yaml_bank: dict[str, dict] = _load_fallback()["question_bank"]
    assert set(_QUESTION_BANK) == set(yaml_bank)
    for focus, entry in yaml_bank.items():
        local = _QUESTION_BANK[focus]
        assert local["questions"] == entry["questions"], f"Questions drift ở {focus!r}"
        assert local["coaching_tip"] == entry["coaching_tip"], f"Tip drift ở {focus!r}"


def test_disclaimer_matches_yaml() -> None:
    assert _DISCLAIMER == _load_fallback()["disclaimer"]
