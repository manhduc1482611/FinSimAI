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
    _CONCEPT_GLOSSARY,
    _DETECTION,
    _DISCLAIMER,
    _PRIORITY_ORDER,
    _QUESTION_BANK,
    _STRATEGY_BANK,
)

_YAML_PATH = (
    Path(__file__).resolve().parents[2] / "ai_engine" / "prompts" / "mentor_prompts.yaml"
)
_KB_PATH = (
    Path(__file__).resolve().parents[2] / "ai_engine" / "data" / "knowledge_base.yaml"
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


def test_strategy_bank_matches_yaml() -> None:
    """Gateway framework bank mirror = YAML strategy_bank (docs v2.0 mục 4.2).

    ``_STRATEGY_BANK`` trong mentor_engine.py là bản mirror deterministic cho
    chế độ plan; nguồn chân lý là ``ai_engine/prompts/mentor_prompts.yaml``.
    Nội dung khóa cứng (đã duyệt pháp lý) — test này chặn drift từng field.
    """
    with _YAML_PATH.open(encoding="utf-8") as fh:
        yaml_bank = yaml.safe_load(fh)["strategy_bank"]["frameworks"]

    assert _STRATEGY_BANK, "Gateway framework bank không được rỗng"
    assert set(_STRATEGY_BANK) == set(yaml_bank), "Framework id drift giữa hai nguồn"
    for framework_id, entry in _STRATEGY_BANK.items():
        yaml_entry = yaml_bank[framework_id]
        assert entry["name"] == yaml_entry["name"], f"Name drift ở {framework_id!r}"
        assert entry["objective"] == yaml_entry["objective"], f"Objective drift ở {framework_id!r}"
        assert entry["criteria"] == yaml_entry["criteria"], f"Criteria drift ở {framework_id!r}"
        assert entry["allocation_rule"] == yaml_entry["allocation_rule"], (
            f"Allocation drift ở {framework_id!r}"
        )
        assert entry["risk_rule"] == yaml_entry["risk_rule"], f"Risk drift ở {framework_id!r}"
        assert entry["how_to_trade"] == yaml_entry["how_to_trade"], (
            f"How-to-trade drift ở {framework_id!r}"
        )
        assert entry["questions"] == yaml_entry.get("questions", []), (
            f"Questions drift ở {framework_id!r}"
        )


def test_concept_glossary_matches_knowledge_base() -> None:
    with _KB_PATH.open(encoding="utf-8") as fh:
        kb = yaml.safe_load(fh)["concepts"]

    assert _CONCEPT_GLOSSARY, "Gateway mirror glossary không được rỗng"
    for concept_id, entry in _CONCEPT_GLOSSARY.items():
        assert concept_id in kb, f"Concept {concept_id!r} không có trong knowledge_base.yaml"
        kb_keywords = _normalize_kw(kb[concept_id].get("keywords") or [])
        mirror_keywords = _normalize_kw(entry.get("keywords") or [])
        unknown = mirror_keywords - kb_keywords
        assert not unknown, f"Concept {concept_id!r} có keyword lạ không có trong YAML: {unknown}"


def _normalize_kw(keywords: list[str]) -> set[str]:
    import unicodedata

    def _strip(text: str) -> str:
        lowered = unicodedata.normalize("NFD", text.lower())
        stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
        return stripped.replace("đ", "d").strip()

    return {_strip(k) for k in keywords if k and k.strip()}
