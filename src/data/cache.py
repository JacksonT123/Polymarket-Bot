import time
from typing import Any
from config.settings import CACHE_MARKET_METADATA_TTL_S, CACHE_TOKEN_IDS_TTL_S


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._ttl > 0 and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        expires_at = (time.monotonic() + self._ttl) if self._ttl > 0 else float("inf")
        self._store[key] = (value, expires_at)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


class CacheRegistry:
    def __init__(self):
        self.market_metadata = TTLCache(CACHE_MARKET_METADATA_TTL_S)
        self.token_ids = TTLCache(CACHE_TOKEN_IDS_TTL_S)
        self.wallet_stats = TTLCache(86400)   # 24h — refreshed by daily funnel run

    def clear_all(self) -> None:
        self.market_metadata.clear()
        self.token_ids.clear()
        self.wallet_stats.clear()


_cache: CacheRegistry | None = None


def get_cache() -> CacheRegistry:
    global _cache
    if _cache is None:
        _cache = CacheRegistry()
    return _cache
