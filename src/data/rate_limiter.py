import asyncio
import time
from config.settings import RATE_LIMITS


class TokenBucket:
    """Token bucket rate limiter for a single endpoint."""

    def __init__(self, max_tokens: int, window_seconds: int):
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        async with self._lock:
            self._refill()
            while self._tokens < tokens:
                wait = (tokens - self._tokens) / (self.max_tokens / self.window_seconds)
                await asyncio.sleep(min(wait, 1.0))
                self._refill()
            self._tokens -= tokens

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.max_tokens,
            self._tokens + elapsed * (self.max_tokens / self.window_seconds),
        )
        self._last_refill = now

    @property
    def utilization(self) -> float:
        return 1.0 - (self._tokens / self.max_tokens)


class RateLimiterRegistry:
    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {
            key: TokenBucket(max_tokens, window)
            for key, (max_tokens, window) in RATE_LIMITS.items()
        }

    async def acquire(self, endpoint_key: str) -> None:
        bucket = self._buckets.get(endpoint_key)
        if bucket:
            await bucket.acquire()

    def get_utilization(self, endpoint_key: str) -> float:
        bucket = self._buckets.get(endpoint_key)
        return bucket.utilization if bucket else 0.0

    def all_utilizations(self) -> dict[str, float]:
        return {k: b.utilization for k, b in self._buckets.items()}

    def is_conserve_mode(self, endpoint_key: str) -> bool:
        return self.get_utilization(endpoint_key) >= 0.70

    def is_critical_mode(self, endpoint_key: str) -> bool:
        return self.get_utilization(endpoint_key) >= 0.90


_registry: RateLimiterRegistry | None = None


def get_rate_limiter() -> RateLimiterRegistry:
    global _registry
    if _registry is None:
        _registry = RateLimiterRegistry()
    return _registry
