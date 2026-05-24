# Session Handoff

When the user says "read handoff.md," read this entire file before doing anything else. This is the bridge between sessions: where the last session left off, what state the project is in, and what you need to continue without losing context. Make sure to read edits.md as well. Always read the entire codebase no less to get to know it before doing anything.

## Your responsibilities

1. **At session start:** Read this whole file. If anything seems stale, contradictory, or thin, read `edits.md` for the full history before doing anything.
2. **During the session:** Keep the sections below current. This is a living document — overwrite freely (unlike `edits.md`).
3. **Before the session ends, or whenever context starts to feel heavy:** Refresh every section as if a brand-new Claude with zero memory is about to take over. Be specific. Don't assume shared context.
4. **When you finish a task or hit a checkpoint:** Update at least "Recent work," "Current task," and "Next steps" before moving on.
5. **Never leave a section stale.** If something below is no longer true, fix it the moment you notice.

---

# Project state

## Project summary
Polymarket Copy Bot v2.3 — a fully automated copy-trading bot for Polymarket prediction markets. It discovers, validates, and mirrors trades from qualified "lead" wallets. The bot runs a 5-stage wallet funnel (leaderboard → 13 hard DQs → composite scoring → 21-day shadow simulation → active pool of max 5 wallets), then executes fixed-size mirrored trades and exits when the lead exits. No stop-losses, no take-profits — pure mirror strategy. Paper mode by default; live mode plumbed but requires POLYMARKET_PRIVATE_KEY to activate.

## Tech stack
- Python 3.12.10, uv (package manager)
- asyncio + aiohttp for all async work
- SQLAlchemy 2.0 async + asyncpg — PostgreSQL (Neon.tech free tier or local)
- Alembic for DB migrations
- FastAPI + Uvicorn — REST API + WebSocket dashboard backend
- HTMX + Alpine.js + Tailwind (CDN) + Plotly.js (CDN) — no-build-step frontend
- structlog — structured JSON logging
- Click — CLI
- pydantic v2 + pydantic-settings — config and models
- polymarket-apis SDK — Polymarket data/CLOB APIs
- pytest + pytest-asyncio — testing

## Current task
**BOT IS RUNNING** — 16 open positions, 13 shadow wallets. Dashboard at http://localhost:8000.

## Status
Complete and running:
- Phase 1: Core, config, DB, API client ✓
- Phase 2: Wallet funnel (Stages A–F) + all 13 metrics ✓
- Phase 3: Execution engine (poller, filters, sizer, paper fill, order engine) ✓
- Phase 4: Position management + risk + runner.py ✓
- Phase 5: Dashboard (FastAPI + true-black terminal UI + WebSocket + live market data) ✓
- Phase 6: Unit/integration tests + fixtures + docker-compose + CI ✓
- **Setup**: PostgreSQL running locally, migrations applied, bot started ✓
- **GitHub**: https://github.com/JacksonT123/Polymarket-Bot.git — all files committed and pushed ✓

## Recent work (most recent first)
- **Fixed dashboard showing zeros (3 bugs, all fixed):**
  1. `config/settings.py`: `EQUITY_SNAPSHOT_S` 3600→60 — snapshots now every minute (was hourly, seed snapshot showed $0 deployed)
  2. `src/data/polymarket_client.py`: Added `get_token_price(token_id, condition_id)` using gamma API `outcomePrices` as primary source (CLOB SSL fails on Windows); CLOB midpoint as fallback
  3. `src/positions/pricer.py`: Switched to `get_token_price`; writes updated price back to in-memory position objects so equity snapshot sees current unrealized P&L
  4. `src/runner.py` `_equity_snapshot_loop`: Reads fresh positions from DB (`pos_repo.get_open`) instead of stale in-memory list
- **Dashboard full redesign**: `web/index.html` — true black terminal UI, scrolling ticker tape, live position cards with P&L bars, CoinGecko crypto prices, GDELT news feed, animated equity chart
- **New API routes**: `src/api/routes/market_data.py` — `/api/data/market`, `/api/data/markets/active`, `/api/data/price`, `/api/data/prices/bulk`, `/api/data/crypto`, `/api/data/news`
- **setup.py**: Interactive colored CLI with 10-option menu for bot management
- **WebSocket rewrite**: `src/data/clob_websocket.py` connects to `wss://ws-live-data.polymarket.com` global feed

## Next steps
1. **Restart the bot** to pick up the 3 bug fixes — run `uv run polymarket-bot start`. After ~60 seconds the dashboard will show real equity/P&L data.
2. **Verify dashboard** — positions should show current prices, equity curve should update every minute
3. **Monitor promotion** — 13 shadow wallets, need 21 days + ≥25 copies + ≥0.60 capture ratio to promote to active pool

## Open questions / blockers
- POLYMARKET_PRIVATE_KEY not set — live mode locked; paper mode working fine
- Discord / ntfy credentials not set — notifications go to console logs only
- Bot must be restarted to pick up the 3 fixes committed this session

