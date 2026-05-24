"""Dedup gate: prevents copying same (market_id, side) twice."""


class DedupRegistry:
    """
    In-memory dedup. Key = (market_id, side).
    Lock is set ONLY after successful execution — a skipped signal doesn't block.
    """
    def __init__(self):
        self._keys: set[str] = set()

    def is_duplicate(self, market_id: str, side: str) -> bool:
        return self._make_key(market_id, side) in self._keys

    def lock(self, market_id: str, side: str) -> None:
        self._keys.add(self._make_key(market_id, side))

    def unlock(self, market_id: str, side: str) -> None:
        self._keys.discard(self._make_key(market_id, side))

    def _make_key(self, market_id: str, side: str) -> str:
        return f"{market_id}:{side}"

    def active_count(self) -> int:
        return len(self._keys)

    def clear(self) -> None:
        self._keys.clear()
