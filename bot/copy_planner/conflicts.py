from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from bot.config import get_settings
from bot.models import CopyIntent, DecisionCode, Side


@dataclass
class PendingDelta:
    buy_notional: float = 0.0
    sell_notional: float = 0.0
    updated_at: float = 0.0


class ConflictTracker:
    def __init__(self) -> None:
        self._pending: dict[str, PendingDelta] = defaultdict(PendingDelta)
        self._window = get_settings().conflict_window_seconds

    def _prune(self) -> None:
        now = time.time()
        expired = [k for k, v in self._pending.items() if now - v.updated_at > self._window]
        for k in expired:
            del self._pending[k]

    def check(self, intent: CopyIntent) -> DecisionCode | None:
        self._prune()
        key = intent.condition_id
        p = self._pending[key]
        now = time.time()
        if intent.side == Side.BUY:
            p.buy_notional += intent.target_notional
        else:
            p.sell_notional += intent.target_notional
        p.updated_at = now

        if p.buy_notional > 0 and p.sell_notional > 0:
            net = abs(p.buy_notional - p.sell_notional)
            if net < get_settings().min_copy_for_mode:
                return DecisionCode.CONFLICT_NET_ZERO
            if p.buy_notional > p.sell_notional * 1.5:
                return None
            if p.sell_notional > p.buy_notional * 1.5:
                return None
            return DecisionCode.CONFLICT_OPPOSING_SIGNALS
        return None
