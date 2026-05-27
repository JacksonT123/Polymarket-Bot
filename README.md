# Polymarket Copy Trader

Full-stack copy trader: **auto wallet discovery**, per-trade mirroring, **unified paper/live execution** (same CLOB book pricing), conflict rules, redeem pass, WebSocket dashboard.

## Quick start

```powershell
copy .env.example .env
pip install -e .
python -m bot.main
```

Dashboard: **http://127.0.0.1:8787/dashboard**

## Paper → Live (one switch)

1. Paper: `BOT_MODE=PAPER` (default), $100 virtual bankroll.
2. Live: set in `.env`:
   - `BOT_MODE=LIVE`
   - `POLYGON_PRIVATE_KEY=...`
   - `POLYMARKET_PROXY_ADDRESS=...` (your Polymarket proxy)
   - CLOB creds optional (derived from key if omitted)

Same code path: `execute_copy()` → CLOB book → plan fill → paper ledger **or** live order.

## Features

| Feature | Status |
|---------|--------|
| Auto leaderboard discovery | Yes |
| Standby roster (30) | Yes |
| Anti-sybil clusters | Yes |
| Activity polling | Yes |
| CLOB book fills (paper + live) | Yes |
| Portfolio-% sizing | Yes |
| Conflict detection | Yes |
| Decision audit log | Yes |
| WebSocket dashboard | Yes |
| Auto-redeem resolved | Yes |
| Chain listener (optional) | Yes (needs `pip install -e ".[chain]"`) |

See [strategy.md](strategy.md) for full design.
