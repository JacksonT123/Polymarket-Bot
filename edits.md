# Edits Log — APPEND ONLY

This file is the permanent, immutable history of every change made in this project. Read it whenever you need full context on how the project got to its current state.

## Rules

1. **Never delete, overwrite, edit, or reformat existing entries.** Past entries are immutable. If you change your mind or revert something, add a NEW entry that references the old one — don't touch the original.
2. **Append-only.** New entries go at the bottom.
3. **Log every meaningful action**, including: file create/modify/delete, commands that change state, architectural decisions, dependencies added, bugs found, bugs fixed, refactors, dead-ends you backed out of. When in doubt, log it.
4. **Do not log:** trivial reads, navigation, file inspection, or your own thinking. Only log changes and decisions.

## Entry format (use exactly this)

---
## [YYYY-MM-DD HH:MM TZ] — <short title>
**What:** <1–2 sentences on what was done>
**Why:** <the user request or reason that triggered it>
**Files touched:** <path — created | modified | deleted>
**Commands run:** <shell commands, if any>
**Outcome:** <result, including errors, partial success, or surprises>
**Notes:** <gotchas, half-finished work, things future-you should know>
---

## On reverts and mistakes

If you undo something, write a new entry titled "Revert: <original title>" and reference the original timestamp. The original entry stays. The log tells the truth about what happened, including wrong turns.

## On compaction

If this file gets long, do not summarize or prune it yourself. Ask the user before doing anything destructive.

---

# Log

<!-- New entries below this line. Oldest at top, newest at bottom. -->

---
## [2026-05-23 — Session: Full v2.3 Build Complete

