"""Metrics registry tối giản (Prometheus text format) — không thêm dependency.

Ghi nhận trong process gateway:
- ``finsim_http_requests_total`` — request theo (route bucket, method, status).
- ``finsim_http_request_duration_seconds`` — histogram latency (cumulative).
- ``finsim_http_errors_total`` — response 5xx (dùng cho alert trực quan).
- ``finsim_ws_active_connections`` — gauge số WebSocket đang kết nối.
- ``finsim_uptime_seconds`` + ``finsim_process_resident_memory_bytes`` (khi O/S hỗ trợ).

``GET /metrics`` xuất ra đúng định dạng Prometheus để công cụ scrape (Render
có sẵn metrics proxy, hoặc Grafana Cloud / Prometheus bên ngoài) đọc được.

Cardinality: path được bucket hoá (UUID / số → ``{id}``) để tránh mỗi news_id
lại tạo ra 1 series riêng — tổng series ổn định theo số route thực tế.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections import Counter, defaultdict

_started = time.monotonic()

_requests: defaultdict[str, defaultdict[str, Counter]] = defaultdict(
    lambda: defaultdict(Counter)
)
_latency: Counter = Counter()  # index bucket (le) -> count
_latency_sum_seconds = 0.0
_errors_total = 0
_LOCK = threading.Lock()

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^\d+$"
)


def _bucket_path(path: str) -> str:
    """Normalise path: UUID / số → ``{id}`` (giữ cardinality thấp)."""
    parts = path.split("/")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if _ID_RE.match(part):
            out.append("{id}")
        else:
            out.append(part)
    return "/" + "/".join(out)


def _latency_index(duration: float) -> int:
    for i, bound in enumerate(_LATENCY_BUCKETS):
        if duration <= bound:
            return i
    return len(_LATENCY_BUCKETS)


def record_request(path: str, method: str, status: int, duration: float) -> None:
    global _errors_total, _latency_sum_seconds
    bucket = _bucket_path(path)
    with _LOCK:
        _requests[bucket][method][status] += 1
        _latency[_latency_index(duration)] += 1
        _latency_sum_seconds += duration
        if status >= 500:
            _errors_total += 1


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _collect_memory_bytes() -> float:
    """RSS của process hiện tại — dùng resource trên POSIX, psapi trên Windows."""
    if os.name == "nt":
        return _windows_rss_bytes()
    try:
        import resource  # type: ignore[import-not-found]

        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:  # noqa: BLE001 - nền tảng không hỗ trợ → bỏ qua metric
        return 0.0


def _windows_rss_bytes() -> float:
    try:
        import ctypes
        from ctypes import wintypes

        class _ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(_ProcessMemoryCounters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return float(counters.WorkingSetSize)
    except Exception:  # noqa: BLE001 - psapi bị chặn → không đo được
        return 0.0
    return 0.0


def collect() -> str:
    """Trả toàn bộ metrics ở dạng Prometheus text format (content-type text/plain)."""
    with _LOCK:
        requests_snapshot = {
            bucket: {method: dict(statuses) for method, statuses in methods.items()}
            for bucket, methods in _requests.items()
        }
        latency_snapshot = dict(_latency)
        errors_total = _errors_total

    lines: list[str] = []
    lines.append("# HELP finsim_http_requests_total Tổng request HTTP theo route/method/status")
    lines.append("# TYPE finsim_http_requests_total counter")
    for bucket in sorted(requests_snapshot):
        for method in sorted(requests_snapshot[bucket]):
            for status in sorted(requests_snapshot[bucket][method]):
                n = requests_snapshot[bucket][method][status]
                lines.append(
                    f'finsim_http_requests_total{{route="{_escape(bucket)}",'
                    f'method="{method}",status="{status}"}} {n}'
                )

    lines.append("# HELP finsim_http_request_duration_seconds Phân bố latency HTTP (giây)")
    lines.append("# TYPE finsim_http_request_duration_seconds histogram")
    total_count = sum(latency_snapshot.values())
    cumulative = 0
    for i, bound in enumerate(_LATENCY_BUCKETS):
        cumulative += latency_snapshot.get(i, 0)
        lines.append(f'finsim_http_request_duration_seconds_bucket{{le="{bound}"}} {cumulative}')
    lines.append(f"finsim_http_request_duration_seconds_bucket{{le=\"+Inf\"}} {total_count}")
    lines.append(f"finsim_http_request_duration_seconds_sum {_latency_sum_seconds:.6f}")
    lines.append(f"finsim_http_request_duration_seconds_count {total_count}")

    lines.append("# HELP finsim_http_errors_total Tổng response 5xx")
    lines.append("# TYPE finsim_http_errors_total counter")
    lines.append(f"finsim_http_errors_total {errors_total}")

    try:
        from realtime.connection_manager import connection_manager

        active = int(connection_manager.active_connections)
    except Exception:  # noqa: BLE001 - metrics không được làm chết endpoint
        active = 0
    lines.append("# HELP finsim_ws_active_connections Số WebSocket đang kết nối")
    lines.append("# TYPE finsim_ws_active_connections gauge")
    lines.append(f"finsim_ws_active_connections {active}")

    lines.append("# HELP finsim_uptime_seconds Số giây process đã chạy")
    lines.append("# TYPE finsim_uptime_seconds gauge")
    lines.append(f"finsim_uptime_seconds {int(time.monotonic() - _started)}")

    memory = _collect_memory_bytes()
    if memory > 0:
        lines.append("# HELP finsim_process_resident_memory_bytes RSS của process (bytes)")
        lines.append("# TYPE finsim_process_resident_memory_bytes gauge")
        lines.append(f"finsim_process_resident_memory_bytes {int(memory)}")

    return "\n".join(lines) + "\n"
