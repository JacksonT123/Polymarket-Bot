"""Tier-based position sizing with all promotion/demotion guardrails."""
from datetime import datetime, timezone, timedelta
from config.settings import (
    TIER_TABLE, ROLLING_BANKROLL_WINDOW_DAYS, PROMOTION_GRACE_DAYS,
    MAX_TIERS_PROMOTED_PER_WEEK,
)
from src.core.models import TradeParams
import structlog

log = structlog.get_logger(__name__)


def compute_tier(rolling_7d_avg_bankroll: float, override: int | None = None) -> int:
    if override is not None:
        return max(0, min(len(TIER_TABLE) - 1, override))
    for i in range(len(TIER_TABLE) - 1, -1, -1):
        if rolling_7d_avg_bankroll >= TIER_TABLE[i]["min_bankroll"]:
            return i
    return 0


def get_trade_params(tier: int) -> TradeParams:
    t = TIER_TABLE[tier]
    return TradeParams(
        tier=tier,
        trade_size_usd=t["trade_size"],
        max_positions=t["max_positions"],
        max_deployed_pct=t["max_deployed_pct"],
    )


class TierManager:
    """
    Manages tier state with promotion guardrails:
    - Promotion: 7 consecutive days above next threshold
    - Demotion: immediate when rolling avg drops below current floor
    - Max 1 tier promotion per week
    """
    def __init__(
        self,
        current_tier: int = 0,
        override: int | None = None,
    ):
        self.current_tier = current_tier
        self.override = override
        self._days_above_next_threshold: int = 0
        self._last_promotion_date: datetime | None = None

    def update(self, rolling_avg: float) -> tuple[int, str | None]:
        """
        Call daily. Returns (new_tier, reason_if_changed).
        """
        candidate = compute_tier(rolling_avg, self.override)
        reason = None

        if candidate < self.current_tier:
            # Immediate demotion
            old = self.current_tier
            self.current_tier = candidate
            self._days_above_next_threshold = 0
            reason = f"demotion:{old}→{candidate}"
            log.info("tier_demoted", from_tier=old, to_tier=candidate, rolling_avg=rolling_avg)

        elif candidate > self.current_tier:
            # Promotion requires 7 consecutive days + max 1/week
            self._days_above_next_threshold += 1
            if self._days_above_next_threshold >= PROMOTION_GRACE_DAYS:
                if self._within_week_limit():
                    # Only advance one tier at a time
                    new_tier = min(self.current_tier + 1, len(TIER_TABLE) - 1)
                    if self.override is None or new_tier <= self.override:
                        old = self.current_tier
                        self.current_tier = new_tier
                        self._days_above_next_threshold = 0
                        self._last_promotion_date = datetime.now(timezone.utc)
                        reason = f"promotion:{old}→{new_tier}"
                        log.info("tier_promoted", from_tier=old, to_tier=new_tier, rolling_avg=rolling_avg)
        else:
            self._days_above_next_threshold = 0

        return self.current_tier, reason

    def _within_week_limit(self) -> bool:
        if self._last_promotion_date is None:
            return True
        days_since = (datetime.now(timezone.utc) - self._last_promotion_date).days
        return days_since >= 7

    def days_until_next_promotion(self, rolling_avg: float) -> int:
        if self.current_tier >= len(TIER_TABLE) - 1:
            return -1
        next_threshold = TIER_TABLE[self.current_tier + 1]["min_bankroll"]
        if rolling_avg < next_threshold:
            return -1
        return max(0, PROMOTION_GRACE_DAYS - self._days_above_next_threshold)
