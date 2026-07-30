import numpy as np
from dataclasses import dataclass


def _apply_vn_tick_size(prices: np.ndarray | float) -> np.ndarray | float:
    is_scalar = np.isscalar(prices) or (isinstance(prices, np.ndarray) and prices.ndim == 0)
    arr = np.atleast_1d(prices).astype(np.float64, copy=True)

    mask1 = arr < 10000
    arr[mask1] = np.round(arr[mask1] / 10.0) * 10.0

    mask2 = (arr >= 10000) & (arr < 50000)
    arr[mask2] = np.round(arr[mask2] / 50.0) * 50.0

    mask3 = arr >= 50000
    arr[mask3] = np.round(arr[mask3] / 100.0) * 100.0

    if is_scalar:
        return float(arr[0])

    return arr.reshape(np.shape(prices)) if isinstance(prices, np.ndarray) else arr


@dataclass
class MarketConfig:
    mu: float = 0.10
    sigma: float = 0.25
    price_limit_pct: float = 0.07
    jump_lambda: float = 0.0
    jump_mu: float = 0.0
    jump_sigma: float = 0.0


class PriceGenerator:
    def __init__(self, config: MarketConfig, seed: int | None = None):
        self.config = config
        self.rng = np.random.default_rng(seed)

    def generate_next_price(
        self,
        current_price: float,
        reference_price: float,
        dt_simulated_years: float,
        external_shock: float = 0.0,
    ) -> float:
        config = self.config

        log_return = (config.mu - 0.5 * config.sigma ** 2) * dt_simulated_years
        log_return += config.sigma * np.sqrt(dt_simulated_years) * self.rng.standard_normal()

        if config.jump_lambda > 0:
            n_jumps = self.rng.poisson(config.jump_lambda * dt_simulated_years)
            if n_jumps > 0:
                mean = n_jumps * config.jump_mu
                std = np.sqrt(n_jumps) * config.jump_sigma
                log_return += self.rng.normal(mean, std)

        log_return += external_shock
        raw_price = current_price * np.exp(log_return)

        floor_px = reference_price * (1.0 - config.price_limit_pct)
        ceiling_px = reference_price * (1.0 + config.price_limit_pct)

        clipped = np.clip(raw_price, floor_px, ceiling_px)
        return float(_apply_vn_tick_size(clipped))

    def _sample_jumps(self, shape: tuple[int, ...], dt_simulated_years: float) -> np.ndarray:
        config = self.config
        jumps = np.zeros(shape, dtype=np.float64)

        if config.jump_lambda > 0:
            n_jumps = self.rng.poisson(config.jump_lambda * dt_simulated_years, size=shape)
            mask = n_jumps > 0
            if np.any(mask):
                n_active = n_jumps[mask]
                mean = n_active * config.jump_mu
                std = np.sqrt(n_active) * config.jump_sigma
                jumps[mask] = self.rng.normal(mean, std)

        return jumps

    def generate_price_path(
        self,
        start_price: float,
        dt_simulated_years: float,
        steps: int,
    ) -> np.ndarray:
        config = self.config
        n = steps + 1
        S = np.empty(n, dtype=np.float64)
        S[0] = start_price

        Z = self.rng.standard_normal(steps)
        drift = (config.mu - 0.5 * config.sigma ** 2) * dt_simulated_years
        diffusion = config.sigma * np.sqrt(dt_simulated_years) * Z
        jumps = self._sample_jumps((steps,), dt_simulated_years)

        returns = drift + diffusion + jumps

        floor_px = S[0] * (1.0 - config.price_limit_pct)
        ceil_px = S[0] * (1.0 + config.price_limit_pct)

        for i in range(1, n):
            raw = S[i - 1] * np.exp(returns[i - 1])
            clipped = np.clip(raw, floor_px, ceil_px)
            S[i] = _apply_vn_tick_size(clipped)

        return S

    def generate_price_path_batch(
        self,
        start_prices: np.ndarray,
        dt_simulated_years: float,
        steps: int,
    ) -> np.ndarray:
        config = self.config
        n_assets = len(start_prices)
        n = steps + 1
        S = np.empty((n_assets, n), dtype=np.float64)
        S[:, 0] = start_prices

        Z = self.rng.standard_normal((n_assets, steps))
        drift = (config.mu - 0.5 * config.sigma ** 2) * dt_simulated_years
        diffusion = config.sigma * np.sqrt(dt_simulated_years) * Z
        jumps = self._sample_jumps((n_assets, steps), dt_simulated_years)

        returns = drift + diffusion + jumps

        floor_px = S[:, 0:1] * (1.0 - config.price_limit_pct)
        ceil_px = S[:, 0:1] * (1.0 + config.price_limit_pct)

        for t in range(1, n):
            raw = S[:, t - 1:t] * np.exp(returns[:, t - 1:t])
            clipped = np.clip(raw, floor_px, ceil_px)
            S[:, t:t + 1] = _apply_vn_tick_size(clipped)

        return S
