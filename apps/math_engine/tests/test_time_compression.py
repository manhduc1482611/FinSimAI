
import pytest

from engine.time_compression.compressor import (
    SECONDS_PER_SIMULATED_DAY,
    TRADING_DAYS_PER_YEAR,
    TimeCompressionConfig,
    format_sim_datetime,
    sim_days_to_dt_years,
)


class TestTimeCompressionConfig:
    def test_default_ratio(self):
        config = TimeCompressionConfig()
        assert config.ratio == 1440.0

    def test_custom_ratio(self):
        config = TimeCompressionConfig(real_seconds_per_simulated_day=120.0)
        assert config.ratio == 720.0

    def test_real_to_sim_seconds(self):
        config = TimeCompressionConfig(60.0)
        assert config.real_to_sim_seconds(1.0) == 1440.0
        assert config.real_to_sim_seconds(0.5) == 720.0
        assert config.real_to_sim_seconds(0.0) == 0.0

    def test_sim_to_real_seconds(self):
        config = TimeCompressionConfig(60.0)
        assert config.sim_to_real_seconds(1440.0) == 1.0
        assert config.sim_to_real_seconds(0.0) == 0.0

    def test_roundtrip(self):
        config = TimeCompressionConfig(60.0)
        original = 123.456
        sim = config.real_to_sim_seconds(original)
        back = config.sim_to_real_seconds(sim)
        assert pytest.approx(back, rel=1e-12) == original

    def test_real_to_sim_dt_years(self):
        config = TimeCompressionConfig(60.0)
        dt = config.real_to_sim_dt_years(0.5)
        expected = 720.0 / (SECONDS_PER_SIMULATED_DAY * TRADING_DAYS_PER_YEAR)
        assert pytest.approx(dt, rel=1e-7) == expected

    def test_real_to_sim_dt_years_zero(self):
        config = TimeCompressionConfig(60.0)
        assert config.real_to_sim_dt_years(0.0) == 0.0

    def test_invalid_zero(self):
        with pytest.raises(ValueError, match="strictly positive"):
            TimeCompressionConfig(real_seconds_per_simulated_day=0.0)

    def test_invalid_negative(self):
        with pytest.raises(ValueError, match="strictly positive"):
            TimeCompressionConfig(real_seconds_per_simulated_day=-10.0)

    def test_fast_compression(self):
        config = TimeCompressionConfig(real_seconds_per_simulated_day=1.0)
        assert config.ratio == 86400.0
        assert config.real_to_sim_seconds(1.0) == 86400.0  # 1 real sec = 1 sim day

    def test_slow_compression(self):
        config = TimeCompressionConfig(real_seconds_per_simulated_day=3600.0)
        assert config.ratio == 24.0
        assert config.real_to_sim_seconds(3600.0) == 86400.0  # 1 real hour = 1 sim day


class TestSimDaysToDtYears:
    def test_one_trading_year(self):
        assert sim_days_to_dt_years(252.0) == 1.0

    def test_zero_days(self):
        assert sim_days_to_dt_years(0.0) == 0.0

    def test_half_year(self):
        assert sim_days_to_dt_years(126.0) == 0.5

    def test_negative(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            sim_days_to_dt_years(-1.0)


class TestFormatSimDatetime:
    def test_epoch_zero(self):
        result = format_sim_datetime(0.0, base_year=2026, include_time=True)
        assert "2026-01-01 00:00:00 (Sim Day 0)" in result

    def test_one_sim_day(self):
        result = format_sim_datetime(SECONDS_PER_SIMULATED_DAY, base_year=2026, include_time=True)
        assert "2026-01-02 00:00:00 (Sim Day 1)" in result

    def test_half_sim_day_with_time(self):
        sim_epoch = 1.5 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2026, include_time=True)
        assert "2026-01-02 12:00:00 (Sim Day 1)" in result

    def test_end_of_year_no_month_13(self):
        sim_epoch = 364 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2026, include_time=False)
        assert "2026-12-31 (Sim Day 364)" in result

    def test_year_rollover(self):
        sim_epoch = 365 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2026, include_time=False)
        assert "2027-01-01 (Sim Day 365)" in result

    def test_multi_year(self):
        sim_epoch = 730 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2026, include_time=False)
        assert "2028-01-01 (Sim Day 730)" in result

    def test_leap_year_handling(self):
        sim_epoch = 365 * SECONDS_PER_SIMULATED_DAY
        base = 2023  # 2023 is not a leap year
        result = format_sim_datetime(sim_epoch, base_year=base, include_time=False)
        assert "2024-01-01 (Sim Day 365)" in result

    def test_base_year_2024_leap(self):
        sim_epoch = 366 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2024, include_time=False)
        assert "2025-01-01 (Sim Day 366)" in result

    def test_without_time(self):
        result = format_sim_datetime(0.0, base_year=2026, include_time=False)
        assert "2026-01-01 (Sim Day 0)" in result
        assert "00:00:00" not in result

    def test_negative_epoch(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            format_sim_datetime(-1.0)

    def test_large_epoch(self):
        sim_epoch = 10000 * SECONDS_PER_SIMULATED_DAY
        result = format_sim_datetime(sim_epoch, base_year=2026, include_time=False)
        assert "Sim Day 10000" in result
