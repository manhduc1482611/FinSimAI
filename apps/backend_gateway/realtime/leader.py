"""Leader election fail-closed cho background task multi-worker.

Khi chạy nhiều worker/replica, chỉ đúng 1 worker được phép thực hiện tác vụ
"quản trị" (poll DB + phát tick giá / bù phát khớp lệnh). Cơ chế dựa trên Redis lock:
- Giành quyền: ``SET lock token NX EX ttl``.
- Gia hạn: ``SET lock token XX EX ttl`` — leader giữ quyền miễn là còn sống và tới
  tick kế tiếp; leader chết → lock hết TTL → worker khác giành được.
- Fencing token: mỗi NHIỆM KỲ leader mới nhận một mã số tăng dần (Redis ``INCR``
  trên counter riêng). Mọi broadcast phải mang kèm token này; phía tiêu thụ chỉ
  chấp nhận dữ liệu của token CAO hơn token đã thấy — chặn "split-brain tạm thời"
  khi leader cũ bị pause (GC/lag) lâu hơn TTL, tỉnh dậy muộn và vẫn phát nốt tin
  đang dở với token thấp.

Fail-closed (mặc định, an toàn multi-worker): nếu Redis lỗi/lạc mạng, worker KHÔNG
được tự xưng leader. Khi Redis chập chờn mà mọi worker tự nhận leader → split-brain:
N worker cùng SELECT DB mỗi giây + cùng phát message trùng lặp xuống client. Hệ quả
chấp nhận được khi fail-closed: feed tạm dừng tới khi Redis quay lại (khối realtime
đã phụ thuộc Redis ngay từ đầu: backplane cũng rơi về local-only).

Chế độ ``local_mode`` (chạy đúng 1 instance / dev / test): ``acquire()`` luôn trả
token tăng dần cục bộ mà không đụng Redis — không có worker nào khác để split-brain.
"""

from __future__ import annotations

from typing import Any, cast

from core.cache import get_cache

# Gia hạn lock theo nguyên tố (atomic): chỉ thành công nếu key vẫn do TOKEN của
# worker này giữ. KHÔNG dùng ``SET key value XX EX ttl`` — lệnh đó chỉ kiểm tra
# key TỒN TẠI, không kiểm tra VALUE. Kịch bản lỗi: leader A bị treo lâu hơn TTL,
# Redis xoá lock, leader B giành được; A tỉnh dậy gọi ``SET XX`` → Redis ghi đè
# token của B bằng token của A → CẢ HAI cùng tin mình là leader (split-brain).
#
# KEYS[1] = lock key, KEYS[2] = fence counter key. ARGV[1] = token, ARGV[2] = ttl_ms.
# - Gia hạn (đang giữ): pexpire lock, trả về fence token HIỆN TẠI (cùng nhiệm kỳ).
# - Giành mới: set lock + INCR counter → fence token mới CAO HƠN nhiệm kỳ cũ.
# - Thua: trả 0.
ACQUIRE_OR_RENEW_LUA = """
local current = redis.call('get', KEYS[1])
if current == ARGV[1] then
    redis.call('pexpire', KEYS[1], ARGV[2])
    return redis.call('get', KEYS[2])
end
if not current then
    redis.call('set', KEYS[1], ARGV[1], 'PX', ARGV[2])
    return redis.call('incr', KEYS[2])
end
return 0
"""


class LeaderElection:
    """Bầu cử leader dựa trên Redis lock nguyên tố (Lua), fail-closed khi mất Redis.

    - Giành quyền: SET (NX) atomically trong Lua.
    - Gia hạn: ``pexpire`` chỉ khi ``GET(key) == token`` — một leader hết TTL bị
      leader khác thay thế KHÔNG thể tự gia hạn lại và đè token đối thủ.
    - Fencing token: ``acquire()`` trả về mã nhiệm kỳ tăng dần (``INCR`` trên
      counter riêng), ``0`` khi không phải leader. Token KHÔNG hết hạn — kể cả khi
      lock hết TTL, counter vẫn cao hơn để nhiệm kỳ tiếp theo không lặp mã.
    """

    def __init__(
        self,
        lock_key: str,
        *,
        token: str,
        ttl: int,
        local_mode: bool = False,
    ) -> None:
        self._lock_key = lock_key
        self._token = token
        self._ttl = ttl
        self._ttl_ms = ttl * 1000
        self._fence_key = f"{lock_key}:fence"
        self._local_mode = local_mode
        self._is_leader = local_mode
        self._fencing_token = 1 if local_mode else 0
        self._local_fence = 1 if local_mode else 0

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    @property
    def fencing_token(self) -> int:
        """Mã nhiệm kỳ hiện tại (0 = không phải leader)."""
        return self._fencing_token

    async def acquire(self) -> int:
        """Cố giành/gia hạn lock.

        Trả về fencing token của nhiệm kỳ hiện tại (>0 khi là leader, ``0`` khi
        không). Token mới cao hơn token của mọi nhiệm kỳ trước — broadcast phải
        mang token này và receiver chỉ nhận token cao hơn đã thấy.
        """
        if self._local_mode:
            if not self._is_leader:
                self._local_fence += 1
            self._fencing_token = self._local_fence
            self._is_leader = True
            return self._fencing_token
        try:
            client = cast(Any, get_cache())
            result = await client.eval(
                ACQUIRE_OR_RENEW_LUA,
                2,
                self._lock_key,
                self._fence_key,
                self._token,
                self._ttl_ms,
            )
            self._fencing_token = int(result) if result is not None else 0
            self._is_leader = self._fencing_token > 0
        except Exception:
            # Fail-closed: mất Redis → không tự xưng leader (tránh split-brain).
            self._is_leader = False
            self._fencing_token = 0
        return self._fencing_token
