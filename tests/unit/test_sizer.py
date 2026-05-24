"""Unit tests for trade sizer / tier ladder."""
import pytest
from src.execution.sizer import compute_tier, get_trade_params, TierManager
from config.settings import TIER_TABLE


class TestComputeTier:
    def test_below_min_gives_tier_0(self):
        assert compute_tier(50.0) == 0

    def test_at_tier_0_floor(self):
        assert compute_tier(100.0) == 0

    def test_at_tier_1_floor(self):
        assert compute_tier(250.0) == 1

    def test_at_max_tier_floor(self):
        max_tier = len(TIER_TABLE) - 1
        bankroll = TIER_TABLE[max_tier]["min_bankroll"]
        assert compute_tier(float(bankroll)) == max_tier

    def test_large_bankroll_gives_max_tier(self):
        max_tier = len(TIER_TABLE) - 1
        assert compute_tier(10_000_000.0) == max_tier

    def test_override_respected(self):
        assert compute_tier(100.0, override=3) == 3

    def test_override_clamped_to_valid_range(self):
        assert compute_tier(100.0, override=999) == len(TIER_TABLE) - 1


class TestGetTradeParams:
    def test_returns_trade_params(self):
        params = get_trade_params(0)
        assert params.trade_size_usd == TIER_TABLE[0]["trade_size"]
        assert params.max_positions == TIER_TABLE[0]["max_positions"]
        assert params.max_deployed_pct == TIER_TABLE[0]["max_deployed_pct"]

    def test_trade_size_increases_with_tier(self):
        small = get_trade_params(0)
        large = get_trade_params(len(TIER_TABLE) - 1)
        assert large.trade_size_usd > small.trade_size_usd


class TestTierManager:
    def test_demotion_is_immediate(self):
        tm = TierManager(current_tier=3)
        # Balance drops below tier 3 threshold
        new_tier, reason = tm.update(500.0)  # tier 2 range
        assert new_tier < 3
        assert reason is not None
        assert "demotion" in reason

    def test_promotion_requires_grace_days(self):
        tm = TierManager(current_tier=0)
        # Balance at tier 1 level but haven't hit grace days yet
        for day in range(6):
            new_tier, reason = tm.update(300.0)
        assert new_tier == 0  # not promoted yet

    def test_promotion_after_grace_days(self):
        from config.settings import PROMOTION_GRACE_DAYS
        tm = TierManager(current_tier=0)
        result_tier = 0
        for day in range(PROMOTION_GRACE_DAYS):
            result_tier, _ = tm.update(300.0)  # tier 1 range
        assert result_tier == 1
