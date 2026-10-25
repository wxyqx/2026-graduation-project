"""
【简易限流】——防止有人反复猜密码

原理：给每个 key（比如「手机号 138xxxx」）记一串「失败时间」，
窗口内失败次数达到上限就拒绝，过了窗口自动清空。

限制：数据在内存里，进程重启就清零；只适合本地单进程 uvicorn。
以后要多进程部署，换成 Redis 或数据库计数即可。
"""
import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_events: dict[str, deque[float]] = defaultdict(deque)


def _prune(key: str, window_seconds: int) -> deque[float]:
    """丢掉窗口之外的旧记录。调用方必须已经持有锁。"""
    q = _events[key]
    cutoff = time.monotonic() - window_seconds
    while q and q[0] < cutoff:
        q.popleft()
    return q


def too_many(key: str, limit: int, window_seconds: int) -> bool:
    """窗口内失败次数是否已达上限。"""
    if limit <= 0:
        return False
    with _lock:
        q = _prune(key, window_seconds)
        return len(q) >= limit


def record_failure(key: str, window_seconds: int) -> None:
    """记一次失败。"""
    with _lock:
        q = _prune(key, window_seconds)
        q.append(time.monotonic())


def record_event(key: str, window_seconds: int) -> None:
    """记一次事件（投递成功也用它计数，避免「失败次数」这个语义把人绕晕）。"""
    record_failure(key, window_seconds)


def reset(key: str) -> None:
    """成功后清空该 key 的失败记录。"""
    with _lock:
        _events.pop(key, None)


def remaining_seconds(key: str, window_seconds: int) -> int:
    """还要等多少秒才能再试（给前端提示用）。"""
    with _lock:
        q = _prune(key, window_seconds)
        if not q:
            return 0
        return max(1, int(window_seconds - (time.monotonic() - q[0])))
