import numpy as np
import pytest

from engine.pricing.price_generator import MarketConfig, PriceGenerator, _apply_vn_tick_size


class TestMarketConfig:
    def test_defaults(self):
        cfg = MarketConfig()
        assert cfg.mu == 0.10
        assert cfg.sigma == 0.25
        assert cfg.price_limit_pct == 0.07

    def test_custom_values(self):
        cfg = MarketConfig(mu=0.05, sigma=0.3, price_limit_pct=0.1)
        assert cfg.mu == 0.05
        assert cfg.sigma == 0.3


class TestGBMDeterministic:
    def test_zero_sigma_no_change(self):
        config = MarketConfig(mu=0.0, sigma=0.0, price_limit_pct=1.0)
        gen = PriceGenerator(config, seed=42)
        price = gen.generate_next_price(100.0, 100.0, 1.0 / 252)
        assert price == 100.0

    def test_path_deterministic_with_zero_sigma(self):
        config = MarketConfig(mu=0.0, sigma=0.0, price_limit_pct=1.0)
        gen = PriceGenerator(config, seed=42)
        path = gen.generate_price_path(100.0, 1.0 / 252, 10)
        assert np.all(path == 100.0)


class TestPriceLimit:
    def test_price_clip_within_band(self):
        config = MarketConfig(mu=0.0, sigma=0.0, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        price = gen.generate_next_price(100.0, 100.0, 1.0 / 252)
        assert 93.0 <= price <= 107.0

    def test_extreme_shock_clipped(self):
        config = MarketConfig(mu=0.0, sigma=0.0, price_limit_pct=0.10)
        gen = PriceGenerator(config, seed=99)
        price = gen.generate_next_price(100.0, 100.0, 1.0 / 252, external_shock=10.0)
        assert 90.0 <= price <= 110.0


class TestPricePath:
    def test_length(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        path = gen.generate_price_path(100.0, 1.0 / 252, 10)
        assert len(path) == 11

    def test_start_price_preserved(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        path = gen.generate_price_path(100.0, 1.0 / 252, 10)
        assert path[0] == 100.0

    def test_zero_steps(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        path = gen.generate_price_path(100.0, 1.0 / 252, 0)
        assert len(path) == 1
        assert path[0] == 100.0

    def test_all_positive_prices(self):
        config = MarketConfig(sigma=0.3, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        path = gen.generate_price_path(100.0, 1.0 / 252, 50)
        assert np.all(path > 0)


class TestPricePathBatch:
    def test_shape(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        start_prices = np.array([100.0, 50.0, 200.0])
        paths = gen.generate_price_path_batch(start_prices, 1.0 / 252, 10)
        assert paths.shape == (3, 11)

    def test_single_asset(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen = PriceGenerator(config, seed=42)
        paths = gen.generate_price_path_batch(np.array([100.0]), 1.0 / 252, 5)
        assert paths.shape == (1, 6)


class TestVNTickSize:
    def test_scalar_below_10k(self):
        assert _apply_vn_tick_size(5430.0) == 5430.0
        assert _apply_vn_tick_size(12345.0) == 12350.0

    def test_scalar_10k_to_50k(self):
        assert _apply_vn_tick_size(25000.0) == 25000.0
        assert _apply_vn_tick_size(25135.0) == 25150.0

    def test_scalar_above_50k(self):
        assert _apply_vn_tick_size(55000.0) == 55000.0
        assert _apply_vn_tick_size(55100.0) == 55100.0

    def test_array(self):
        prices = np.array([5430.0, 25000.0, 55000.0])
        result = _apply_vn_tick_size(prices)
        np.testing.assert_array_equal(result, [5430.0, 25000.0, 55000.0])


class TestSeedReproducibility:
    def test_same_seed_same_path(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=0.07)
        gen1 = PriceGenerator(config, seed=42)
        gen2 = PriceGenerator(config, seed=42)
        path1 = gen1.generate_price_path(100.0, 1.0 / 252, 50)
        path2 = gen2.generate_price_path(100.0, 1.0 / 252, 50)
        np.testing.assert_array_equal(path1, path2)

    def test_different_seed_different_path(self):
        config = MarketConfig(sigma=0.3, price_limit_pct=0.10)
        gen1 = PriceGenerator(config, seed=42)
        gen2 = PriceGenerator(config, seed=99)
        path1 = gen1.generate_price_path(50000.0, 21.0 / 252, 10)
        path2 = gen2.generate_price_path(50000.0, 21.0 / 252, 10)
        assert not np.array_equal(path1, path2)


class TestEdgeCases:
    def test_dt_zero_no_movement(self):
        config = MarketConfig(mu=0.1, sigma=0.2, price_limit_pct=1.0)
        gen = PriceGenerator(config, seed=42)
        price = gen.generate_next_price(100.0, 100.0, 0.0)
        assert price == 100.0

    def test_very_low_price(self):
        config = MarketConfig(sigma=0.2, price_limit_pct=1.0)
        gen = PriceGenerator(config, seed=42)
        price = gen.generate_next_price(0.01, 0.01, 1.0 / 252)
        assert price >= 0.0
