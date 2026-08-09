"""Load test cho FinSimAI backend gateway.

Chạy N user ảo (asyncio + httpx) cùng lúc, mỗi user thực hiện một chuỗi
request ngẫu nhiên trọng số hóa vào các endpoint đọc chính (news, companies,
social, knowledge), báo cáo RPS + phân vị latency + phân bố status.

Ví dụ:
    python scripts/load_test/loadtest.py --url http://localhost:8000 --users 25 --duration 30
    python scripts/load_test/loadtest.py --login admin --password secret --users 10 --duration 20 --json result.json

Không cần thư viện ngoài stdlib ngoài httpx (đã là dependency của gateway).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

PUBLIC_ENDPOINTS: dict[str, float] = {
    "/api/v1/news": 4.0,
    "/api/v1/companies": 3.0,
    "/api/v1/social": 2.0,
    "/api/v1/knowledge": 1.0,
    "/api/v1/tasks": 0.5,
}

DETAIL_ENDPOINTS: dict[str, tuple[str, str]] = {
    "/api/v1/news/{id}": ("/api/v1/news", "id"),
    "/api/v1/companies/{id}": ("/api/v1/companies", "id"),
}


def _weighted_pick(weights: dict[str, float], rng: random.Random) -> str:
    total = sum(weights.values())
    r = rng.uniform(0, total)
    acc = 0.0
    for key, w in weights.items():
        acc += w
        if r <= acc:
            return key
    return next(iter(weights))


@dataclass
class Stats:
    latencies: list[float] = field(default_factory=list)
    statuses: Counter = field(default_factory=Counter)
    started: float = field(default_factory=time.monotonic)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def record(self, latency: float, status: int) -> None:
        self.latencies.append(latency)
        self.statuses[status] += 1

    def pct(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        data = sorted(self.latencies)
        idx = min(len(data) - 1, int(len(data) * p))
        return data[idx] * 1000.0

    def summary(self) -> dict[str, Any]:
        n = len(self.latencies)
        elapsed = max(time.monotonic() - self.started, 1e-9)
        ok = sum(c for s, c in self.statuses.items() if 200 <= s < 400)
        return {
            "requests": n,
            "rps": round(n / elapsed, 1),
            "success_rate": round(ok / n * 100, 1) if n else 0.0,
            "mean_ms": round(statistics.fmean(self.latencies) * 1000, 1) if n else 0.0,
            "p50_ms": round(self.pct(0.50), 1),
            "p75_ms": round(self.pct(0.75), 1),
            "p90_ms": round(self.pct(0.90), 1),
            "p95_ms": round(self.pct(0.95), 1),
            "p99_ms": round(self.pct(0.99), 1),
            "statuses": {str(s): c for s, c in sorted(self.statuses.items())},
            "errors": self.errors[:10],
        }


async def _fetch_id_pools(client: httpx.AsyncClient, base: str) -> dict[str, list[str]]:
    pools: dict[str, list[str]] = {}
    for detail_path, (list_path, key) in DETAIL_ENDPOINTS.items():
        try:
            resp = await client.get(base + list_path, params={"limit": 50})
            resp.raise_for_status()
            pools[detail_path] = [item[key] for item in resp.json().get("items", []) if item.get(key)]
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] không lấy được danh sách id cho {detail_path}: {exc}")
            pools[detail_path] = []
    return pools


async def _run_worker(
    name: str,
    client: httpx.AsyncClient,
    base: str,
    stats: Stats,
    id_pools: dict[str, list[str]],
    rng: random.Random,
    stop: asyncio.Event,
    login: tuple[str, str] | None,
) -> None:
    token: str | None = None
    if login:
        username, password = login
        try:
            resp = await client.post(base + "/api/v1/auth/login", json={"username": username, "password": password})
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                stats.record(resp.elapsed.total_seconds(), resp.status_code)
            else:
                stats.record(resp.elapsed.total_seconds(), resp.status_code)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append((name, f"login: {exc}"))

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    while not stop.is_set():
        path = _weighted_pick(PUBLIC_ENDPOINTS, rng)
        if path in id_pools and id_pools[path]:
            path = path.format(id=rng.choice(id_pools[path]))
        elif path in id_pools:
            continue
        try:
            resp = await client.get(base + path, params={"limit": rng.randint(5, 20)}, headers=headers)
            stats.record(resp.elapsed.total_seconds(), resp.status_code)
        except httpx.HTTPError as exc:
            stats.statuses[0] += 1
            stats.errors.append((name, f"{path}: {exc}"))
        await asyncio.sleep(rng.uniform(0, 0.05))


async def _amain(args: argparse.Namespace) -> Stats:
    base = args.url.rstrip("/")
    limits = httpx.Limits(max_connections=args.users * 2, max_keepalive_connections=args.users)
    timeout = httpx.Timeout(args.timeout)
    stats = Stats()
    login = (args.login, args.password) if args.login else None

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        print(f"[load] lấy id pool từ {base} ...")
        id_pools = await _fetch_id_pools(client, base)
        print(
            "[load] id pool: "
            + ", ".join(f"{path}->{len(ids)}" for path, ids in id_pools.items())
        )

        stop = asyncio.Event()
        seed = int(time.monotonic())
        workers = [
            asyncio.create_task(
                _run_worker(
                    f"user-{i}",
                    client,
                    base,
                    stats,
                    id_pools,
                    random.Random(seed + i),
                    stop,
                    login,
                )
            )
            for i in range(args.users)
        ]

        print(f"[load] chạy {args.users} user trong {args.duration}s ...")
        try:
            await asyncio.sleep(args.duration)
        finally:
            stop.set()
        await asyncio.gather(*workers, return_exceptions=True)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test FinSimAI gateway")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--login")
    parser.add_argument("--password", default="")
    parser.add_argument("--json")
    args = parser.parse_args()
    if args.users < 1 or args.duration < 1:
        parser.error("--users và --duration phải >= 1")

    stats = asyncio.run(_amain(args))
    summary = stats.summary()
    print("\n=== KẾT QUẢ LOAD TEST ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[load] đã ghi kết quả vào {out}")
    return 0 if summary["success_rate"] >= 95.0 else 2


if __name__ == "__main__":
    sys.exit(main())
