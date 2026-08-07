"""Tests cho schemas/contest (config + template) và pure helpers của generator.

Không cần DB — kiểm tra logic resolve rules, lọc công ty theo lĩnh vực,
sinh công ty bổ sung (SCEN_), và builder nội dung deterministic.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from models.company import Company
from schemas.contest import (
    TEMPLATES,
    ContestCreateRequest,
    ContestTemplate,
    build_config,
    resolve_rules,
)
from services import contest_service


# ────────────────────────────────────────────────────────────────────────────
# build_config / resolve_rules
# ────────────────────────────────────────────────────────────────────────────
def test_build_config_classic_defaults() -> None:
    config = build_config(ContestCreateRequest(name="Cuộc thi mẫu"))
    assert config.template == "classic"
    assert config.company_count == 8
    assert config.difficulty == "normal"
    assert config.auto_news is True
    assert config.auto_social is True
    assert config.rules.start_cash == Decimal("100000000")
    assert config.rules.cooldown_seconds == 30
    assert config.rules.allow_short is False
    assert config.content.generated is False


def test_build_config_tech_news_hard() -> None:
    config = build_config(
        ContestCreateRequest(
            name="Tin nóng",
            template="tech_news",
            difficulty="hard",
            company_count=5,
        )
    )
    assert config.template == "tech_news"
    assert config.company_count == 5
    # hard: volatility *1.4, cooldown *0.5, start_cash *0.5
    assert config.rules.volatility_multiplier == pytest.approx(1.2 * 1.4)
    assert config.rules.cooldown_seconds == 7
    assert config.rules.start_cash == Decimal("100000000")


def test_resolve_rules_micro_easy() -> None:
    template: ContestTemplate = TEMPLATES["micro"]
    rules = resolve_rules(template, "easy")
    # cooldown 5 * 2.0 = 10
    assert rules.cooldown_seconds == 10
    assert rules.start_cash == Decimal("75000000")
    assert rules.volatility_multiplier == pytest.approx(1.0 * 0.7)
    assert rules.trading_duration_days == 7


# ────────────────────────────────────────────────────────────────────────────
# Pure helpers của generator
# ────────────────────────────────────────────────────────────────────────────
def test_slugify_vietnamese() -> None:
    assert contest_service.slugify("Thị Trường 1") == "thi-truong-1"
    assert contest_service.slugify("Công nghệ") == "cong-nghe"
    assert contest_service.slugify("   ") == "contest"


def _templates(n: int = 2) -> list[dict[str, Any]]:
    return [
        {
            "symbol": f"T{i}",
            "name": f"Company {i}",
            "sector": "Technology" if i % 2 == 0 else "Financial",
            "current_price": 100.0,
            "volatility": 0.03,
            "shares_outstanding": 100000000,
            "health_score": 70,
        }
        for i in range(n)
    ]


def test_match_company_templates_by_industry() -> None:
    templates = _templates(4)
    matched = contest_service._match_company_templates(templates, "công nghệ")
    assert matched
    assert all(c["sector"] == "Technology" for c in matched)


def test_match_company_templates_general() -> None:
    templates = _templates(3)
    assert contest_service._match_company_templates(templates, "tổng hợp") == templates
    assert contest_service._match_company_templates(templates, "") == templates


def test_ensure_company_count_generates_synthetic() -> None:
    templates = _templates(2)
    picked = contest_service._ensure_company_count(templates, 5, "Technology")
    assert len(picked) == 5
    symbols = [c["symbol"] for c in picked]
    assert len(symbols) == len(set(symbols))
    assert "SCEN001" in symbols
    assert "SCEN002" in symbols
    assert all(c["sector"] == "Technology" for c in picked if c["symbol"].startswith("SCEN"))


def _fake_company(symbol: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), symbol=symbol, name=f"{symbol} Corp")


def test_news_rows_deterministic_and_scoped() -> None:
    companies = cast(list[Company], [_fake_company("AAA"), _fake_company("BBB")])
    rows = contest_service._news_rows_for_contest(companies, "công nghệ", False)
    assert len(rows) == 3  # 1/công ty + 1 vĩ mô
    per_company = [r for r in rows if r["company_id"] is not None]
    assert len(per_company) == 2
    assert all(r["simulated_at"].year >= 2020 for r in rows)
    # deterministic: chạy lại cho kết quả giống hệt
    rows2 = contest_service._news_rows_for_contest(companies, "công nghệ", False)
    assert [r["title"] for r in rows] == [r["title"] for r in rows2]


def test_news_rows_tech_emphasis_doubles() -> None:
    companies = cast(list[Company], [_fake_company("AAA")])
    rows = contest_service._news_rows_for_contest(companies, "công nghệ", True)
    assert len(rows) == 3  # 2 tin công ty + 1 vĩ mô


def test_social_rows_deterministic() -> None:
    companies = cast(
        list[Company],
        [_fake_company("AAA"), _fake_company("BBB"), _fake_company("CCC")],
    )
    rows = contest_service._social_rows_for_contest(companies)
    assert len(rows) == 3
    assert all(r["company_id"] is not None for r in rows)
    assert all(0 <= r["virality_score"] <= 10 for r in rows)
