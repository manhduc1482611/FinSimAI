import pytest
from realtime import leader as leader_module
from realtime.leader import LeaderElection


class FakeRedis:
    """Stub Redis lock: mô phỏng eval Lua ACQUIRE_OR_RENEW + set/get + fence counter."""

    def __init__(self) -> None:
        self.locks: dict[str, str] = {}
        self.fences: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.raise_error = False

    async def eval(self, script: str, numkeys: int, *args) -> int | str:
        if self.raise_error:
            raise ConnectionError("redis down")
        lock_key, fence_key, token, ttl_ms = args[0], args[1], args[2], args[3]
        current = self.locks.get(lock_key)
        if current == token:
            self.ttls[lock_key] = int(ttl_ms)
            # Gia hạn → giữ nguyên fence token của nhiệm kỳ hiện tại.
            return self.fences.get(fence_key, 0)
        if current is None:
            self.locks[lock_key] = token
            self.fences[fence_key] = self.fences.get(fence_key, 0) + 1
            self.ttls[lock_key] = int(ttl_ms)
            return self.fences[fence_key]
        return 0

    def release(self, key: str) -> None:
        """Mô phỏng lock hết TTL (leader cũ chết)."""
        self.locks.pop(key, None)
        self.ttls.pop(key, None)


def make_election(lock_key: str = "lock:test", token: str = "tok", **kwargs):
    return LeaderElection(lock_key, token=token, ttl=5, **kwargs)


@pytest.mark.asyncio
async def test_acquire_wins_lock_and_renews(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    a = make_election()
    b = make_election(token="tok-b")

    fence_a = await a.acquire()
    assert fence_a > 0  # a giành lock
    assert await b.acquire() == 0  # b thua
    assert await a.acquire() == fence_a  # a gia hạn → GIỮ NGUYÊN fencing token


@pytest.mark.asyncio
async def test_takeover_when_leader_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    a = LeaderElection("lock:test", token="tok-a", ttl=5)
    b = LeaderElection("lock:test", token="tok-b", ttl=5)

    fence_a = await a.acquire()
    redis.release("lock:test")  # a chết, lock hết TTL
    fence_b = await b.acquire()
    assert fence_b > 0  # b tiếp quản
    assert fence_b > fence_a  # fencing token CAO HƠN nhiệm kỳ của a
    assert await a.acquire() == 0  # a (nếu hồi sinh) không giành lại được
    # Token của b KHÔNG bị a ghi đè — đây là regression của lỗi split-brain
    # (SET XX chỉ kiểm tra key tồn tại, không kiểm tra value).
    assert redis.locks["lock:test"] == "tok-b"


@pytest.mark.asyncio
async def test_renew_after_own_lock_keeps_own_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gia hạn lock do chính mình giữ → giữ nguyên token, không đổi chủ."""
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    election = make_election(token="tok-mine")
    first = await election.acquire()
    assert await election.acquire() == first
    assert redis.locks["lock:test"] == "tok-mine"


@pytest.mark.asyncio
async def test_fail_closed_when_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mất Redis → worker KHÔNG được tự xưng leader (chống split-brain)."""
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    election = make_election()
    redis.raise_error = True
    assert await election.acquire() == 0  # fail-closed: không self-elect
    assert election.fencing_token == 0

    redis.raise_error = False
    assert await election.acquire() > 0  # Redis hồi phục → giành lại bình thường


@pytest.mark.asyncio
async def test_fail_closed_demotes_current_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leader đang giữ lock gặp lỗi Redis → bị hạ xuống non-leader (không renew)."""
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    election = make_election()
    assert await election.acquire() > 0
    redis.raise_error = True
    assert await election.acquire() == 0  # không giữ được → fail-closed


@pytest.mark.asyncio
async def test_local_mode_always_leader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chế độ 1 instance (dev/test): luôn là leader, không đụng Redis."""
    redis = FakeRedis()
    redis.raise_error = True
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    election = make_election(local_mode=True)
    assert election.is_leader is True
    first = await election.acquire()
    assert first > 0
    assert await election.acquire() == first  # local: token giữ nguyên khi là leader


@pytest.mark.asyncio
async def test_fencing_token_grows_across_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nhiều đợt giành-giữ-mất liên tiếp → token tăng đơn điệu (receiver bác token cũ)."""
    redis = FakeRedis()
    monkeypatch.setattr(leader_module, "get_cache", lambda: redis)

    tokens: list[int] = []
    for i in range(4):
        e = make_election(token=f"tok-{i}")
        tokens.append(await e.acquire())
        redis.release("lock:test")

    assert all(t > 0 for t in tokens)
    assert tokens == sorted(tokens)
    assert len(set(tokens)) == len(tokens)  # không có token nào bị lặp