## Key decisions
- `get_trade_params(tier: int)` takes a tier integer, NOT a bankroll. Always call `compute_tier(bankroll)` first.
- `EquitySnapshot` DB columns: `timestamp`, `cash_balance`, `position_value`, `total_equity` (NOT `ts`, `cash_usd`, `deployed_usd`)
- `WalletPoller.run(get_active_wallets, get_shadow_wallets)` takes async callables that return fresh address lists each poll cycle
- `SignalEvent.side` is a string `"YES"` or `"NO"` (not an enum) — don't call `.value` on it
- `SignalRepo.get_recent(wallet_id, limit)` requires wallet_id; use `get_all_recent(limit)` for the dashboard signal feed
- All circuit breaker state lives in the `CircuitBreakerManager` instance inside the runner process — not persisted to DB between restarts
- `TIER_TABLE` is a list of dicts with keys: `min_bankroll`, `trade_size`, `max_positions`, `max_deployed_pct`

## File map
```
config/
  settings.py         # ALL v2.3 constants (TIER_TABLE, DQ_ thresholds, W_ weights, etc.)
  secrets.py          # Env var loading via pydantic-settings
  validators.py       # validate_config() — call at startup

src/core/
  models.py           # Pydantic models: SignalEvent, TradeParams, FillResult, WalletRecord, etc.
  enums.py            # WalletStatus, ExitReason, PositionStatus, CircuitBreakerType, etc.
  clock.py            # now() — mockable UTC clock for tests
  exceptions.py       # All custom exceptions

src/db/
  models.py           # ORM: Wallet, Signal, Position, EquitySnapshot, etc.
  repositories.py     # WalletRepo, PositionRepo, EquityRepo, SignalRepo
  engine.py           # init_engine(), get_session_factory()

src/data/
  polymarket_client.py  # PolymarketClient — wraps polymarket-apis SDK
  rate_limiter.py       # Token bucket per endpoint
  cache.py              # TTL cache for market metadata

src/metrics/           # 13 individual metric files + composite_score.py
src/funnel/            # stage_a through stage_f + orchestrator.py

src/execution/
  sizer.py            # compute_tier(bankroll) → int, get_trade_params(tier) → TradeParams
  filters.py          # run_all_filters(signal, market, cash, params, open_count)
  order_engine.py     # OrderEngine.place_buy(signal, params, volume, category)
  poller.py           # WalletPoller.run(get_active, get_shadow)
  queue.py            # get_signal_queue() singleton

src/positions/
  tracker.py          # State machine: open_position, begin_close, finalize_close
  pricer.py           # PositionPricer — 30s price update loop
  exiter.py           # ExitHandler — all 8 exit reasons

src/risk/
  circuit_breakers.py # CircuitBreakerManager — daily/weekly/permanent halts
  caps.py             # check_portfolio_caps
  killswitch.py       # start_monitor(), check_and_raise()

src/runner.py         # Main entry point — BotRunner orchestrates all async loops
src/api/main.py       # FastAPI app
src/cli/main.py       # Click CLI
web/index.html        # HTMX + Alpine.js dashboard frontend

tests/unit/           # 6 unit test files (filters, sizer, scoring, circuit breakers, etc.)
tests/integration/    # 2 integration test files (order engine, exiter)
scripts/
  seed_db.py          # Seed initial $1000 equity snapshot
  reset_paper.py      # Wipe paper state, keep funnel data
```

## Gotchas
- **uv SSL on Windows**: Always use `--system-certs` flag with `uv add`, e.g. `uv add --system-certs <package>`
- **Alembic env.py**: Custom — converts `postgresql+asyncpg://` to `postgresql+psycopg2://` for offline migrations (sync driver). Online migrations use `async_engine_from_config`. Don't overwrite with `alembic init`.
- **SIGINT on Windows**: `loop.add_signal_handler` raises `NotImplementedError` for SIGTERM on Windows — runner.py handles this with a fallback to `signal.signal()`
- **Circuit breaker state not persisted**: If bot restarts, `CircuitBreakerManager` resets. Daily/weekly halts clear on restart. Permanent halt also clears unless you call `manual_reset_permanent()` explicitly during the session.
- **Wallet funnel is slow on first run**: Stage A fetches 200 wallets with rate-limited API calls. First `funnel run` takes 2–5 minutes.
- **Paper fill slippage**: `simulate_fill` applies slippage based on `market_volume_24h_usd`. If volume is 0 (unknown market), it uses the highest slippage tier (2.5%). Pass real market metadata for accurate simulation.
- **TIER_TABLE dict keys**: `min_bankroll`, `trade_size`, `max_positions`, `max_deployed_pct` — there is no `max_bal` field.

## User preferences for this project
- Keep Handoff.md updated at end of every session
- PostgreSQL from day one (no SQLite)
- Paper mode default; live mode is built but shouldn't be activated without real credentials
- All external stubs (Discord, ntfy, PolyTrack, Polysights) should work silently without credentials
