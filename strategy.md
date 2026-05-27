# Strategy — Polymarket copy trader

## Goal

Mirror **every buy/sell** from an auto-discovered roster of top wallets. No discretionary strategy beyond **who** to follow and **how much** to size each copy.

## Execution (paper = live)

One path: `build_intent` → risk caps → **`execute_copy()`**

1. Fetch CLOB order book for the leader’s token
2. Walk the book (same VWAP + slippage logic)
3. **PAPER**: ledger fill at planned price/size  
4. **LIVE**: `post_live_order()` (FAK/FOK) then same ledger update

Switch: set `BOT_MODE=LIVE` and credentials in `.env` (see `.env.example`).

## Discovery

- Poll Polymarket Data API leaderboard (~200 candidates)
- Score on 30d PnL, win rate, activity, anti-gaming filters
- Cluster by overlapping markets → one wallet per cluster
- **15 active** + **30 standby**; re-run every `DISCOVERY_INTERVAL_HOURS`

## Sizing

Portfolio-% of leader trade vs cached leader bankroll, capped by:

- `MAX_COPY_PCT_PER_TRADE`, `MAX_LEADER_FRACTION_PER_TRADE`
- Per-market and open-market caps

## Risk

- Kill switch on daily loss (optional)
- Conflict window: skip if leaders disagree on same market

## Ops

- Activity API poll ~1.5s per leader (parallel)
- Optional chain block listener (stub; enable with `[chain]` extra)
- Redeem pass: exit positions when mid ≈ 0 or 1
- Full **decision_log** + WebSocket dashboard

## Honest limits

- Paper fills ≠ guaranteed live PnL (latency, partial fills, fees)
- Leaderboard wallets can churn; past performance ≠ future results
