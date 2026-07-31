import time
from asyncio import Lock
from collections import defaultdict

WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5

_attempts: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _prune(key: str, now: float) -> list[float]:
    kept = [t for t in _attempts[key] if now - t < WINDOW_SECONDS]
    _attempts[key] = kept
    return kept


async def record_failure(key: str) -> None:
    async with _lock:
        now = time.monotonic()
        _prune(key, now)
        _attempts[key].append(now)


async def is_blocked(key: str) -> bool:
    async with _lock:
        now = time.monotonic()
        return len(_prune(key, now)) >= MAX_ATTEMPTS
