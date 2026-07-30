import numpy as np
import pytest

from engine.portfolio.portfolio_calc import Holding, TradeResult, calc_nav, calc_unrealized_pnl, apply_buy, apply_sell
from engine.portfolio.risk_metrics import calc_sharpe_ratio, calc_max_drawdown, calc_volatility, calc_daily_returns


class TestCalcNAV:
    def test_basic(self):
        holdings = [Holding(10, 50.0, 55.0), Holding(5, 100.0, 110.0)]
        nav = calc_nav(1000.0, holdings)
        assert nav == 1000.0 + 10 * 55.0 + 5 * 110.0

    def test_empty_holdings(self):
        assert calc_nav(5000.0, []) == 5000.0

    def test_zero_cash(self):
        holdings = [Holding(10, 50.0, 55.0)]
        assert calc_nav(0.0, holdings) == 550.0

    def test_zero_quantity_holdings(self):
        holdings = [Holding(0, 50.0, 55.0)]
        assert calc_nav(1000.0, holdings) == 1000.0


class TestCalcUnrealizedPnL:
    def test_profit(self):
        holdings = [Holding(10, 50.0, 55.0)]
        assert calc_unrealized_pnl(holdings) == 50.0

    def test_loss(self):
        holdings = [Holding(10, 50.0, 45.0)]
        assert calc_unrealized_pnl(holdings) == -50.0

    def test_mixed(self):
        holdings = [Holding(10, 50.0, 55.0), Holding(5, 100.0, 90.0)]
        pnl = calc_unrealized_pnl(holdings)
        assert pnl == 10 * (55 - 50) + 5 * (90 - 100)

    def test_empty_list(self):
        assert calc_unrealized_pnl([]) == 0.0


class TestApplyBuy:
    def test_basic(self):
        result = apply_buy(10, 50.0, 5, 60.0)
        assert result.new_quantity == 15
        expected_avg = (10 * 50.0 + 5 * 60.0) / 15.0
        assert result.new_avg_price == expected_avg
        assert result.realized_pnl_delta == 0.0

    def test_with_fee(self):
        result = apply_buy(10, 50.0, 5, 60.0, fee=10.0)
        assert result.realized_pnl_delta == -10.0
        assert result.fee == 10.0

    def test_first_purchase(self):
        result = apply_buy(0, 0.0, 10, 50.0)
        assert result.new_quantity == 10
        assert result.new_avg_price == 50.0

    def test_invalid_quantity(self):
        with pytest.raises(ValueError):
            apply_buy(10, 50.0, -1, 60.0)

    def test_invalid_price(self):
        with pytest.raises(ValueError):
            apply_buy(10, 50.0, 5, 0.0)


class TestApplySell:
    def test_partial(self):
        result = apply_sell(10, 50.0, 5, 60.0)
        assert result.new_quantity == 5
        assert result.new_avg_price == 50.0  # avg unchanged on partial sell
        assert result.realized_pnl_delta == 5 * (60 - 50)

    def test_full_close(self):
        result = apply_sell(10, 50.0, 10, 60.0)
        assert result.new_quantity == 0
        assert result.new_avg_price == 0.0

    def test_with_fee(self):
        result = apply_sell(10, 50.0, 5, 60.0, fee=5.0)
        assert result.realized_pnl_delta == 5 * (60 - 50) - 5.0
        assert result.fee == 5.0

    def test_sell_exceeds_quantity(self):
        with pytest.raises(ValueError, match="cannot sell more"):
            apply_sell(10, 50.0, 15, 60.0)

    def test_invalid_quantity(self):
        with pytest.raises(ValueError):
            apply_sell(10, 50.0, 0, 60.0)


class TestSharpeRatio:
    def test_positive_returns(self):
        returns = np.array([0.01, 0.02, 0.015, 0.005, 0.01])
        sr = calc_sharpe_ratio(returns, risk_free_rate=0.0)
        assert sr > 0
        assert isinstance(sr, float)

    def test_negative_returns(self):
        returns = np.array([-0.01, -0.02, -0.015])
        sr = calc_sharpe_ratio(returns, risk_free_rate=0.0)
        assert sr < 0

    def test_zero_risk_free(self):
        returns = np.array([0.01, 0.02])
        sr = calc_sharpe_ratio(returns, risk_free_rate=0.0)
        assert sr > 0

    def test_with_risk_free_rate(self):
        returns = np.array([0.01, 0.02, 0.015])
        sr_with_rf = calc_sharpe_ratio(returns, risk_free_rate=0.05)
        sr_no_rf = calc_sharpe_ratio(returns, risk_free_rate=0.0)
        assert sr_with_rf < sr_no_rf  # RF reduces excess return

    def test_single_return(self):
        assert calc_sharpe_ratio(np.array([0.01])) == 0.0

    def test_empty_array(self):
        assert calc_sharpe_ratio(np.array([])) == 0.0

    def test_constant_returns_zero_std(self):
        returns = np.array([0.01, 0.01, 0.01])
        assert calc_sharpe_ratio(returns) == 0.0


class TestMaxDrawdown:
    def test_no_drawdown(self):
        nav = np.array([100.0, 110.0, 120.0])
        assert calc_max_drawdown(nav) >= 0  # 0.0 in practice

    def test_with_drawdown(self):
        nav = np.array([100.0, 110.0, 90.0, 95.0, 80.0])
        mdd = calc_max_drawdown(nav)
        assert mdd < 0
        expected = (80.0 - 110.0) / 110.0  # peak 110, trough 80
        assert pytest.approx(mdd, abs=0.01) == expected

    def test_strictly_increasing_no_dd(self):
        nav = np.array([100.0, 101.0, 102.0])
        assert calc_max_drawdown(nav) >= 0

    def test_single_element(self):
        assert calc_max_drawdown(np.array([100.0])) == 0.0

    def test_two_elements_decreasing(self):
        nav = np.array([100.0, 80.0])
        mdd = calc_max_drawdown(nav)
        assert mdd < 0

    def test_all_zeros(self):
        assert calc_max_drawdown(np.array([0.0, 0.0, 0.0])) == 0.0

    def test_negative_nav(self):
        assert calc_max_drawdown(np.array([-100.0, -50.0])) == 0.0


class TestVolatility:
    def test_positive(self):
        returns = np.array([0.01, -0.01, 0.005, -0.005])
        vol = calc_volatility(returns)
        assert vol > 0

    def test_constant_returns(self):
        assert calc_volatility(np.array([0.01, 0.01, 0.01])) == 0.0

    def test_single_return(self):
        assert calc_volatility(np.array([0.01])) == 0.0

    def test_empty_array(self):
        assert calc_volatility(np.array([])) == 0.0


class TestDailyReturns:
    def test_basic(self):
        prices = np.array([100.0, 110.0, 99.0])
        rets = calc_daily_returns(prices)
        expected = np.array([0.1, -0.1])
        np.testing.assert_array_almost_equal(rets, expected)

    def test_single_price(self):
        rets = calc_daily_returns(np.array([100.0]))
        assert len(rets) == 0

    def test_empty_array(self):
        rets = calc_daily_returns(np.array([]))
        assert len(rets) == 0

    def test_decreasing(self):
        prices = np.array([100.0, 90.0, 81.0])
        rets = calc_daily_returns(prices)
        expected = np.array([-0.1, -0.1])
        np.testing.assert_array_almost_equal(rets, expected)
