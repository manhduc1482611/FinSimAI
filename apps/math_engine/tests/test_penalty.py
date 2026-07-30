import pytest
from engine.penalty_calc.penalty import (
    PenaltyConfig,
    calc_cooldown_seconds,
    calc_risk_score_delta,
    calc_points_deducted,
)


def test_calc_cooldown_seconds_thresholds():
    assert calc_cooldown_seconds(0) == 0.0
    assert calc_cooldown_seconds(20) == 0.0
    assert calc_cooldown_seconds(21) == 30.0
    assert calc_cooldown_seconds(40) == 30.0
    assert calc_cooldown_seconds(60) == 300.0
    assert calc_cooldown_seconds(80) == 900.0
    assert calc_cooldown_seconds(100) == 1800.0


def test_calc_cooldown_unsorted_config():
    custom_cfg = PenaltyConfig(
        cooldown_tiers=[(60, 300.0), (20, 0.0), (100, 1800.0)]
    )
    assert calc_cooldown_seconds(15, config=custom_cfg) == 0.0


def test_calc_risk_score_delta_capping():
    assert calc_risk_score_delta(trap_severity=5, current_risk_score=50) == 20
    assert calc_risk_score_delta(trap_severity=5, current_risk_score=90) == 10
    assert calc_risk_score_delta(trap_severity=5, current_risk_score=100) == 0


def test_calc_points_deducted():
    assert calc_points_deducted(1) == 0
    assert calc_points_deducted(3) == 25
    assert calc_points_deducted(5) == 100


def test_all_severity_values():
    for sev, expected_delta in [(1, 1), (2, 3), (3, 5), (4, 10), (5, 20)]:
        assert calc_risk_score_delta(sev, 50) == expected_delta
        assert calc_points_deducted(sev) == {1: 0, 2: 10, 3: 25, 4: 50, 5: 100}[sev]


def test_custom_config_override():
    custom = PenaltyConfig(
        cooldown_tiers=[(100, 500.0)],
        severity_risk_map={5: 50},
        severity_points_map={5: 999},
    )
    assert calc_cooldown_seconds(99, config=custom) == 500.0
    assert calc_risk_score_delta(5, 0, config=custom) == 50
    assert calc_points_deducted(5, config=custom) == 999


def test_penalty_invalid_inputs():
    with pytest.raises(ValueError, match="risk_score must be between 0 and 100"):
        calc_cooldown_seconds(-5)

    with pytest.raises(ValueError, match="risk_score must be between 0 and 100"):
        calc_cooldown_seconds(101)

    with pytest.raises(ValueError, match="trap_severity must be between 1 and 5"):
        calc_risk_score_delta(trap_severity=6, current_risk_score=50)

    with pytest.raises(ValueError, match="current_risk_score must be between 0 and 100"):
        calc_risk_score_delta(trap_severity=3, current_risk_score=105)

    with pytest.raises(ValueError, match="trap_severity must be between 1 and 5"):
        calc_points_deducted(0)
