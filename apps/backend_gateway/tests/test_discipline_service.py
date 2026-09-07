"""Test Discipline Score — clamp, luật cộng/trừ, không phụ thuộc lợi nhuận."""

from types import SimpleNamespace

import pytest
from models.discipline import DisciplineScoreHistory
from services.discipline_service import (
    R_VIOLATION,
    apply_discipline,
    clamp,
)


class _FakeDB:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)


def _user(score: int = 90) -> SimpleNamespace:
    return SimpleNamespace(id=123, discipline_score=score)


def test_clamp_bounds() -> None:
    assert clamp(-10) == 0
    assert clamp(200) == 100
    assert clamp(50) == 50


@pytest.mark.asyncio
async def test_apply_violation_deducts_and_clamps() -> None:
    db = _FakeDB()
    user = _user(score=90)
    delta = await apply_discipline(db, user, R_VIOLATION)
    assert delta == -8
    assert user.discipline_score == 82


@pytest.mark.asyncio
async def test_apply_violation_never_below_zero() -> None:
    db = _FakeDB()
    user = _user(score=3)
    delta = await apply_discipline(db, user, R_VIOLATION)
    # -8 nhưng clamp 0 → delta thực tế chỉ -3.
    assert delta == -3
    assert user.discipline_score == 0


@pytest.mark.asyncio
async def test_apply_records_history() -> None:
    db = _FakeDB()
    user = _user(score=50)
    await apply_discipline(db, user, R_VIOLATION, context={"trap": "fomo"})
    assert len(db.added) == 1
    entry = db.added[0]
    assert isinstance(entry, DisciplineScoreHistory)
    assert entry.score_delta == -8
    assert entry.reason == R_VIOLATION
    assert entry.context == {"trap": "fomo"}
    assert entry.user_id == 123


@pytest.mark.asyncio
async def test_unknown_rule_is_noop() -> None:
    db = _FakeDB()
    user = _user(score=90)
    delta = await apply_discipline(db, user, "not_a_real_rule")
    assert delta == 0
    assert user.discipline_score == 90
