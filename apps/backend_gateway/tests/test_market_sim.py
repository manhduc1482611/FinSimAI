import asyncio

import pytest
from realtime import market_sim as market_sim_module
from realtime.market_sim import MAX_DT_SECONDS, MarketSim, sim_dt_years


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def __call__(self) -> float:
        return self.value


class AlwaysLeader:
    is_leader = True

    async def acquire(self) -> int:
        return 1


class NeverLeader:
    is_leader = False

    async def acquire(self) -> int:
        return 0


def make_sim(
    *,
    update: list[float] | None = None,
    match_calls: list[int] | None = None,
    clock: FakeClock | None = None,
    tick_seconds: float = 3.0,
    local_mode: bool = True,
) -> MarketSim:
    update_calls: list[float] = [] if update is None else update
    match_list: list[int] = [] if match_calls is None else match_calls

    async def fake_update_prices(dt_years: float) -> None:
        update_calls.append(dt_years)

    async def fake_match_orders() -> None:
        match_list.append(1)

    return MarketSim(
        tick_seconds=tick_seconds,
        local_mode=local_mode,
        update_prices=fake_update_prices,
        match_orders=fake_match_orders,
        now=clock or FakeClock(),
    )


@pytest.mark.asyncio
async def test_sim_dt_years_compresses_time() -> None:
    # 1 phút thực = 1 ngày giao dịch ảo = 1/252 năm.
    assert sim_dt_years(60.0) == pytest.approx(1.0 / 252.0)
    assert sim_dt_years(3.0) == pytest.approx((3.0 / 60.0) / 252.0)
    assert sim_dt_years(0.0) == 0.0
    assert sim_dt_years(-10.0) == 0.0


@pytest.mark.asyncio
async def test_first_tick_only_records_milestone() -> None:
    update_calls: list[float] = []
    match_calls: list[int] = []
    clock = FakeClock(start=1000.0)
    sim = make_sim(update=update_calls, match_calls=match_calls, clock=clock)

    await sim.tick()

    assert update_calls == []
    assert match_calls == []
    assert sim.last_tick_ts == 1000.0


@pytest.mark.asyncio
async def test_tick_moves_prices_then_matches_orders() -> None:
    update_calls: list[float] = []
    match_calls: list[int] = []
    clock = FakeClock(start=1000.0)
    sim = make_sim(update=update_calls, match_calls=match_calls, clock=clock)

    await sim.tick()
    clock.advance(6.0)
    await sim.tick()

    assert update_calls == [pytest.approx(sim_dt_years(6.0))]
    assert match_calls == [1]
    assert sim.last_tick_ts == 1006.0


@pytest.mark.asyncio
async def test_tick_caps_elapsed_at_one_sim_day() -> None:
    """Downtime/failover dài không được tạo cú nhảy giá phi lý (cap 1 ngày ảo)."""
    update_calls: list[float] = []
    clock = FakeClock(start=1000.0)
    sim = make_sim(update=update_calls, clock=clock)

    await sim.tick()
    clock.advance(MAX_DT_SECONDS * 50.0)
    await sim.tick()

    assert update_calls == [pytest.approx(sim_dt_years(MAX_DT_SECONDS))]


@pytest.mark.asyncio
async def test_run_loop_ticks_only_when_leader() -> None:
    """Fail-closed: không phải leader → không dịch chuyển giá / khớp lệnh."""
    update_calls: list[float] = []
    match_calls: list[int] = []
    sim = make_sim(
        update=update_calls,
        match_calls=match_calls,
        tick_seconds=0.02,
        local_mode=False,
    )
    sim._election = NeverLeader()  # type: ignore[assignment]
    sim._last_tick_ts = 0.0

    await sim.start()
    await asyncio.sleep(0.1)
    await sim.stop()

    assert update_calls == []
    assert match_calls == []

    sim._election = AlwaysLeader()  # type: ignore[assignment]
    await sim.start()
    await asyncio.sleep(0.1)
    await sim.stop()

    assert len(update_calls) > 0
    assert len(match_calls) > 0


@pytest.mark.asyncio
async def test_run_loop_graceful_cancel() -> None:
    sim = make_sim(tick_seconds=0.02)
    sim._election = AlwaysLeader()  # type: ignore[assignment]
    sim._last_tick_ts = 0.0

    await sim.start()
    await asyncio.sleep(0.05)
    await sim.stop()

    assert sim._task is None
    assert sim.is_leader is True


@pytest.mark.asyncio
async def test_default_singleton_and_fallbacks_wired() -> None:
    sim = market_sim_module.market_sim
    assert isinstance(sim, MarketSim)
    assert sim._update_prices is market_sim_module.default_update_prices
    assert sim._match_orders is market_sim_module.default_match_orders
    # Leader lock dùng namespace riêng — không đụng lock của price broadcaster.
    assert sim._leader_lock_key == "finsim:ws:leader:market_sim"


@pytest.mark.asyncio
async def test_default_dt_for_zero_elapsed() -> None:
    # Trường hợp đo 2 lần trong cùng tích tắc: không nhảy giá dù là leader.
    update_calls: list[float] = []
    clock = FakeClock(start=1000.0)
    sim = make_sim(update=update_calls, clock=clock)

    await sim.tick()
    await sim.tick()  # không advance clock → elapsed 0

    assert update_calls == [0.0]