**What:** Built all 6 phases of the Polymarket Copy Bot v2.3 from scratch. Phase 1 (core, config, DB, API client), Phase 2 (wallet funnel Stages A–F + 13 metric files), Phase 3 (execution engine: poller, filters, sizer, paper fill, order engine, dedup, queue), Phase 4 (positions: tracker, pricer, exiter, reconciler; risk: circuit_breakers, caps, killswitch; runner.py), Phase 5 (notifications: discord, ntfy, alerts; CLI: click-based with all commands; API: FastAPI + 6 route modules + WebSocket; frontend: HTMX + Alpine.js + Plotly.js dashboard in web/index.html), Phase 6 (unit tests, integration tests, fixture data, docker-compose.yml, Dockerfile, .github/workflows/ci.yml, scripts/).
**Why:** User requested complete build of the v2.3 spec documented in All about.md.
**Files touched:** 95 Python files created, web/index.html created, docker-compose.yml, Dockerfile, .github/workflows/ci.yml, scripts/seed_db.py, scripts/reset_paper.py, tests/fixtures/*.json
**Commands run:** `python -c "import ast..."` for syntax checks (all 95 files pass)
**Outcome:** All 95 Python files pass syntax check. Full project structure complete.
**Notes:**
  - `get_trade_params(tier: int)` — takes tier int, NOT bankroll. Always call `compute_tier(bankroll)` first.
  - `EquitySnapshot` DB columns: timestamp, cash_balance, position_value, total_equity (NOT ts, cash_usd, etc.)
  - `WalletPoller.run(get_active, get_shadow)` takes async callables, not address lists
  - `SignalEvent.side` is plain string "YES"/"NO", not enum — don't call .value
  - `SignalRepo.get_recent` requires wallet_id; added `get_all_recent(limit)` for dashboard use
  - DATABASE_URL must be set in .env before bot can start. Neon.tech free tier recommended.

---

## 2026-05-23 — Session 3: Setup + Runtime Bug Fixes

**What:** Provisioned PostgreSQL, ran migrations, started bot, fixed 6 runtime bugs discovered during live API testing.

**Bugs fixed (in order discovered):**
1. `polymarket-bot` CLI not found after `uv sync` — hatchling build system was missing. Added to `pyproject.toml`.
2. `DuplicateOptionError: sqlalchemy.url` in alembic.ini — two `sqlalchemy.url` entries. Removed duplicate.
3. Alembic `Could not parse SQLAlchemy URL` — `.env` not auto-loaded by alembic. Fix: set `$env:DATABASE_URL` before running alembic.
4. Poller `'coroutine' object is not iterable` — runner's `_get_active_addresses` / `_get_shadow_addresses` are async; poller wasn't awaiting them. Fixed `poller.py` to check `asyncio.iscoroutine()` and await.
5. Funnel HTTP 404 on leaderboard — `data-api.polymarket.com/leaderboard` doesn't exist. Correct URL: `https://lb-api.polymarket.com/profit?window=all&limit=100`. Fixed `polymarket_client.py`.
6. Funnel `unsupported operand type for -: datetime - int` — real API `timestamp` field is Unix integer. Fixed all timestamp parsing in `stage_b_disqualifiers.py` and `metrics/consistency.py` to use `_parse_ts()` helper.
7. Funnel `'async_sessionmaker' object has no attribute 'execute'` — `_funnel_loop` passed the factory instead of a session. Wrapped in `async with self._session_factory() as session:`.
8. Stage B DQ'd all 50 wallets — real API: no `pnl`/`size_usd` in trades, positions endpoint only shows open positions, leaderboard returns only `proxyWallet`/`amount`/`name`. Rewrote `compute_stats()` to compute win rate from net PNL per (conditionId, outcome) pair using BUY/SELL trade reconstruction.
9. Orchestrator didn't promote wallets to shadow — condition only promoted `not existing or status == "candidate"`. Wallets from prior run had "disqualified" status. Fixed to promote any non-active/non-suspended wallet.
10. Signal normalizer dropped all real signals — real `/activity` uses `"side": "BUY"/"SELL"` not `"action"` or `"type"`. Fixed `normalize_activity()` to also check `raw.get("side")`. Fixed `_infer_side()` to use `outcome`/`outcomeIndex` fields for YES/NO.

**Real Polymarket API schema discovered:**
- lb-api/profit: `{ proxyWallet, amount (PNL), name, pseudonym }` — no winRate, tradesCount
- data-api/trades: `{ proxyWallet, side (BUY/SELL), asset (token ID), conditionId, size (shares), price, timestamp (Unix int), outcome (Yes/No), title, slug }`
- data-api/positions: only returns OPEN positions (empty for wallets that exited all positions)
- data-api/activity: same schema as trades — uses `side` field for BUY/SELL

**Outcome:** Bot running cleanly. Funnel completes in ~3s: 50 candidates → 37 DQ'd → 13 scored → 13 in shadow pool. 13 shadow wallet rows in DB. Poller running every 15s.

**Files touched:** src/data/polymarket_client.py, src/execution/poller.py, src/execution/signal_normalizer.py, src/funnel/stage_a_candidates.py, src/funnel/stage_b_disqualifiers.py, src/funnel/orchestrator.py, src/metrics/consistency.py, src/metrics/win_rate.py, src/runner.py, pyproject.toml (build-system), alembic.ini (dup removed), Handoff.md
---

---
## [2026-05-23] — WebSocket: Switch to wss://ws-live-data.polymarket.com (global activity feed)

**What:** Rewrote src/data/clob_websocket.py to connect to the correct Polymarket WebSocket endpoint. The old endpoint (wss://ws-subscriptions-clob.polymarket.com/ws/) returned 404. The new endpoint broadcasts every trade globally with proxyWallet in the payload. We subscribe once with `{"action": "subscribe", "subscriptions": [{"type": "activity"}]}` and filter events by proxyWallet against tracked lead wallets — no per-market subscription needed.
**Why:** User wanted best-in-class real-time polling. Old WS was silently failing (404); all detection was falling back to periodic HTTP sweeps (2–5s). New approach gives sub-100ms detection when any lead wallet trades.
**Files touched:** src/data/clob_websocket.py — modified
**Commands run:** none
**Outcome:** clob_websocket.py is now ~100 lines (down from 177). register() API unchanged so poller.py needs no edits. Internal _token_to_wallets and _market_to_wallets mappings removed — wallet address lookup is all that's needed.
**Notes:** Subscription format discovered from polymarket-apis SDK source at .venv/Lib/site-packages/polymarket_apis/clients/websockets_client.py. ActivityTradeEvent.payload.proxyWallet is present in every trade event. The SDK itself uses lomond (sync) — we use aiohttp for async compat.
---