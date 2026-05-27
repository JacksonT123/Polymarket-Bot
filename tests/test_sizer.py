from bot.copy_planner.portfolio_sizer import compute_copy_notional
from bot.models import LeaderTradeEvent, Side


def test_compute_copy_notional_basic():
    ev = LeaderTradeEvent(
        event_id="t1",
        leader_proxy="0xabc",
        condition_id="c1",
        token_id="tok",
        side=Side.BUY,
        price=0.5,
        usdc_size=50.0,
        timestamp=1,
        tx_hash="tx",
    )
    target, frac, _ = compute_copy_notional(ev, leader_bankroll=1000.0, my_bankroll=100.0)
    assert target >= 1.0
    assert 0 < frac <= 0.25
