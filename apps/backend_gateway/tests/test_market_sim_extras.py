"""Test wiring: T+2 settlement release & corporate events trong MarketSim.tick."""

import pytest
from realtime import market_sim as market_sim_module
from realtime.market_sim import MarketSim


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def __call__(self) -> float:
        return self.value


def make_sim() -> tuple[MarketSim, list[float], list[float]]:
    release_calls: list[float] = []
    corp_calls: list[float] = []
    clock = FakeClock(start=1000.0)

    async def fake_update_prices(dt_years: float) -> None:
        pass

    async def noop() -> None:
        pass

    async def fake_release() -> None:
        release_calls.append(1)

    async def fake_corp() -> None:
        corp_calls.append(1)

    sim = MarketSim(
        tick_seconds=3.0,
        local_mode=True,
        update_prices=fake_update_prices,
        match_orders=noop,
        release_settlements=fake_release,
        apply_corporate_events=fake_corp,
        now=clock,
    )
    return sim, release_calls, corp_calls


@pytest.mark.asyncio
async def test_first_tick_no_release() -> None:
    sim, release_calls, corp_calls = make_sim()
    await sim.tick()
    assert release_calls == []
    assert corp_calls == []


@pytest.mark.asyncio
async def test_tick_releases_settlements_and_corporate_events() -> None:
    sim, release_calls, corp_calls = make_sim()
    await sim.tick()
    sim._now.advance(6.0)
    await sim.tick()
    assert release_calls == [1]
    assert corp_calls == [1]


@pytest.mark.asyncio
async def test_singleton_wires_new_fallbacks() -> None:
    sim = market_sim_module.market_sim
    assert sim._release_settlements is market_sim_module.default_release_settlements
    assert (
        sim._apply_corporate_events
        is market_sim_module.default_apply_corporate_events
    )
