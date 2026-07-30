import numpy as np

TRADING_DAYS_PER_YEAR = 252


def calc_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
) -> float:
    if len(returns) < 2:
        return 0.0

    daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - daily_rf

    std_excess = np.std(excess, ddof=1)
    if std_excess == 0 or np.isnan(std_excess):
        return 0.0

    return float(np.mean(excess) / std_excess * np.sqrt(TRADING_DAYS_PER_YEAR))


def calc_max_drawdown(nav_series: np.ndarray) -> float:
    if len(nav_series) < 2:
        return 0.0

    if np.any(nav_series <= 0):
        return 0.0

    peak = np.maximum.accumulate(nav_series)
    drawdown = (nav_series - peak) / peak
    return float(np.min(drawdown))


def calc_volatility(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))


def calc_daily_returns(prices: np.ndarray) -> np.ndarray:
    if len(prices) < 2:
        return np.array([], dtype=np.float64)
    return (prices[1:] / prices[:-1]) - 1.0
