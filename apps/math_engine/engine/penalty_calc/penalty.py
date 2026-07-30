from dataclasses import dataclass, field

COOLDOWN_TIERS: list[tuple[int, float]] = [
    (20, 0.0),
    (40, 30.0),
    (60, 300.0),
    (80, 900.0),
    (100, 1800.0),
]

SEVERITY_RISK_MAP: dict[int, int] = {
    1: 1,
    2: 3,
    3: 5,
    4: 10,
    5: 20,
}

SEVERITY_POINTS_MAP: dict[int, int] = {
    1: 0,
    2: 10,
    3: 25,
    4: 50,
    5: 100,
}


@dataclass
class PenaltyConfig:
    cooldown_tiers: list[tuple[int, float]] = field(
        default_factory=lambda: list(COOLDOWN_TIERS)
    )
    severity_risk_map: dict[int, int] = field(
        default_factory=lambda: dict(SEVERITY_RISK_MAP)
    )
    severity_points_map: dict[int, int] = field(
        default_factory=lambda: dict(SEVERITY_POINTS_MAP)
    )

    def __post_init__(self):
        self.cooldown_tiers.sort(key=lambda x: x[0])


DEFAULT_PENALTY_CONFIG = PenaltyConfig()


def calc_cooldown_seconds(
    risk_score: int,
    config: PenaltyConfig | None = None,
) -> float:
    if not (0 <= risk_score <= 100):
        raise ValueError("risk_score must be between 0 and 100")

    cfg = config or DEFAULT_PENALTY_CONFIG
    for threshold, duration in cfg.cooldown_tiers:
        if risk_score <= threshold:
            return duration
    return cfg.cooldown_tiers[-1][1]


def calc_risk_score_delta(
    trap_severity: int,
    current_risk_score: int,
    config: PenaltyConfig | None = None,
) -> int:
    if not (1 <= trap_severity <= 5):
        raise ValueError("trap_severity must be between 1 and 5")
    if not (0 <= current_risk_score <= 100):
        raise ValueError("current_risk_score must be between 0 and 100")

    cfg = config or DEFAULT_PENALTY_CONFIG
    delta = cfg.severity_risk_map.get(trap_severity, 1)

    max_allowed_delta = max(0, 100 - current_risk_score)
    return min(delta, max_allowed_delta)


def calc_points_deducted(
    trap_severity: int,
    config: PenaltyConfig | None = None,
) -> int:
    if not (1 <= trap_severity <= 5):
        raise ValueError("trap_severity must be between 1 and 5")

    cfg = config or DEFAULT_PENALTY_CONFIG
    return cfg.severity_points_map.get(trap_severity, 0)
