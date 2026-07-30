from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SECONDS_PER_REAL_MINUTE = 60
SECONDS_PER_SIMULATED_DAY = 86400
TRADING_DAYS_PER_YEAR = 252


@dataclass
class TimeCompressionConfig:
    real_seconds_per_simulated_day: float = SECONDS_PER_REAL_MINUTE

    def __post_init__(self):
        if self.real_seconds_per_simulated_day <= 0:
            raise ValueError("real_seconds_per_simulated_day must be strictly positive")

    @property
    def ratio(self) -> float:
        return SECONDS_PER_SIMULATED_DAY / self.real_seconds_per_simulated_day

    def real_to_sim_seconds(self, real_seconds: float) -> float:
        return real_seconds * self.ratio

    def sim_to_real_seconds(self, sim_seconds: float) -> float:
        return sim_seconds / self.ratio

    def real_to_sim_dt_years(self, real_seconds: float) -> float:
        sim_seconds = self.real_to_sim_seconds(real_seconds)
        return sim_seconds / (SECONDS_PER_SIMULATED_DAY * TRADING_DAYS_PER_YEAR)


def sim_days_to_dt_years(sim_days: float) -> float:
    if sim_days < 0:
        raise ValueError("sim_days cannot be negative")
    return sim_days / TRADING_DAYS_PER_YEAR


def format_sim_datetime(
    sim_epoch_seconds: float,
    base_year: int = 2026,
    include_time: bool = True,
) -> str:
    if sim_epoch_seconds < 0:
        raise ValueError("sim_epoch_seconds cannot be negative")

    start_date = datetime(base_year, 1, 1, tzinfo=timezone.utc)
    sim_dt = start_date + timedelta(seconds=sim_epoch_seconds)
    sim_days = int(sim_epoch_seconds // SECONDS_PER_SIMULATED_DAY)

    if include_time:
        formatted_dt = sim_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        formatted_dt = sim_dt.strftime("%Y-%m-%d")

    return f"{formatted_dt} (Sim Day {sim_days})"
