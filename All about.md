# Polymarket Copy Bot v2.3 — Complete Build Specification

This is the exhaustive spec for the bot. Every behavior, every number, every rule, every formula. Built from primary research across working copy operators (Polycopy, Polycopybot, Polycule, Polycop, Stand.trade, PolyTrack), academic studies (Shen et al. on follower-count alpha decay; Akey/Grégoire/Harvie/Martineau SSRN 6443103 on profit concentration; Gómez-Cram et al. April 2026 on skilled trader minority; LBS Alpha Decay paper; McLean & Pontiff on post-publication decay), and Polymarket's own newsletter "The Oracle" (Stand.trade Ridgely interview, Primo interview on category leaderboards).

**This version is build-ready.** Project structure, tech stack, state machines, exact metric formulas, error handling, deployment, web dashboard, CLI, testing — all included. Hand to Claude Code with confidence.

---

## What This Bot Is

A faithful copy-trading bot for Polymarket. It auto-discovers and ranks specialist wallets through a two-stage funnel, then mirrors their buys with fixed-size positions. It exits when the lead trader exits. It does not invent its own strategy. It does not use percentage stop-losses. It does not try to predict outcomes.

The bot has one job: **see what a qualified lead trader does, do the same thing scaled down, exit when they exit.**

---

## Core Philosophy (Read This First)

Three rules that override everything else:

**Rule 1: Mirror exits, never percentage stops.** A position bought at $0.60 that drifts to $0.48 looks like a 20% loss but might resolve at $1.00. Binary markets oscillate. The lead trader decides when the thesis is dead — not a fixed percentage.

**Rule 2: Pick humans, not bots.** HFT crypto bots dominate Polymarket's 5-minute and 15-minute markets (55–62% of volume). You cannot copy them — by the time you fill, the edge is gone. The auto-rank funnel has to disqualify them at the gate, not score them.

**Rule 3: Minimal filtering at execution.** Working copy bots execute 10–25% of detected signals. The previous version executed 0.5%. The filters were fighting each other because the watchlist was full of uncopyable wallets generating uncopyable signals. v2.2 fixes this upstream — by the time a signal reaches the filter chain, it's already from a wallet worth copying. Execution filters drop to 5.

---

## Wallet Selection — The Auto-Rank Funnel

### The problem the funnel solves

A naive top-20-by-composite-score ranking on Polymarket pulls roughly: 8–12 HFT crypto bots, 2–3 one-shot election whales (Théo cluster), 2–4 reward farmers / market makers, and 1–3 actual copyable specialists. The score formula can't tell "edge I can copy" from "edge I cannot copy" — it sees PnL and volume, both of which favor wallets you can't follow.

The two-stage funnel solves this: **hard disqualifiers at the gate, composite scoring on the survivors, then a shadow-mode validation period before any real signal flows.**

### Stage A — Candidate Pool (runs daily)

Pull the top 200 wallets from Polymarket's leaderboard via Data API (`/leaderboard?window=all&limit=200`). For each wallet, fetch lifetime activity stats from `/positions` and `/trades`.

### Stage B — Hard Disqualifiers (applied to all 200)

Any wallet hitting ANY of these is permanently flagged as INELIGIBLE:

| Disqualifier | Threshold | Why |
|---|---|---|
| Volume in 5-min crypto markets | > 30% of total volume | HFT bot — Stand.trade confirmed most-copied bots went silent after March 2026 fee changes |
| Volume in 15-min crypto markets | > 30% of total volume | HFT bot — same as above |
| Total closed trades | < 100 | Sample size: per academic research, n<100 trades is statistically indistinguishable from luck |
| Months active | < 4 | Insufficient track record (vs. v2.1's 4-month minimum — kept) |
| Trades per day (mean) | > 30 | Reduced from 50 — research shows manual traders rarely exceed 100 trades/month |
| Trades per day (mean) | < 0.3 | Inactive / one-shot wallet |
| Single-market PnL concentration | > 50% of lifetime PnL from one market | Tightened from 60% — Théo cluster level of concentration is uncopyable |
| Category diversity | Trades in > 5 distinct categories | Tightened from 8 — per 0xmega: "wallets profitable across politics, crypto, and sports simultaneously are bots or statistical anomalies" |
| Average holding time | < 30 minutes | HFT or scalper, uncopyable |
| Win rate | < 55% overall (or category-specific floor below) | Skill floor |
| Cluster size (PolyTrack data) | > 2 linked wallets | Multi-wallet operator — you're seeing fragmentary picture |
| ROI on positive resolved trades | < 8% | Per LaikaLabs research: <8% margin is below transaction cost drag |
| Max drawdown | > 35% | Even profitable wallets aren't copyable if they swing this hard |

**Category-specific win rate floors** (researched from per-category profitability studies):

| Category | Win rate floor | Notes |
|---|---|---|
| Soccer specialists | 58% | RN1 archetype: high-volume soccer with consistent edge |
| Politics/Geopolitics | 60% | Higher noise, need higher floor |
| Sports markets (NFL, NBA, MLB) | 56% | Market-makers run here; harder to outperform |
| Weather | 65% | Niche; profitable wallets here have real expertise |
| Mention markets | 60% | Specialized vocabulary edge |
| Macro/Finance | 60% | Per atomicwallet research: slower-moving, more disciplined |
| Crypto (non-HFT only) | 60% | Bonding strategies acceptable; HFT excluded above |

After Stage B, typically 10–25 wallets remain from the original 200. These are the SCORING POOL.

### Stage C — ZuluRank-Style Composite Scoring (applied to survivors)

The scoring formula is rebuilt around **risk-adjusted returns** rather than raw P&L. This is modeled on ZuluTrade's ZuluRank Algorithm, which uses 15 factors weighting risk-adjusted returns above absolute performance. Adapted to Polymarket binary structure:

```
S = w1·log(closed_trades)         [sample size]
  + w2·win_rate_vs_category_floor [skill margin]
  + w3·log(profit_factor)         [win/loss skew]
  + w4·months_active              [track record depth]
  + w5·domain_score               [specialization depth]
  + w6·hold_to_resolution_pct     [exits IRL match exits in copy]
  + w7·consistency_score          [equity curve smoothness]
  + w8·conviction_signal          [position size variance — Stand.trade insight]
  + w9·counter_trade_signal       [if known-loser wallet, NEGATIVE entry]
  - w10·entropy                   [category spread penalty]
  - w11·insider_proximity         [traded close to news anomalies]
  - w12·max_drawdown_pct          [worst peak-to-trough]
  - w13·crowding_penalty          [popularity hurts edge — academic-confirmed]
```

| Factor | Weight | What it measures |
|---|---|---|
| `log(closed_trades)` | +0.10 | Sample size (log-scaled) |
| `win_rate_vs_category_floor` | +0.18 | Excess win rate above category-specific minimum |
| `log(profit_factor)` | +0.15 | Gross wins ÷ gross losses |
| `months_active` | +0.08 | Track record duration (capped at 24) |
| `domain_score` | +0.20 | % of volume in single category (rewards 60%+ concentration) |
| `hold_to_resolution_pct` | +0.12 | % of positions held to resolution (key signal — copies will faithfully exit) |
| `consistency_score` | +0.10 | Std-dev of monthly returns; LOW std-dev = consistent edge |
| `conviction_signal` | +0.08 | Avg position size on winners vs losers (winners larger = real conviction) |
| `counter_trade_signal` | ±0.05 | Add inverted score for high-volume losers (Stand.trade feature) |
| `entropy` | −0.05 | Penalty for spreading across unrelated markets |
| `insider_proximity` | −0.05 | Penalty if traded suspiciously close to news/results |
| `max_drawdown_pct` | −0.08 | Penalty for high peak-to-trough drawdown |
| `crowding_penalty` | −0.10 | NEW: penalty for high follower count / public attention |

**Why these specific changes from v2.1:**

- **Consistency score**: ZuluTrade-style; rewards stable monthly returns over big-spike-then-flat curves. Stand.trade's "The Oracle" specifically called out the equity curve being "monotonic-ish" as the key signal for RN1.
- **Conviction signal**: Per LaikaLabs research, position-size variance is the most underused metric. Beachboy4 deploys $2M on high-conviction trades vs $200K normally — that 10x signals genuine conviction differential.
- **Hold-to-resolution %**: Critical for copy mirroring. If lead holds to resolution, your copy follows the same path. If lead exits early, your mirror-exit logic needs that signal.
- **Counter-trade signal**: Stand.trade discovered users counter-trading high-volume losers as a strategy. Inverting a known-loser's signal becomes a positive edge.
- **Crowding penalty**: ACADEMIC-BACKED. The Shen et al. study (using randomized field experiment data from a crypto social trading platform) found that *"traders garnering increased social audience size exhibit tendencies to trade more frequently, utilize higher leverage, and, surprisingly, attain poorer performance."* This is empirically validated — popularity causes worse performance.
- **Insider proximity**: Polysights has a "Beta Insider Finder" — wallets trading just before news breaks. These are uncopyable (you'll always be late).

### Stage D — Top 25 Ranking

The bot ranks Stage C survivors by composite score. **Top 25 enter the SHADOW POOL.** (Expanded from 20 — more candidates to shadow-test.)

### Stage E — Shadow Mode (mandatory, 21 days minimum)

**No real signals copy from a wallet until it survives shadow mode.**

For 21 days (extended from 14), the bot tracks each shadow-pool wallet's trades and simulates a copy with FULL fidelity:

- Real slippage modeling per market liquidity tier
- Real fee deduction (1.0% politics, up to 1.8% crypto)
- Real 5-filter execution chain
- Real latency simulation (1–18 second delay from lead trade detection)

At the end of 21 days, each wallet has TWO metrics:

1. **Copy P&L** — what the bot WOULD have made copying it
2. **Capture Ratio** — copy P&L ÷ lead's P&L over the same period

Promotion from shadow to ACTIVE requires ALL of:
- ≥ 25 simulated copies executed (signal-to-exec ratio between 10–25%)
- Simulated copy P&L net positive
- **Capture ratio ≥ 60%** (NEW — borrowed from real industry benchmarks)
- No catastrophic single-trade loss > 15% of simulated bankroll
- Lead's win rate during shadow period within ±5% of historical baseline (i.e., they didn't go cold during test)

Wallets failing shadow validation stay in shadow another 21 days or get dropped from the pool after 2 failed cycles.

### Stage F — Active Pool (the real watchlist)

**Maximum 5 wallets active at any time.** Selection from shadow-passers ranks by:

```
Promotion Score = composite_score × capture_ratio × signal_count_factor
```

Where `signal_count_factor` rewards wallets producing more trades (more data per unit time). The top 5 become active. Shadow-passers ranked 6+ become BENCH alternates (auto-promote when an active wallet is suspended).

### Re-evaluation cadence

| Action | Cadence |
|---|---|
| Stage A: refresh candidate pool from leaderboard | Daily (12:00 UTC) |
| Stage B: apply hard disqualifiers | Daily |
| Stage C: rescore all candidates | Daily |
| Stage D: refresh shadow pool top 25 | Daily |
| Stage E: shadow-mode validation | Continuous, minimum 21 days per wallet |
| Stage F: rotate active pool | Weekly review |
| Cluster detection rerun | Weekly (manual check vs PolyTrack data if subscribed) |

### Active wallet suspension triggers (any one fires → suspend back to shadow)

- Wallet generates 3 consecutive losing closed trades for the bot
- Bot's capture ratio drops below 40% over last 20 copies (edge is dying or wallet became uncopyable)
- Wallet silent ≥ 14 days
- Wallet's personal 20-trade rolling win rate drops below its category floor
- Wallet starts trading > 30% volume in 5-min or 15-min markets (turned bot-mode)
- Wallet's category diversity exceeds 5 (lost specialization)
- Crowding penalty score increases > 50% (sudden popularity spike — Stand.trade interview noted this happens fast)
- Cluster detection flags wallet as linked to a previously-disqualified wallet

Suspended wallets go back to shadow pool for re-validation; they don't get auto-dropped after first suspension. Second suspension within 60 days = permanent drop.

### Data sources for the funnel

| Source | What it provides | Cost |
|---|---|---|
| Polymarket Data API `/leaderboard` | Top wallets by P&L or volume, filterable by time window | Free |
| Polymarket Data API `/positions`, `/trades`, `/activity` | Per-wallet lifetime stats, category breakdown | Free |
| **PolyTrack ($9.99/week)** | **Cluster detection — identifies multi-wallet operators (Théo had 11)** | $9.99/wk |
| Polysights | 30+ custom metrics including Insider Finder beta | Free tier + paid |
| Polymarket Analytics | Multi-platform aggregation (Polymarket + Kalshi) | Free + paid |
| Wallet Master (walletmaster.tools) | 80+ metrics across 7M+ wallets | Subscription |
| PolyTrends | Wallet archetype classification (Mega Capital, Precision, Specialist) | Free + paid |
| Apify Polymarket Whale Tracker | ML clustering and anomaly detection | $0.50/1000 results |
| Goldsky / The Graph | Historical aggregate data for cross-market analysis | Free tier available |
| **Stand.trade newsletter "The Oracle"** | **Qualitative insights on which wallets are surviving copy pressure** | Free (substack) |

**PolyTrack's $9.99/week is the single highest-ROI subscription** for serious wallet selection — cluster detection alone is worth it. Without it, you'll repeatedly select wallets that are actually two halves of the same operator.

### What the funnel will NOT find (honest limits)

- **Secondary/tertiary wallets of public whales.** Per Stand.trade's Ridgely: "Top traders now have secondary and tertiary accounts because they know their main accounts are being copy traded immediately." You'll find the public face, not the full book.
- **Insider wallets that haven't been caught yet.** New anonymous wallets making suspiciously profitable trades — these get filtered out by the <100 closed trades threshold, which is correct because by the time they have enough sample, the regulator may have caught them.
- **Pre-fame wallets.** A wallet that's about to become elite but currently has 60 trades will get filtered. Acceptable tradeoff — better to miss the early career of the next Domer than to catch 50 false positives.

---

## The 5 Execution Filters (And Only 5)

When a watched wallet places a buy, the bot evaluates the trade against exactly five checks. Pass all five → execute. Fail any → log and skip with the specific reason.

### Filter 1: Capital available
- Bot has enough USDC for the fixed trade size + fees
- At least 1 open-position slot available (max 10 simultaneous positions)

### Filter 2: Minimum lead trade size
- Lead's trade ≥ **$5**
- This is the floor only to skip dust and meet Polymarket's 5-share / ~$4.75 minimum
- **NOT $100.** The previous $100 floor killed every iceberged signal from Domer and the small-trade entries from soccer specialists.

### Filter 3: Market liquidity
- 24-hour volume on the market ≥ **$5,000**
- Below this, slippage destroys the copy

### Filter 4: Price range
- Lead's fill price between **$0.05 and $0.95**
- Wide band intentional. Compresses only to skip resolved-already markets.
- Underdog plays (RN1, Swiss Tony) live at $0.10–$0.40. Bond strategies (Sharky6999) live at $0.80–$0.95. Don't kill either.

### Filter 5: Resolution window
- Market resolves within **next 60 days**
- AND not within next **2 hours** (avoid resolution-arbitrage chaos)

### Duplicate prevention (not a filter, a hard gate)
- If bot already holds a position on this `(market_id, side)` combo → skip
- Dedup key locks only AFTER successful execution (so a $5 skip doesn't block a later $1,000 entry by the same whale in the same market)

### Filters explicitly REMOVED from v1

| v1 filter | Why removed |
|---|---|
| 20% stop-loss | Converts winning theses into realized losses; no major operator uses fixed % stops |
| Daily exposure cap | Position cap (10) already controls this at $100 |
| Trade size bounds at execution layer | Sizing is now fixed-formula upstream |
| Slippage estimate filter | Replaced by hard slippage cap at order placement |
| Time-to-resolution > 1 hour | Replaced by 2-hour minimum (more restrictive, but for a different reason) |
| Wallet score threshold at execution | Watchlist is auto-curated upstream; if a wallet is active, trust it |

**Target signal-to-execution ratio: 10–25%.** If you're seeing <10%, filters are still too tight OR the active pool needs review. If >40%, the active pool is too noisy.

---

## Position Sizing — The Math

### Why fixed-dollar per tier (not pure proportional)
Lead traders bet $100–$50,000. Pure proportional sizing (e.g., "always bet 1% of bankroll") produces wildly inconsistent dollar amounts and either over-concentrates as you scale up or stays uselessly small. Pure fixed sizing (always $5) never scales. The correct answer is **tiered scaling**: trade size is fixed *within a bankroll band* and bumps up when you cross thresholds.

### The tier ladder

The bot automatically adjusts trade size, position count, and deployment caps based on current bankroll. Tier transitions happen on a 7-day rolling average bankroll (so a single bad day doesn't demote you and a single lucky win doesn't promote you).

| Tier | Bankroll | Trade size | Max positions | Max deployed | % per trade |
|---|---|---|---|---|---|
| 0 | $100–$249 | $5 | 10 | 50% | 5.0% |
| 1 | $250–$499 | $10 | 12 | 55% | 4.0% |
| 2 | $500–$999 | $20 | 14 | 60% | 4.0% |
| 3 | $1,000–$2,499 | $40 | 16 | 65% | 4.0% |
| 4 | $2,500–$4,999 | $75 | 18 | 65% | 3.0% |
| 5 | $5,000–$9,999 | $150 | 20 | 70% | 3.0% |
| 6 | $10,000–$24,999 | $300 | 22 | 70% | 3.0% |
| 7 | $25,000–$49,999 | $600 | 24 | 70% | 2.4% |
| 8 | $50,000–$99,999 | $1,200 | 25 | 70% | 2.4% |
| 9 | $100,000+ | $2,000 | 25 | 70% | 2.0% |

### How the ladder works

**Trade size doubles roughly every tier through tier 6, then growth slows.** This reflects two realities: (a) small-account fee drag dominates so you need to size up aggressively early, and (b) at larger sizes you start moving markets and need to slow down to avoid slippage penalties.

**Position count grows slowly** from 10 → 25. More positions = more diversification, but also more management overhead. Above 25 you're not adding meaningful diversification; you're just adding noise.

**Capital deployment % grows from 50% to 70%.** Smaller accounts hold more reserve because a single bad fill matters more in dollar terms. Larger accounts can afford to keep less idle cash.

**% per trade DROPS as bankroll grows.** This is the Kelly-style insight: at $100 you need 5% bets to overcome fixed costs; at $100k you'd be insane to bet 5% per position because variance compounds.

### Tier transition logic

```python
def compute_tier(rolling_7d_avg_bankroll):
    if bankroll < 250:     return 0
    if bankroll < 500:     return 1
    if bankroll < 1_000:   return 2
    if bankroll < 2_500:   return 3
    if bankroll < 5_000:   return 4
    if bankroll < 10_000:  return 5
    if bankroll < 25_000:  return 6
    if bankroll < 50_000:  return 7
    if bankroll < 100_000: return 8
    return 9

def get_trade_params(current_tier):
    return TIER_TABLE[current_tier]
```

**Promotion guardrail**: bot needs 7 consecutive days with rolling-avg bankroll above the next tier's threshold before promoting. Prevents promote-then-demote-then-promote thrashing.

**Demotion guardrail**: bot demotes immediately if rolling-avg drops below current tier's floor. No grace period on the way down — drawdowns are real, scale down fast.

**Hard guardrail on tier jumps**: bot can only promote ONE tier at a time per week, even if bankroll growth would suggest skipping levels (e.g., $100 → $5,000 in a week from a massive win must still walk through tiers 1, 2, 3 over several weeks). This is a sanity check against single-event windfalls.

### Manual override (optional, but recommended)

The bot supports a `TIER_OVERRIDE` env var that lets you cap the tier manually:

```
TIER_OVERRIDE=3   # don't auto-promote above tier 3 regardless of bankroll
```

Use this when you're not yet psychologically or operationally ready to trade at the next tier's size. The bot will still demote automatically if needed, but won't promote past the cap.

### Worked examples

**Example 1: $100 → $250 over 6 weeks**
- Week 1–4: Tier 0, $5/trade, ~30 trades, ending bankroll $145
- Week 5: rolling avg $180 — still Tier 0
- Week 6: rolling avg $260 (above $250 for 7+ days) — promotes to Tier 1
- Week 7+: $10/trade, 12 position slots

**Example 2: $5,000 account hits a -25% week**
- Pre-drawdown: Tier 5, $150/trade
- After drawdown: bankroll $3,750
- Tier 5 floor is $5,000 — immediate demotion to Tier 4
- New params: $75/trade, 18 positions
- Existing positions stay open at original size; only NEW positions use new params

**Example 3: $100 → $50k windfall (impossible, but illustrative)**
- Bot does NOT jump to Tier 8 immediately
- Each week, bot can promote at most one tier
- Takes 8 weeks minimum to climb the full ladder
- This is intentional — sudden large bankrolls usually come from single trades that won't repeat

### Tier-specific behavioral adjustments

Beyond just trade size, some tiers unlock additional behaviors:

| Tier | Unlocks |
|---|---|
| 2 ($500+) | Bot can hold positions in markets with < $5k 24h volume IF lead's trade ≥ $100 (loosen Filter 3) |
| 3 ($1k+) | Bot can copy lead trades < $5 if they're from a wallet on a 5+ trade winning streak |
| 4 ($2.5k+) | Bot starts using WebSocket via Goldsky instead of 15s polling (latency upgrade pays off here) |
| 5 ($5k+) | Bot considers running 6 active wallets instead of 5 (one slot reserved for highest-conviction shadow promotee) |
| 6 ($10k+) | Bot starts copying SELL orders for partial exits at proportional ratio (e.g., lead sells 30%, bot sells 30%) |
| 8 ($50k+) | Bot adds book-depth check before market orders to avoid being its own market mover |

These are unlocks, not requirements — they activate automatically at the tier threshold.

### Why this beats fixed sizing

At $100 with $5 trades, a winning month of 10 closed copies at +20% average = $10 gain (10%). Reasonable.

At $10,000 with $5 trades, that same 10-copy month = $10 gain (0.1%). Useless. You need to scale up or quit.

The tier ladder ensures the bot's earning power scales with your bankroll instead of asymptoting at $10/trade forever.

---

## Exit Logic — The Three Ways A Position Closes

### Exit 1: Mirror the lead's exit (PRIMARY)
**The lead trader sells their position → bot sells immediately.**

- Bot polls each active wallet's activity every 15 seconds
- When a SELL is detected on a market where bot holds the same side → place a market order to close
- Sell as much of the bot's position as the lead sold proportionally:
  - Lead sold 100% of their position → bot sells 100%
  - Lead sold 50% → bot sells 50%
- Slippage cap on the sell: 15%

### Exit 2: Market resolves (AUTOMATIC)
- Market resolves → outcome tokens redeem at $1.00 (winning side) or $0.00 (losing side)
- Position auto-closes at settlement
- Bot detects via CLOB `/markets/{condition_id}` showing `closed: true`

### Exit 3: Hard time stop (SAFETY NET ONLY)
- Position open ≥ **90 days** → force close at market price
- Almost never triggers; exists only to prevent forgotten positions
- Logged distinctly so you can identify when this fires (it shouldn't)

### Exits explicitly NOT used

- **No percentage stop-loss.** The lead's exit IS the stop. Trust the active pool or don't include them in it.
- **No take-profit.** If the lead holds to $0.99, bot holds to $0.99.
- **No time-based "rotate stale positions."** Holding to resolution is the point.

### Sanity-check exit: thesis-broken override
**One discretionary override.** If a market's price moves > 40% against entry AND the followed wallet has NOT bought more in the last 24 hours AND has not sold → close. This catches the rare case where the lead silently abandoned a position without explicitly selling (e.g., wallet inactive).

---

## Detection & Execution Flow

### The polling loop

```
Every 15 seconds:
  For each wallet in ACTIVE pool:
    Fetch Data API /activity?user={wallet}&limit=20
    Compare against last-seen trade timestamps
    For each NEW trade:
      Normalize to internal event format
      Push to event queue (mark as live)
  
  For each wallet in SHADOW pool:
    Same fetch logic
    Push events to shadow queue (paper-only)
```

### The queue consumer

```
For each event in queue:
  If event.type == BUY:
    Run 5 filters
    If all pass → place mirror order (live or paper depending on source pool)
    Log result (executed | skipped:reason)
  
  If event.type == SELL:
    Check open positions for same (market_id, side)
    If found → place close order proportional to lead's sell
    Log result
```

### Order placement

```
Market order via CLOB API
Slippage cap: 10% on buys, 15% on sells
Three-phase retry:
  Phase 1: FOK (fill-or-kill) at lead's fill price
  Phase 2: FOK at ±2% of lead's fill price
  Phase 3: Market order with max-slippage cap
If all three phases fail → log "unfillable" and abandon signal
```

### Latency budget

- Polymarket Data API poll: ~200–500ms
- New trade detection: 0–15s (polling interval)
- Filter evaluation: <100ms
- Order signing (EIP-712): 100–500ms
- CLOB acknowledgment: 100–500ms
- First match: 500–1500ms

**Total: 1–18 seconds from lead's fill to your fill.** Fine for humans. Useless for HFT bots — which is why HFT bots are disqualified at Stage B.

### Why 15-second polling and not WebSocket

WebSocket is faster (~340ms achievable) but more complex and more failure-prone. For copying HUMAN traders on multi-hour to multi-week positions, 15-second polling is sufficient. Per Polycopytrade.space's published numbers: "Your copy arrives 6–14 seconds later. For liquid markets, this slippage is typically 0.1–0.5 cents per share."

**Upgrade trigger:** if you ever expand to copy faster-moving wallets (sub-day holding), upgrade to Goldsky Turbo Pipeline WebSocket on the V2 CTF Exchange contract. Until then, 15s polling is correct.

---

## Data Sources

### Primary: Polymarket Data API
- **Endpoint**: `data-api.polymarket.com`
- **Rate limit**: 1,000 req / 10s general; 200 req / 10s on `/trades`; 150 req / 10s on `/positions`
- **Used for**: leaderboard, wallet activity polling, position lookups, lifetime stats for ranking

### Secondary: Gamma API
- **Endpoint**: `gamma-api.polymarket.com`
- **Rate limit**: 4,000 req / 10s general; 500 req / 10s on `/events`; 300 req / 10s on `/markets`
- **Used for**: market metadata, 24h volume (CLOB doesn't return volume), resolution status, end-date, category

### Tertiary: CLOB API
- **Endpoint**: `clob.polymarket.com`
- **Rate limit**: 1,500 req / 10s public reads; 3,500 burst on POST /order
- **Used for**: order placement, midpoint prices, market token IDs, active/closed status

### Cache strategy
- Market metadata: 5-minute cache per `condition_id`
- Wallet activity: never cached (always fresh)
- Token IDs: cached indefinitely (don't change)
- Lifetime wallet stats: 24-hour cache (refreshed in daily Stage A run)

### Backup data feeds (optional, for future)
- **Goldsky Turbo Pipeline**: real-time `OrderFilled` events on V2 CTF Exchange (`0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`). Sub-second latency.
- **Polygon RPC** (Alchemy free tier): direct log scanning as fallback

---

## Risk Management

### Position-level
*(Values shown for Tier 0 / $100 bankroll. Trade size and max positions scale with tier ladder — see Position Sizing section.)*

| Parameter | Tier 0 value | Scales with tier? |
|---|---|---|
| Fixed trade size | $5 | Yes ($5 → $2,000) |
| Max open positions | 10 | Yes (10 → 25) |
| Max slippage on buy | 10% | No |
| Max slippage on sell | 15% | No |
| Thesis-broken override | Close if -40% AND lead inactive 24h+ | No |
| Hard time stop | 90 days | No |

### Portfolio-level
*(Deployment % scales with tier; suspension/correlation rules are constant.)*

| Parameter | Tier 0 value | Scales? |
|---|---|---|
| Max capital deployed | 50% of bankroll ($50 at $100) | Yes (50% → 70%) |
| Reserve | 50% of bankroll | Yes (50% → 30%) |
| Max same-day NEW positions | 5 | No (prevents cascade on one wallet's bad day) |
| Max correlation to single market | 1 position per (market_id, side) — enforced by dedup | No |

### Circuit breakers
| Trigger | Action | Duration |
|---|---|---|
| Day P&L ≤ -15% of bankroll (-$15 at $100) | Halt new entries; existing positions stay open | 24 hours |
| Week P&L ≤ -25% of bankroll | Halt all activity | 7 days |
| Drawdown from peak ≥ 40% | Permanent halt; manual restart required | Indefinite |
| Same active wallet generates 3 consecutive losing closed trades | Suspend that wallet → back to shadow | Until weekly review |

Circuit breakers in paper mode match live thresholds so the equity curve you see represents real risk.

---

## Modes: Paper vs Live

### Paper mode (DEFAULT)

```python
TRADING_MODE = TradingMode.PAPER
INITIAL_BALANCE = 100.0
```

**Fill model:**
```python
fill_price = entry_price * (1 + slippage_pct)
slippage_pct = tier_lookup(market_volume_24h)
fee_pct = 0.01  # 1% taker (politics); category-tiered up to 1.8% on crypto
total_cost = (trade_size_usd * (1 + slippage_pct)) + (trade_size_usd * fee_pct)
```

**Slippage tiers:**
| 24h Volume | Simulated Slippage |
|---|---|
| ≥ $500,000 | 0.3% |
| ≥ $100,000 | 0.5% |
| ≥ $50,000 | 1.0% |
| ≥ $10,000 | 2.0% |
| ≥ $5,000 | 2.5% |
| < $5,000 | filtered out (Filter 3) |

**No simulated execution failures.** If the filters passed, paper fills.

### Live mode

Requirements:
1. Polymarket account funded with USDC on Polygon
2. L2 API credentials generated
3. Legal review of jurisdiction (Minnesota / US TOS issues remain unresolved)
4. `.env` populated:
   ```
   POLYMARKET_PRIVATE_KEY=0x...
   POLYMARKET_API_KEY=...
   POLYMARKET_API_SECRET=...
   POLYMARKET_API_PASSPHRASE=...
   POLYMARKET_PROXY_ADDRESS=0x...
   ```
5. Config flip:
   ```python
   TRADING_MODE = TradingMode.LIVE
   ```

**Live-mode additional safeties:**
- Pre-flight: check balance, allowances, key validity before first trade
- All orders signed EIP-712 via py-clob-client-v2
- Slippage cap enforced at order construction
- Hard kill switch: `KILLSWITCH=1` env var halts all new orders within 30s

---

## Configuration Reference

```python
# config.py

# ─── Capital & Tier Ladder ──────────────────────────
PAPER_INITIAL_BALANCE       = 100.0

# Tier table: (min_bankroll, trade_size, max_positions, max_deployed_pct)
TIER_TABLE = [
    # Tier 0
    {"min_bankroll": 100,     "trade_size": 5,    "max_positions": 10, "max_deployed_pct": 0.50},
    # Tier 1
    {"min_bankroll": 250,     "trade_size": 10,   "max_positions": 12, "max_deployed_pct": 0.55},
    # Tier 2
    {"min_bankroll": 500,     "trade_size": 20,   "max_positions": 14, "max_deployed_pct": 0.60},
    # Tier 3
    {"min_bankroll": 1_000,   "trade_size": 40,   "max_positions": 16, "max_deployed_pct": 0.65},
    # Tier 4
    {"min_bankroll": 2_500,   "trade_size": 75,   "max_positions": 18, "max_deployed_pct": 0.65},
    # Tier 5
    {"min_bankroll": 5_000,   "trade_size": 150,  "max_positions": 20, "max_deployed_pct": 0.70},
    # Tier 6
    {"min_bankroll": 10_000,  "trade_size": 300,  "max_positions": 22, "max_deployed_pct": 0.70},
    # Tier 7
    {"min_bankroll": 25_000,  "trade_size": 600,  "max_positions": 24, "max_deployed_pct": 0.70},
    # Tier 8
    {"min_bankroll": 50_000,  "trade_size": 1200, "max_positions": 25, "max_deployed_pct": 0.70},
    # Tier 9
    {"min_bankroll": 100_000, "trade_size": 2000, "max_positions": 25, "max_deployed_pct": 0.70},
]

ROLLING_BANKROLL_WINDOW_DAYS = 7        # rolling avg for tier compute
PROMOTION_GRACE_DAYS         = 7        # consecutive days above threshold required
DEMOTION_GRACE_DAYS          = 0        # immediate demotion on drawdown
MAX_TIERS_PROMOTED_PER_WEEK  = 1        # one tier max per week
TIER_OVERRIDE                = None     # set to int 0-9 to cap, None for auto

# ─── Wallet Funnel (v2.3) ───────────────────────────
CANDIDATE_POOL_SIZE             = 200    # Stage A: leaderboard pull
SHADOW_POOL_SIZE                = 25     # Stage D: top 25 after scoring (v2.2: was 20)
ACTIVE_POOL_SIZE                = 5      # Stage F: max active wallets
SHADOW_MODE_MIN_DAYS            = 21     # v2.2: was 14
SHADOW_MIN_SIMULATED_COPIES     = 25     # v2.2: was 20
SHADOW_MIN_CAPTURE_RATIO        = 0.60   # v2.2 NEW — required for promotion
SHADOW_MAX_SINGLE_LOSS_PCT      = 0.15
SHADOW_MAX_FAILED_CYCLES        = 2      # v2.2 NEW — drop after 2 failed cycles
SHADOW_LEAD_WR_DRIFT_TOLERANCE  = 0.05   # v2.2 NEW — lead's WR must stay within ±5% of baseline

# ─── Hard Disqualifiers (v2.2 tightened — 13 total) ─
DQ_MAX_5MIN_CRYPTO_PCT          = 0.30
DQ_MAX_15MIN_CRYPTO_PCT         = 0.30
DQ_MIN_CLOSED_TRADES            = 100    # v2.2: was 50
DQ_MIN_MONTHS_ACTIVE            = 4
DQ_MAX_TRADES_PER_DAY           = 30     # v2.2: was 50
DQ_MIN_TRADES_PER_DAY           = 0.3
DQ_MAX_SINGLE_MARKET_PNL        = 0.50   # v2.2: was 0.60
DQ_MAX_CATEGORY_DIVERSITY       = 5      # v2.2: was 8
DQ_MIN_AVG_HOLD_MINUTES         = 30
DQ_MIN_WIN_RATE                 = 0.55   # global floor; category floors below override upward
DQ_MAX_CLUSTER_SIZE             = 2      # v2.2 NEW — requires PolyTrack/clustering data
DQ_MIN_POSITIVE_ROI             = 0.08   # v2.2 NEW — per LaikaLabs
DQ_MAX_DRAWDOWN_PCT             = 0.35   # v2.2 NEW

# Category-specific win rate floors (v2.2 NEW)
# Applied AFTER global floor; whichever is HIGHER wins for that wallet
CATEGORY_WIN_RATE_FLOORS = {
    "soccer":      0.58,
    "politics":    0.60,
    "geopolitics": 0.60,
    "sports_us":   0.56,   # NFL, NBA, MLB — market-makers run here
    "weather":     0.65,
    "mention":     0.60,
    "macro":       0.60,
    "finance":     0.60,
    "crypto":      0.60,   # non-HFT only; HFT excluded above
    "culture":     0.58,
    "tech":        0.58,
    "_default":    0.55,
}

# ─── Scoring Weights (v2.2 — 13 factors) ────────────
W_LOG_TRADES                    = 0.10   # v2.2: was 0.15
W_WIN_RATE_VS_CATEGORY_FLOOR    = 0.18   # v2.2 NEW (replaces W_WIN_RATE)
W_LOG_PROFIT_FACTOR             = 0.15
W_MONTHS_ACTIVE                 = 0.08   # v2.2: was 0.10
W_DOMAIN_SCORE                  = 0.20
W_HOLD_TO_RESOLUTION_PCT        = 0.12   # v2.2 NEW (replaces W_HOLDING_TIME)
W_CONSISTENCY_SCORE             = 0.10   # v2.2 NEW — std-dev of monthly returns
W_CONVICTION_SIGNAL             = 0.08   # v2.2 NEW — winner-size vs loser-size
W_COUNTER_TRADE_SIGNAL          = 0.05   # v2.2 NEW — bidirectional (±)
W_ENTROPY                       = -0.05
W_INSIDER_PROXIMITY             = -0.05  # v2.2 renamed from W_INSIDER_FLAG
W_MAX_DRAWDOWN                  = -0.08  # v2.2: was -0.10
W_CROWDING_PENALTY              = -0.10  # v2.2 NEW — academic-backed (Shen et al.)

# ─── Active Wallet Suspension (v2.2) ────────────────
SUSPEND_CONSECUTIVE_LOSSES      = 3
SUSPEND_CAPTURE_RATIO_FLOOR     = 0.40   # v2.2 NEW — suspend if bot capture drops below this
SUSPEND_CAPTURE_LOOKBACK_TRADES = 20
SUSPEND_LEAD_SILENT_DAYS        = 14
SUSPEND_CROWDING_SPIKE_PCT      = 0.50   # v2.2 NEW — suspend on >50% popularity spike
PERMANENT_DROP_AFTER_N_SUSPENSIONS_IN_60D = 2  # v2.2 NEW

# ─── Execution Filters ──────────────────────────────
MIN_LEAD_TRADE_USD              = 5
MIN_MARKET_VOLUME_24H_USD       = 5000
MIN_PRICE                       = 0.05
MAX_PRICE                       = 0.95
MAX_HOURS_TO_RESOLUTION         = 60 * 24    # 60 days
MIN_HOURS_TO_RESOLUTION         = 2

# ─── Order Placement ────────────────────────────────
MAX_BUY_SLIPPAGE_PCT            = 0.10
MAX_SELL_SLIPPAGE_PCT           = 0.15
ORDER_RETRY_PHASES              = 3
ORDER_PHASE_1_TOLERANCE         = 0.00       # FOK at exact price
ORDER_PHASE_2_TOLERANCE         = 0.02       # FOK ±2%
ORDER_PHASE_3_TOLERANCE         = 0.10       # Market with max-slippage

# ─── Exits ──────────────────────────────────────────
EXIT_MODE                       = "mirror_lead"
THESIS_BROKEN_THRESHOLD         = -0.40
THESIS_BROKEN_LEAD_QUIET_H      = 24
HARD_TIME_STOP_DAYS             = 90

# ─── Circuit Breakers ───────────────────────────────
DAILY_LOSS_HALT_PCT             = 0.15
WEEKLY_LOSS_HALT_PCT            = 0.25
PERMANENT_HALT_DRAWDOWN_PCT     = 0.40

# ─── Polling Intervals ──────────────────────────────
ACTIVITY_POLL_S                 = 15
POSITION_PRICE_UPDATE_S         = 30
WALLET_HEALTH_CHECK_S           = 86400      # daily Stage A–D rerun
SHADOW_REVIEW_S                 = 86400      # daily promotion check
ACTIVE_REVIEW_S                 = 604800     # weekly active-pool review
CLUSTER_DETECTION_RERUN_S       = 604800     # weekly (v2.2)

# ─── Mode ───────────────────────────────────────────
TRADING_MODE                    = "PAPER"
```

---

## Database Schema

### `wallets`
```sql
id, address, alias, status,
  -- status: candidate | disqualified | shadow | active | suspended | dropped
disqualified_reasons,            -- array; multiple DQ reasons possible
composite_score,
win_rate, closed_trades_count, months_active,
primary_category, category_diversity_count,
category_win_rate_floor,         -- v2.2: applied per-wallet from CATEGORY_WIN_RATE_FLOORS
avg_holding_minutes, max_drawdown_pct, single_market_pnl_pct,
volume_5min_crypto_pct, volume_15min_crypto_pct,
positive_roi_pct,                -- v2.2: avg ROI on positive resolved trades
hold_to_resolution_pct,          -- v2.2: % of positions held to resolution
consistency_score,               -- v2.2: std-dev of monthly returns (lower = better)
conviction_signal,               -- v2.2: winner_avg_size / loser_avg_size
crowding_score,                  -- v2.2: estimated follower count / public attention
crowding_score_baseline,         -- v2.2: snapshot at activation for delta detection
cluster_id, cluster_size,        -- v2.2: from PolyTrack or manual analysis
insider_proximity_score,         -- v2.2: trades-near-news anomaly score
last_trade_at, shadow_started_at, activated_at, suspended_at,
shadow_copies_count, shadow_pnl_usd, shadow_capture_ratio,    -- v2.2
shadow_failed_cycles,            -- v2.2: increments on each failed shadow validation
consecutive_losses_for_bot,
recent_capture_ratio,            -- v2.2: rolling capture ratio over last 20 copies
suspension_count_60d,            -- v2.2: for permanent-drop trigger
notes
```

### `signals` (every detected lead trade)
```sql
id, wallet_id, wallet_status_at_signal,
  -- shadow signals run through filters but only paper-fill
market_id, token_id, side, direction (BUY|SELL),
price, value_usd, lead_timestamp, detected_timestamp, 
status (executed|skipped:reason|errored), 
is_shadow (bool),
dedup_key
```

### `positions`
```sql
id, signal_id, wallet_id, market_id, token_id, side, 
entry_price, size_shares, cost_usd, 
status (open|closed|resolved),
is_shadow (bool),
opened_at, closed_at, 
exit_reason (mirror|resolve|thesis_broken|time_stop),
exit_price, realized_pnl_usd
```

### `equity_snapshots` (every hour)
```sql
timestamp, cash_balance, position_value, total_equity, 
open_position_count, daily_pnl, weekly_pnl, all_time_pnl,
shadow_equity (separate paper bankroll for shadow tracking),
current_tier, rolling_7d_avg_bankroll
```

### `tier_history`
```sql
id, timestamp, from_tier, to_tier, trigger_reason,
  -- trigger_reason: promotion | demotion | manual_override
rolling_avg_at_change, trade_size_new, max_positions_new
```

### `wallet_performance` (per wallet, recomputed weekly)
```sql
wallet_id, period (7d|30d|all), copies_executed, copies_won, 
copies_lost, copies_open, net_pnl_for_bot, signal_to_exec_ratio,
shadow_period (true if from shadow phase)
```

---

## Rollout Plan

### Stage 1: Funnel Calibration (Week 1)
- Implement v2.3 spec including full funnel
- Let Stage A–D run for 3 days; observe which wallets land in shadow pool
- Manually inspect the top 25 — do they look like real specialists?
- **Success criteria**: shadow pool contains ≥ 10 wallets that pass eyeball test
- **Failure mode**: shadow pool dominated by Théo-cluster or named bots → tighten hard disqualifiers

### Stage 2: Shadow Validation (Weeks 2–5)
- Let shadow pool run paper trades for 21+ days
- Watch which wallets generate good simulated copy P&L vs bad
- Watch capture ratio per wallet — must be ≥ 60% for promotion
- **Success criteria**: ≥ 3 wallets pass shadow promotion criteria
- **Failure mode**: <3 pass → loosen Stage E thresholds OR funnel is rejecting too aggressively

### Stage 3: Active Paper (Weeks 5–9)
- Top 5 promoted wallets become active
- 4 weeks of paper trading with real signal-to-execution measurement
- Daily review: per-wallet P&L, signal-to-exec ratio, slippage vs lead, capture ratio
- **Success criteria**: signal-to-execution ratio 10–25%; bot captures ≥ 60% of unweighted average net return of active leads over 50+ trades
- **Failure mode**: capture <40% → slippage problem or wallet-selection problem (re-check funnel)

### Stage 4: Micro-Live (Weeks 10–13)
- Only proceed if Stage 3 succeeded AND legal question resolved
- $25 real capital, $2 fixed trades (manual Tier 0 override)
- Validate plumbing, real fees, real slippage
- **Success criteria**: 50+ live trades, technical reliability >95%, measured slippage within ±50% of paper assumptions

### Stage 5: Scale Decision (Week 14+)
| Stage 4 result | Action |
|---|---|
| Net positive, capture ≥80% of leads | Remove tier override, let ladder auto-promote |
| Net flat (±5%) | Stay at $25–$100 with tier override; study weak spots |
| Net negative | Shelve. Strategy works for paper, not live — likely slippage/latency you can't fix |

**Hard caps regardless of success:**
- Never scale faster than 2× per quarter (tier ladder already enforces 1 tier/week max)
- Never run more than 5 active wallets
- The tier ladder caps trade size at $2,000 (Tier 9); do not override above this

---

## Logging & Observability

### Every signal logged
```json
{
  "timestamp": "2026-05-20T18:34:12Z",
  "wallet": "0xRN1...",
  "wallet_status": "active",
  "market": "Will Arsenal beat Spurs?",
  "side": "YES",
  "direction": "BUY",
  "lead_price": 0.42,
  "lead_size_usd": 850,
  "outcome": "executed",
  "is_shadow": false,
  "filter_results": {
    "capital_ok": true,
    "lead_size_ok": true,
    "liquidity_ok": true,
    "price_range_ok": true,
    "resolution_window_ok": true
  },
  "bot_action": {
    "fill_price": 0.428,
    "fill_size_shares": 11.68,
    "cost_usd": 5.00,
    "slippage_pct": 1.9,
    "phase_used": "phase_2"
  }
}
```

### Daily summary (Discord webhook)
```
─── Daily Summary 2026-05-20 ───
LIVE EQUITY: $107.42 (+7.42%)
TIER: 0 ($100–$249 band)  |  Trade size: $5  |  Slots: 10
Open: 6 positions, $28.50 deployed (28.5% / 50% max)
Today: 3 executed, 11 skipped, 1 closed (+$1.20)
Active wallets: 4 / 5
  - RN1 +$4.30 (12 trades, 67% WR for bot)
  - Domer +$2.10 (5 trades, 60% WR for bot)
  - ColdMath +$1.02 (8 trades, 75% WR for bot)
  - SwissTony -$0.40 (3 trades, 33% WR for bot — watch)
Signal/exec ratio: 21% (within target)

TIER PROGRESS:
  Rolling 7d avg: $128 (need $250 for Tier 1)
  Days above next threshold: 0 / 7

SHADOW POOL: 25 wallets tracking
  - 3 candidates close to promotion (shadow P&L > $0, capture ≥ 50%)
  - 2 candidates flagged for drop (shadow P&L < -$10 or capture < 30%)

FUNNEL: 23 wallets in scoring pool, 177 disqualified today
Circuit breakers: clear
```

### Alerts (immediate Discord ping)
- Position opened/closed
- Circuit breaker triggered
- Wallet promoted shadow → active
- Wallet suspended active → shadow
- Order failure after all 3 phases
- Equity changes ±5% in <1 hour
- Funnel produces < 3 candidates passing Stage C (potential data issue)
- **Tier promoted (e.g., "Tier 0 → Tier 1, trade size $5 → $10")**
- **Tier demoted (e.g., "Tier 5 → Tier 4 after drawdown, trade size $150 → $75")**

---

## What This Bot Does Not Do

- **No predictive modeling.** No NLP on market titles. No event analysis. No AI scoring of trade quality.
- **No order book micro-trading.** No market-making, no spread capture.
- **No leverage.** Spot positions only.
- **No short selling.** Buy YES or buy NO; never both.
- **No position averaging.** One entry per (market, side) per dedup window.
- **No HFT crypto markets.** Wallets trading them are disqualified at funnel Stage B.
- **No bypassing shadow mode.** Even hand-picked candidates go through 21-day shadow first.

---

## Honest Expected Performance

**Realistic monthly return for a $100 paper account with this config, copying funnel-validated specialist wallets:**

| Scenario | Gross monthly | Net monthly |
|---|---|---|
| Good month | +5% to +10% | +3% to +7% |
| Typical month | +1% to +4% | 0% to +3% |
| Bad month | -5% to -15% | -7% to -18% |

**Annualized realistic central expectation: 0% to +30%, with high variance.**

**Dollar terms at $100:** $0 to $30/year in absolute upside, against $20–$40 of typical drawdown risk in bad months. The skill-building value (learning Polymarket mechanics, learning to spot decaying edges, watching the funnel work) is the actual return at this size.

**Brutal honest summary:** copy-trading at $100 is a learning exercise, not income. Stage 3's "capture 60% of leads' return" is the real success metric. Dollar P&L at this size is noise. Don't deploy $100 you can't afford to use as tuition.

---

## Tech Stack & Project Structure

### Stack decisions (locked in)

| Layer | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | py-clob-client-v2 is Python; richest async ecosystem |
| Package manager | **uv** (or Poetry fallback) | Faster, deterministic |
| Async runtime | **asyncio + aiohttp** | All I/O is network — sync would block |
| Database | **PostgreSQL 15+** (SQLite for paper-only) | Concurrent writes from poller + dashboard + executor |
| ORM | **SQLAlchemy 2.0 async** | Mature async support |
| Migrations | **Alembic** | Standard with SQLAlchemy |
| Web framework | **FastAPI** | Async-native, OpenAPI built-in, WebSockets |
| Frontend | **HTMX + Alpine.js + Tailwind** | No build step, server-rendered, minimal deps |
| Charts | **Plotly.js** (via CDN) | Interactive equity curves, no React needed |
| Process manager | **systemd** (Linux) or **Docker Compose** | Auto-restart, log capture |
| Logging | **structlog** → JSON → file + Loki (optional) | Structured queryable logs |
| Monitoring | **Prometheus client** + Grafana | Industry standard, free tier |
| Notifications | **Discord webhook** + **ntfy.sh** (mobile push) | Both free, both reliable |
| Polymarket SDK | **polymarket-apis (pypi)** | Unified V2 Clob+Gamma+Data+Web3+WS |
| Web3 | **web3.py 7.x** | EIP-712 signing for orders |
| Goldsky (optional) | **goldsky-sdk** | For Tier 4+ WebSocket upgrade |
| Testing | **pytest + pytest-asyncio + respx** | Mock HTTP, async-aware |
| Code quality | **ruff + mypy** | Linter + type checker |

### Project structure

```
polymarket-bot/
├── pyproject.toml              # Dependencies + tooling config
├── README.md
├── .env.example
├── docker-compose.yml          # Optional deployment
├── alembic.ini
│
├── config/
│   ├── settings.py             # ALL constants from this spec
│   ├── validators.py           # Startup config validation
│   └── secrets.py              # Loads from .env / Vault / Keychain
│
├── src/
│   ├── core/
│   │   ├── models.py           # Pydantic models (Wallet, Signal, Position, etc.)
│   │   ├── enums.py            # WalletStatus, SignalStatus, ExitReason, Tier
│   │   ├── exceptions.py       # CustomExceptions
│   │   └── clock.py            # Centralized time (testable, UTC always)
│   │
│   ├── data/
│   │   ├── polymarket_client.py    # Wraps polymarket-apis
│   │   ├── goldsky_client.py       # Optional, Tier 4+
│   │   ├── polytrack_client.py     # Cluster detection
│   │   ├── rate_limiter.py         # Token bucket per endpoint
│   │   └── cache.py                # In-memory TTL cache for market metadata
│   │
│   ├── funnel/                     # Wallet selection pipeline
│   │   ├── stage_a_candidates.py
│   │   ├── stage_b_disqualifiers.py
│   │   ├── stage_c_scoring.py
│   │   ├── stage_d_ranking.py
│   │   ├── stage_e_shadow.py
│   │   ├── stage_f_active.py
│   │   └── orchestrator.py         # Runs the full pipeline
│   │
│   ├── execution/
│   │   ├── poller.py               # 15s wallet activity poller
│   │   ├── signal_normalizer.py    # API trade → internal Signal
│   │   ├── filters.py              # 5 execution filters
│   │   ├── sizer.py                # Tier-based position sizing
│   │   ├── order_engine.py         # CLOB order placement (3-phase retry)
│   │   ├── paper_fill.py           # Paper mode simulator
│   │   └── queue.py                # Event queue (asyncio.Queue or Redis)
│   │
│   ├── positions/
│   │   ├── tracker.py              # Position state machine
│   │   ├── pricer.py               # 30s price update loop
│   │   ├── exiter.py               # Mirror + resolve + thesis-broken + time-stop
│   │   └── reconciler.py           # Verify DB matches on-chain (live mode)
│   │
│   ├── risk/
│   │   ├── circuit_breakers.py
│   │   ├── tier_manager.py         # Tier promotion/demotion logic
│   │   ├── caps.py                 # Position count, deployment %, correlation
│   │   └── killswitch.py           # Emergency halt
│   │
│   ├── metrics/                    # All scoring/analysis calculations
│   │   ├── capture_ratio.py
│   │   ├── consistency.py
│   │   ├── conviction.py
│   │   ├── crowding.py
│   │   ├── insider.py
│   │   ├── clustering.py
│   │   ├── category.py             # Market → category classification
│   │   ├── hold_to_resolution.py
│   │   └── slippage_estimator.py
│   │
│   ├── db/
│   │   ├── engine.py               # Async SQLAlchemy engine
│   │   ├── models.py               # ORM models
│   │   ├── repositories.py         # Data access layer
│   │   └── migrations/             # Alembic
│   │
│   ├── api/                        # FastAPI backend for dashboard
│   │   ├── main.py
│   │   ├── deps.py                 # FastAPI dependencies
│   │   ├── routes/
│   │   │   ├── equity.py
│   │   │   ├── wallets.py
│   │   │   ├── positions.py
│   │   │   ├── signals.py
│   │   │   ├── funnel.py
│   │   │   ├── config_routes.py
│   │   │   └── health.py
│   │   └── websocket.py            # Live updates push
│   │
│   ├── notifications/
│   │   ├── discord.py
│   │   ├── ntfy.py
│   │   └── alerts.py               # Alert routing + dedup
│   │
│   ├── cli/
│   │   ├── main.py                 # Click-based CLI
│   │   └── commands/
│   │       ├── status.py
│   │       ├── wallets.py
│   │       ├── positions.py
│   │       ├── force_exit.py
│   │       ├── tier.py
│   │       └── backtest.py
│   │
│   └── runner.py                   # Main entry point — orchestrates all loops
│
├── web/                            # Dashboard frontend (static, served by FastAPI)
│   ├── index.html
│   ├── static/
│   │   ├── css/tailwind.css
│   │   └── js/
│   │       ├── htmx.min.js
│   │       ├── alpine.min.js
│   │       └── plotly.min.js
│   └── components/                 # Server-rendered HTMX partials
│       ├── equity_chart.html
│       ├── tier_card.html
│       ├── wallet_table.html
│       ├── positions_table.html
│       ├── signals_feed.html
│       └── funnel_view.html
│
├── tests/
│   ├── unit/                       # Test pure functions, formulas
│   │   ├── test_filters.py
│   │   ├── test_sizer.py
│   │   ├── test_scoring.py
│   │   ├── test_capture_ratio.py
│   │   └── test_tier_manager.py
│   ├── integration/                # Test with mocked API
│   │   ├── test_funnel_pipeline.py
│   │   ├── test_order_engine.py
│   │   └── test_exiter.py
│   ├── fixtures/                   # Captured API responses
│   │   ├── leaderboard_sample.json
│   │   ├── wallet_activity_sample.json
│   │   └── market_metadata_sample.json
│   └── conftest.py
│
└── scripts/
    ├── backtest.py                 # Run funnel on historical date range
    ├── seed_db.py                  # Initialize fresh DB
    ├── reset_paper.py              # Wipe paper state, keep funnel
    └── export_results.py           # CSV export of all trades for analysis
```

---

## Exact Metric Formulas

Every metric referenced anywhere in this spec, with exact computation rules. No ambiguity.

### Win rate

```python
win_rate = winning_resolved_trades / total_resolved_trades
```

Only **resolved** trades count. Open positions and disputed/invalid resolutions are excluded.

### Profit factor

```python
profit_factor = sum(realized_pnl for trade in wins) / abs(sum(realized_pnl for trade in losses))
```

If no losses, set profit_factor = 10.0 (capped) to avoid divide-by-zero.

### Excess win rate above category floor

```python
category_floor = CATEGORY_WIN_RATE_FLOORS.get(primary_category, CATEGORY_WIN_RATE_FLOORS["_default"])
effective_floor = max(category_floor, DQ_MIN_WIN_RATE)  # 0.55 global minimum
excess_wr = max(0, wallet_win_rate - effective_floor)
# Scaled 0–1 across the realistic range: 0% excess = 0.0, 15%+ excess = 1.0
win_rate_vs_category_floor_score = min(1.0, excess_wr / 0.15)
```

### Domain score (specialization)

```python
# % of total volume in the wallet's most-traded category
primary_category, primary_volume_pct = max(
    category_volume_breakdown.items(), 
    key=lambda kv: kv[1]
)
# Reward concentration: 60% in one cat = 1.0, 33% = 0.0
domain_score = max(0, (primary_volume_pct - 0.33) / (0.60 - 0.33))
domain_score = min(1.0, domain_score)
```

### Hold-to-resolution %

```python
# For each closed position, was it held until the market resolved (not exited early)?
held_to_resolution_count = sum(
    1 for pos in closed_positions
    if pos.closed_at >= pos.market_resolution_time - timedelta(hours=2)
)
hold_to_resolution_pct = held_to_resolution_count / len(closed_positions)
```

The 2-hour buffer accounts for last-minute close-outs that are effectively at resolution.

### Consistency score

```python
# Group resolved P&L by calendar month
monthly_returns = group_pnl_by_month(resolved_trades)  # list of monthly $ returns

if len(monthly_returns) < 3:
    consistency_score = 0.5  # neutral until enough data
else:
    mean_return = statistics.mean(monthly_returns)
    if mean_return <= 0:
        consistency_score = 0.0  # not profitable on average — no consistency credit
    else:
        # Coefficient of variation; lower = more consistent
        std_dev = statistics.stdev(monthly_returns)
        cv = std_dev / mean_return
        # CV of 0.5 = excellent, CV of 2.0+ = chaotic
        consistency_score = max(0, 1 - (cv / 2.0))
```

### Conviction signal

```python
# Position size on winners vs losers — real conviction means betting bigger on wins
winner_sizes = [pos.cost_usd for pos in wins]
loser_sizes = [pos.cost_usd for pos in losses]

if not winner_sizes or not loser_sizes:
    conviction_signal = 0.5  # neutral until enough data
else:
    avg_winner = statistics.median(winner_sizes)
    avg_loser = statistics.median(loser_sizes)
    ratio = avg_winner / avg_loser  # > 1.0 means winners are larger

    # Ratio of 1.0 = no conviction differential → 0.0
    # Ratio of 3.0+ = strong conviction → 1.0
    conviction_signal = min(1.0, max(0, (ratio - 1.0) / 2.0))
```

Uses MEDIAN not mean to avoid outlier contamination (one $5M bet shouldn't dominate).

### Counter-trade signal

```python
# Per Stand.trade: high-volume losers can be counter-traded profitably
# This is a BIDIRECTIONAL factor — positive for normal scoring, NEGATIVE inverted for counter-list

if wallet.net_pnl_usd < -5000 and wallet.total_volume_usd > 50000:
    # High-volume losers: useful as counter-trade signal
    counter_trade_signal = -1.0  # NEGATIVE entry score (we'd invert their trades)
    wallet.is_counter_trade_candidate = True
else:
    counter_trade_signal = 0.0
```

Counter-trade candidates go into a SEPARATE shadow pool that mirrors their trades INVERTED (buy NO when they buy YES). Default: disabled. Enable via `ENABLE_COUNTER_TRADE_SHADOW = True`.

### Crowding penalty

```python
# Proxy for follower count / public attention
crowding_score = 0
crowding_score += min(0.4, wallet.polymarket_followers / 1000)  # Polymarket native
crowding_score += min(0.3, wallet.twitter_mentions_30d / 100)   # Social mentions
crowding_score += min(0.3, wallet.appears_in_oracle_newsletter * 0.3)  # Featured in The Oracle

# 0.0 = unknown, 1.0 = very famous
# Penalty is applied with weight W_CROWDING_PENALTY = -0.10
```

**Implementation note**: Twitter mention count requires a separate scraping pipeline (e.g., periodic search for the wallet's username). If unavailable, default to 0.

### Insider proximity score

```python
# Did the wallet trade unusually close to news breaks?
# Requires news event timestamp dataset (Polysights provides this in their Beta Insider Finder)

suspicious_trade_count = 0
for trade in wallet.recent_trades(days=90):
    matching_news = find_news_events(
        market_id=trade.market_id,
        time_window=(trade.timestamp, trade.timestamp + timedelta(hours=6))
    )
    if matching_news and trade.timestamp < matching_news[0].timestamp:
        # Wallet traded BEFORE news broke
        suspicious_trade_count += 1

insider_proximity_score = min(1.0, suspicious_trade_count / 10)
# 0 suspicious trades = 0.0 (fine)
# 10+ suspicious trades = 1.0 (max penalty)
```

If no news-event dataset available, the bot logs `insider_proximity_score = 0` and notes data unavailable in the wallet record.

### Max drawdown %

```python
# Walk through wallet's equity curve (cumulative P&L over time)
equity_curve = compute_cumulative_pnl_by_day(wallet.resolved_trades)

peak = 0
max_dd = 0
for point in equity_curve:
    if point > peak:
        peak = point
    if peak > 0:
        drawdown = (peak - point) / peak
        max_dd = max(max_dd, drawdown)

max_drawdown_pct = max_dd  # 0.0 = no DD, 0.40 = 40% peak-to-trough
```

### Cluster size

```python
# If PolyTrack subscription active:
cluster_size = polytrack_client.get_cluster(wallet.address).size

# If not (DIY heuristic — basic but functional):
def detect_cluster_diy(wallet, candidate_pool):
    """Returns probable cluster size based on funding correlation."""
    funding_source = wallet.first_funding_tx.from_address  # Common Kraken/Coinbase address
    funding_amount = wallet.first_funding_tx.value_usd

    related = []
    for other in candidate_pool:
        if other.address == wallet.address:
            continue
        same_funder = (other.first_funding_tx.from_address == funding_source)
        similar_amount = abs(other.first_funding_tx.value_usd - funding_amount) / funding_amount < 0.1
        funded_close_in_time = abs(
            (other.first_funding_tx.timestamp - wallet.first_funding_tx.timestamp).days
        ) < 7
        if same_funder and (similar_amount or funded_close_in_time):
            related.append(other)
    
    return 1 + len(related)
```

DIY clustering is weaker than PolyTrack but free. If a wallet has cluster_size > 2, flag for manual review before active promotion.

### Capture ratio

```python
# THE single most important metric for the bot
# Measures: how much of the lead's P&L did the bot's copies capture?

def compute_capture_ratio(wallet_id, lookback_days=21):
    bot_copies = get_bot_copies_of_wallet(wallet_id, lookback_days)
    lead_trades = get_lead_trades(wallet_id, lookback_days)

    bot_pnl = sum(c.realized_pnl_usd + c.unrealized_pnl_usd for c in bot_copies)
    lead_pnl = sum(t.realized_pnl_usd + t.unrealized_pnl_usd for t in lead_trades)
    
    # NORMALIZE for size difference (bot bets fixed $5–$2000, lead bets variable)
    bot_total_invested = sum(c.cost_usd for c in bot_copies)
    lead_total_invested = sum(t.cost_usd for t in lead_trades)
    
    if lead_total_invested == 0:
        return None
    
    bot_roi = bot_pnl / bot_total_invested if bot_total_invested > 0 else 0
    lead_roi = lead_pnl / lead_total_invested if lead_total_invested > 0 else 0
    
    if lead_roi == 0:
        return None
    
    # Capture ratio = how much of lead's ROI did we get
    return bot_roi / lead_roi
```

Capture ratio is computed two ways and both are stored:
- **Trade-level**: ratio over a rolling 20-trade window (used for suspension triggers)
- **Period-level**: ratio over a rolling 21-day window (used for shadow promotion)

### Composite score

```python
def compute_composite_score(wallet):
    s = 0
    s += W_LOG_TRADES * math.log10(max(1, wallet.closed_trades_count))
    s += W_WIN_RATE_VS_CATEGORY_FLOOR * wallet.win_rate_vs_category_floor_score
    s += W_LOG_PROFIT_FACTOR * math.log10(max(0.1, wallet.profit_factor))
    s += W_MONTHS_ACTIVE * min(1.0, wallet.months_active / 24)
    s += W_DOMAIN_SCORE * wallet.domain_score
    s += W_HOLD_TO_RESOLUTION_PCT * wallet.hold_to_resolution_pct
    s += W_CONSISTENCY_SCORE * wallet.consistency_score
    s += W_CONVICTION_SIGNAL * wallet.conviction_signal
    s += W_COUNTER_TRADE_SIGNAL * wallet.counter_trade_signal  # usually 0
    s += W_ENTROPY * wallet.entropy_score
    s += W_INSIDER_PROXIMITY * wallet.insider_proximity_score
    s += W_MAX_DRAWDOWN * wallet.max_drawdown_pct
    s += W_CROWDING_PENALTY * wallet.crowding_score
    
    # Clamp to [0, 10]
    return max(0, min(10, s * 10))
```

### Slippage estimator (paper mode)

```python
def estimate_slippage(market_volume_24h_usd, trade_size_usd):
    """Returns slippage as decimal (0.01 = 1%)."""
    # Base slippage by liquidity tier
    if market_volume_24h_usd >= 500_000:
        base = 0.003
    elif market_volume_24h_usd >= 100_000:
        base = 0.005
    elif market_volume_24h_usd >= 50_000:
        base = 0.010
    elif market_volume_24h_usd >= 10_000:
        base = 0.020
    elif market_volume_24h_usd >= 5_000:
        base = 0.025
    else:
        return None  # filtered out at Filter 3
    
    # Size impact: trades > 1% of daily volume add slippage
    size_pct_of_volume = trade_size_usd / market_volume_24h_usd
    impact = max(0, (size_pct_of_volume - 0.01) * 2.0)
    
    return base + impact
```

---

## State Machines

### Wallet status transitions

```
                      ┌─────────────┐
                      │  candidate  │  Stage A pulls from leaderboard
                      └──────┬──────┘
                             │ Stage B: hard disqualifiers
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
            ┌──────────┐         ┌──────────────┐
            │ shadow   │         │ disqualified │  Permanent unless re-evaluated
            └────┬─────┘         └──────────────┘
                 │ Stage E: 21-day validation
       ┌─────────┴─────────┬─────────────────┐
       │                   │                 │
       ▼                   ▼                 ▼
  ┌────────┐          ┌──────────┐      ┌─────────┐
  │ active │          │  bench   │      │ dropped │  After 2 failed shadow cycles
  └───┬────┘          └────┬─────┘      └─────────┘
      │ Suspension trigger │ Auto-promote when active slot opens
      │                    │
      ▼                    │
  ┌──────────┐             │
  │suspended │─────────────┘ (after 21-day re-validation in shadow)
  └────┬─────┘
       │ 2nd suspension within 60 days
       ▼
  ┌─────────┐
  │ dropped │
  └─────────┘
```

Allowed transitions only (anything else = bug):
- `candidate → shadow` (passes Stage B)
- `candidate → disqualified` (fails Stage B)
- `disqualified → candidate` (manual re-evaluation only)
- `shadow → active` (passes Stage E)
- `shadow → bench` (passes Stage E but ranked >5)
- `shadow → dropped` (fails 2 shadow cycles)
- `active → suspended` (suspension trigger fires)
- `bench → active` (active slot opens, this wallet is top-ranked bench)
- `suspended → shadow` (1st suspension, re-validate)
- `suspended → dropped` (2nd suspension within 60 days)
- `dropped → candidate` (manual override only, requires 90-day cooldown)

### Position status transitions

```
       (filter chain pass + order placement)
        ┌──────────────┐
        │   pending    │
        └──────┬───────┘
               │ Order filled
               ▼
        ┌──────────────┐
        │     open     │◄────┐ Price updates loop (every 30s)
        └──────┬───────┘     │
               │             │
               ├─────────────┘
               │
               │ Exit trigger fires
               ▼
        ┌──────────────┐
        │   closing    │  Sell order placed
        └──────┬───────┘
               │ Sell filled
               ▼
        ┌──────────────┐
        │    closed    │  Realized P&L recorded
        └──────────────┘

        OR

        ┌──────────────┐
        │     open     │
        └──────┬───────┘
               │ Market resolves while position open
               ▼
        ┌──────────────┐
        │   resolved   │  Auto-redeem at $1.00 or $0.00
        └──────────────┘
```

Each transition writes a row to `position_state_log` for audit.

### Exit reason taxonomy

| Reason | Trigger | Code path |
|---|---|---|
| `mirror_full` | Lead sold 100% of their position | `positions/exiter.py::on_lead_sell` |
| `mirror_partial` | Lead sold X% — bot sells X% | `positions/exiter.py::on_lead_sell` |
| `resolve_win` | Market resolved, position won | `positions/exiter.py::on_resolve` |
| `resolve_loss` | Market resolved, position lost | `positions/exiter.py::on_resolve` |
| `resolve_invalid` | UMA disputed and invalidated | `positions/exiter.py::on_resolve` |
| `thesis_broken` | -40% AND lead inactive 24h+ | `positions/exiter.py::sanity_check` |
| `time_stop` | Position open ≥ 90 days | `positions/exiter.py::time_stop_sweep` |
| `circuit_breaker` | Permanent halt triggered | `risk/circuit_breakers.py::halt` |
| `manual` | CLI or dashboard force-close | `cli/commands/force_exit.py` |

---

## Error Handling & Resilience

### API failure handling

Every API call wrapped in retry logic with these rules:

| Error type | Retries | Backoff | Action after exhaustion |
|---|---|---|---|
| 429 (rate limit) | 5 | Exponential, start 2s, cap 60s | Wait 5 min, then retry |
| 500/502/503 (server) | 3 | Exponential, start 1s, cap 30s | Log critical, alert Discord |
| Timeout (>10s) | 2 | Linear, 5s between | Skip this iteration |
| Connection refused | 5 | Exponential, start 1s, cap 30s | Halt poller for 5 min |
| 401/403 (auth) | 0 | None | Halt bot, alert URGENT |
| 4xx other | 0 | None | Log, skip operation |

Rate limit budget tracking — token bucket per endpoint:

```python
RATE_LIMITS = {
    "data.leaderboard":    (1000, 10),  # 1000 req / 10s
    "data.trades":         (200, 10),
    "data.positions":      (150, 10),
    "data.activity":       (1000, 10),
    "gamma.events":        (500, 10),
    "gamma.markets":       (300, 10),
    "gamma.general":       (4000, 10),
    "clob.read":           (1500, 10),
    "clob.post_order":     (3500, 10),  # burst
    "clob.post_order_min": (36000, 600), # sustained
}
```

When 70% of bucket capacity is consumed, the bot enters CONSERVATIVE mode (slows non-critical polling). At 90%, only execution-critical calls go through.

### Restart-after-crash protocol

On startup the runner executes:

1. **Config validation** — every constant in settings.py has its expected type and range
2. **DB schema check** — current Alembic revision matches code
3. **Reconciliation** — for every position marked `open` in DB, query CLOB to verify it actually exists; flag mismatches as `RECONCILE_REQUIRED` and alert
4. **Pending order recovery** — any `pending` orders older than 5 minutes get cancelled and re-evaluated
5. **Tier recompute** — recalculate current tier from rolling 7d avg
6. **Wallet status verification** — for each `active` wallet, verify last shadow_pnl is still positive; demote any that failed during downtime
7. **Circuit breaker state restore** — if a halt was in effect, restore it with original timer

### What does NOT auto-recover

- **Live mode private key compromise** — halts the bot, requires manual re-auth
- **Persistent rate-limit lockout** — pages operator after 1 hour of failed retries
- **DB corruption** — halts bot, requires backup restore
- **Polymarket API breaking change** — error budget exceeds threshold, halts, alerts

### Notification severity tiers

| Severity | Channel | Examples |
|---|---|---|
| INFO | Discord daily digest | Trades executed, tier check, funnel run complete |
| WARN | Discord ping | Wallet suspended, capture ratio dropped, API slowdown |
| CRITICAL | Discord ping + ntfy | Circuit breaker fired, order failure final, capture < 30% |
| URGENT | Discord ping + ntfy + email | Auth failure, DB corruption, KILLSWITCH triggered |

---

## Web Dashboard Specification

A single-page web app on `localhost:8000` (or any port) showing real-time bot state. Built with FastAPI + HTMX + Alpine.js + Tailwind + Plotly.js — no build step, server-rendered.

### Page layout

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  ┌──────────────┐                                                            ║
║  │ Polymarket   │   PAPER MODE  •  Tier 0 ($100–$249)  •  All systems green ║
║  │ Copy Bot     │                                                            ║
║  └──────────────┘                                                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌────────── EQUITY ──────────┐  ┌─────── TIER ──────────────────────────┐  ║
║  │                            │  │ Current: 0   •   Trade size: $5       │  ║
║  │    [Plotly equity curve]   │  │ Slots: 6/10   •   Deployed: $28 (28%) │  ║
║  │                            │  │ ──────────────────────────────────    │  ║
║  │    $107.42 (+7.4%)         │  │ Next tier @ $250                      │  ║
║  │    7-day: +$5.20           │  │ Rolling 7d avg: $128                  │  ║
║  │    All-time: +$7.42        │  │ Days above next: 0/7                  │  ║
║  └────────────────────────────┘  └────────────────────────────────────────┘  ║
║                                                                              ║
║  ┌─────────────────────── ACTIVE WALLETS (4/5) ─────────────────────────┐    ║
║  │  Wallet      Cat       Score  WR   Capture  Bot P&L   Last Trade    │    ║
║  │  RN1         soccer    8.4    67%  82%      +$4.30    2h ago        │    ║
║  │  Domer       politics  7.9    62%  74%      +$2.10    14m ago       │    ║
║  │  ColdMath    weather   7.7    71%  88%      +$1.02    1d ago        │    ║
║  │  SwissTony   soccer    7.2    58%  56%      -$0.40    3h ago [WATCH]│    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌────── OPEN POSITIONS (6) ──────┐  ┌────── LIVE SIGNAL FEED ─────────┐    ║
║  │  Mkt          Side  Size  P&L  │  │ 14:32 RN1 BUY Arsenal $5.00 ✓  │    ║
║  │  Arsenal-Spurs YES  $5   +0.2 │  │ 14:31 Domer SELL Spurs (skip)  │    ║
║  │  Fed-rate-cut  YES  $5   -0.1 │  │ 14:28 ColdMath BUY temp (skip: │    ║
║  │  NBA-final     NO   $5   +0.0 │  │       liquidity <$5k)          │    ║
║  │  ...                          │  │ 14:25 SwissTony BUY Bayern $5 ✓│    ║
║  └────────────────────────────────┘  └─────────────────────────────────┘    ║
║                                                                              ║
║  ┌─────────── FUNNEL STATUS ──────┐  ┌──── CIRCUIT BREAKERS ──────────┐     ║
║  │ Candidates: 200                │  │ Daily P&L:   -2% / -15% ✓     │     ║
║  │ Scored:     23                 │  │ Weekly P&L:  +6% / -25% ✓     │     ║
║  │ Shadow:     14/25              │  │ Max DD:      4% / 40% ✓       │     ║
║  │ Active:     4/5                │  │ Killswitch:  off              │     ║
║  └────────────────────────────────┘  └────────────────────────────────┘     ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [Equity] [Wallets] [Positions] [Signals] [Funnel] [Settings] [Logs]         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Pages in detail

**1. Overview (default landing)**
- Top bar: mode badge (PAPER/LIVE), tier, system health dot
- Equity card: Plotly chart with 1d/7d/30d/all toggle; current value + delta
- Tier card: current tier, trade size, slots, deployment %, progress to next tier
- Active wallets table: live capture ratio per wallet, color-coded
- Open positions: market name, side, entry/current price, P&L
- Live signal feed: streaming WebSocket updates of incoming signals + filter outcomes
- Funnel status: candidate → scored → shadow → active counts
- Circuit breakers: each breaker with current value vs threshold, green/yellow/red

**2. Wallets page**
- Tabs: Active (5) / Shadow (25) / Bench / Candidates / Disqualified / Suspended / Dropped
- For each wallet, full metric breakdown: composite score, all 13 sub-scores, category, win rate, profit factor, max DD, capture ratio (rolling 20 + period 21d), cluster size, suspension history
- Click into wallet → modal with: equity curve of that wallet, last 50 trades, all bot copies of that wallet with P&L
- Action buttons: force-suspend, force-promote (with warning), add manual note

**3. Positions page**
- Tabs: Open / Closed (last 7d) / Resolved (last 7d) / All
- For each open position: market, side, entry, current, P&L $, P&L %, lead wallet, time held, distance to resolution
- For closed: exit reason badge, realized P&L
- Action buttons: force-exit individual position, force-exit all (requires typed confirmation)
- Filter by wallet, by market category, by date range

**4. Signals page**
- Tab: Live feed (default) — streaming via WebSocket
- Tab: History — searchable log of every signal, filter outcome shown per signal
- Each signal row: timestamp, wallet, market, side, lead size, bot decision (executed / skipped:reason), if executed → fill details
- Aggregate stats at top: signals/day, execution rate, skip reasons breakdown (pie chart)

**5. Funnel page**
- Visual pipeline: 200 candidates → disqualifiers (with breakdown of which DQs are firing most) → scored → shadow pool → active
- For each disqualifier, show count of wallets currently failing it
- Shadow pool detail: each shadow wallet with simulated P&L curve, capture ratio, days until promotion eligible
- Manual "Force re-run funnel" button (cooldown 1h)

**6. Settings page**
- View current config (read-only display of settings.py values, grouped)
- Editable: tier override (dropdown 0-9 or auto), killswitch (toggle), Discord webhook URL test, ntfy topic test
- Mode toggle: Paper ↔ Live (requires typed confirmation + private key re-auth in live)
- Backup: download current DB snapshot

**7. Logs page**
- Last 1000 log entries, structured JSON parsed into table
- Filter by severity (INFO/WARN/CRITICAL/URGENT) and component (poller/funnel/exec/risk/etc.)
- Search bar with regex support
- Export to CSV

### Real-time updates

- WebSocket connection from dashboard to `/ws` endpoint
- Backend pushes events: `signal.detected`, `position.opened`, `position.closed`, `wallet.promoted`, `tier.changed`, `breaker.fired`, `health.degraded`
- Frontend uses HTMX SSE or raw WebSocket; Alpine.js handles small DOM updates

### Dashboard auth

- Default: localhost-only, no auth (firewall handles it)
- Optional: basic auth via env var `DASHBOARD_USER` + `DASHBOARD_PASS` if exposed beyond localhost
- HTTPS optional via Caddy reverse proxy

### Mobile

- Tailwind responsive — collapses to single column on phones
- Critical info (equity, tier, breakers) visible without scroll
- Tap-friendly buttons

---

## CLI Reference

The CLI is the operator's primary control surface when the dashboard isn't available. All commands are read-only by default; mutating commands require `--confirm`.

```
$ polymarket-bot --help

Usage: polymarket-bot COMMAND [OPTIONS]

Commands:
  status              Show current bot state (one-screen summary)
  start               Start the runner (foreground)
  stop                Stop gracefully (waits for in-flight orders)
  
  wallets list        List wallets by status (--status=active/shadow/etc.)
  wallets show ADDR   Show full wallet metrics
  wallets suspend ADDR --confirm
  wallets promote ADDR --confirm
  
  positions list      List open positions
  positions show ID   Show position details + lead trade chain
  positions exit ID --confirm
  positions exit-all --confirm
  
  tier show           Current tier + progression
  tier set N --confirm
  tier auto --confirm
  
  funnel run --confirm        Force funnel re-run now
  funnel show                 Current funnel state
  
  killswitch on --confirm     Halt all new entries
  killswitch off --confirm
  
  backtest run --start=DATE --end=DATE --wallets=N
  backtest results LATEST
  
  db backup PATH
  db restore PATH --confirm
  db migrate                  Run Alembic migrations
  
  config show                 Print current config
  config validate             Verify all settings are valid
```

### Common workflows

```bash
# Morning check
polymarket-bot status

# Investigate a underperforming wallet
polymarket-bot wallets show 0xRN1...

# Manually force-suspend a wallet you don't trust
polymarket-bot wallets suspend 0xABC... --confirm

# Emergency halt
polymarket-bot killswitch on --confirm

# Run a backtest of last 90 days
polymarket-bot backtest run --start=2026-02-20 --end=2026-05-20

# Backup before changes
polymarket-bot db backup /home/jackson/backups/bot-$(date +%F).db
```

---

## Backtesting Harness

Located at `scripts/backtest.py`. Replays historical Polymarket data through the full funnel and execution logic.

### Inputs
- Date range (start, end)
- Initial bankroll (default $100)
- Optional: override config values for sensitivity testing

### Process
1. Snapshot leaderboard as of `start_date`
2. Run Stage B–D against snapshot
3. Simulate shadow mode for 21 days starting `start_date`
4. Promote wallets per shadow rules
5. From `start_date + 21 days` to `end_date`: walk forward day-by-day
6. For each historical trade by active wallets: run 5-filter chain (with historical market data) → simulate fill → track position lifecycle
7. Apply realistic latency (random 1–18 second delay → fill at the price 2 seconds after detection)
8. Resolve positions on actual historical resolution outcomes
9. Output: full equity curve, per-wallet capture ratio, signal-to-exec ratio, max drawdown, ending bankroll

### Outputs
- `backtest_YYYY-MM-DD_to_YYYY-MM-DD.csv` — every simulated trade
- `backtest_summary.json` — aggregate metrics
- `backtest_equity_curve.png` — chart
- Console table with key stats

### Walk-forward analysis (avoid look-ahead bias)
- Wallet selection at time `t` uses ONLY data available at `t-1`
- Never use future P&L to select wallets
- Cross-validate: train on first 60 days, test on next 30, slide window

### Limitations honest
- Backtest assumes historical book depth was as deep as 24h volume suggests — overoptimistic in thin markets
- Backtest cannot perfectly recreate latency (mempool conditions vary)
- Backtest assumes APIs were as reliable historically as today — false during major events

---

## Testing Strategy

### Unit tests (pytest, all pure functions)

```
tests/unit/
├── test_filters.py          # Each of 5 filters with edge cases
├── test_sizer.py            # Tier ladder math, promotion/demotion
├── test_scoring.py          # Composite score, each sub-metric
├── test_capture_ratio.py    # ROI normalization edge cases
├── test_consistency.py      # CV calculation with various distributions
├── test_conviction.py       # Median-based, outlier resistance
├── test_crowding.py         # Score composition
├── test_slippage.py         # All 6 liquidity tiers, impact addition
├── test_clustering.py       # DIY funder heuristic
├── test_tier_manager.py     # All transition guardrails
└── test_state_machines.py   # Wallet status, position status transitions
```

### Integration tests (mocked APIs via respx)

```
tests/integration/
├── test_funnel_pipeline.py    # Full Stage A → F with fixture data
├── test_order_engine.py       # 3-phase retry against mocked CLOB
├── test_exiter.py             # All exit reasons against mocked feeds
├── test_poller.py             # 15s loop with simulated API responses
├── test_reconciliation.py     # Startup with stale DB state
└── test_circuit_breakers.py   # Trigger each breaker, verify halt
```

### Fixture data
- Real captured API responses anonymized into `tests/fixtures/`
- Includes: leaderboard (full top 200), wallet activities, market metadata, order books, edge cases (Théo cluster wallet, HFT bot wallet, dormant wallet, perfect-record wallet)

### Coverage target
- Unit: 90%+
- Integration: critical paths only (funnel, order placement, exits) — 100% on these

### CI
- GitHub Actions: lint (ruff) + type check (mypy) + tests on push
- Don't deploy if any of these fail

---

## Deployment

### Local development
```bash
git clone <repo> polymarket-bot
cd polymarket-bot
uv sync
cp .env.example .env       # Fill in
uv run alembic upgrade head
uv run polymarket-bot start
# Dashboard at http://localhost:8000
```

### Production (VPS — Hetzner CCX12 ~$4.50/mo recommended)

**Option 1: systemd (recommended for simplicity)**

```ini
# /etc/systemd/system/polymarket-bot.service
[Unit]
Description=Polymarket Copy Bot
After=network.target postgresql.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/polymarket-bot
EnvironmentFile=/home/botuser/polymarket-bot/.env
ExecStart=/home/botuser/.local/bin/uv run polymarket-bot start
Restart=on-failure
RestartSec=30
StandardOutput=append:/var/log/polymarket-bot/stdout.log
StandardError=append:/var/log/polymarket-bot/stderr.log

[Install]
WantedBy=multi-user.target
```

**Option 2: Docker Compose (recommended for portability)**

```yaml
# docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    env_file: .env
    restart: unless-stopped
    depends_on: [db]
    ports: ["8000:8000"]
    volumes: ["./logs:/app/logs"]
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: bot
      POSTGRES_DB: polymarket_bot
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    restart: unless-stopped

  caddy:    # Optional HTTPS reverse proxy
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile"]

volumes:
  pgdata:
secrets:
  db_password:
    file: ./.secrets/db_password
```

### Secrets management
- **Never** commit `.env` or private keys
- Live mode: use `keyring` (macOS) or `pass` (Linux) for the private key — `.env` only holds a reference to the keychain entry
- API keys (Discord webhook, Polymarket L2): `.env` is fine, but `chmod 600`
- Backup the keychain entries to encrypted USB

### Backup strategy
- DB backup: nightly cron, `pg_dump` to `/backups/` with 30-day retention
- Off-site: rsync to a second VPS or B2 bucket
- Config + scripts: git repo (private)
- Recovery test: monthly — actually restore to a staging VM

---

## Health Check & Monitoring

### `/health` endpoint
Returns 200 with JSON body if all of:
- DB reachable
- Last poller iteration < 30s ago
- Last funnel run < 25h ago
- No active CRITICAL alerts
- Polymarket API reachable

Otherwise 503 with details.

### Prometheus metrics
Exposed at `/metrics`:
- `bot_equity_usd` (gauge)
- `bot_open_positions` (gauge)
- `bot_current_tier` (gauge)
- `bot_active_wallets` (gauge)
- `bot_shadow_wallets` (gauge)
- `bot_signals_total` (counter, label: outcome)
- `bot_orders_placed_total` (counter, label: phase)
- `bot_order_failures_total` (counter, label: reason)
- `bot_capture_ratio_per_wallet` (gauge, label: wallet)
- `bot_api_calls_total` (counter, label: endpoint)
- `bot_api_rate_limit_utilization` (gauge, label: endpoint)
- `bot_circuit_breaker_state` (gauge)
- `bot_uptime_seconds` (gauge)

### Grafana dashboard
Pre-built JSON in `grafana/dashboard.json`. Panels:
- Equity curve
- Per-wallet capture ratio over time
- API rate limit utilization heatmap
- Signal-to-execution ratio rolling 24h
- Funnel pipeline counts over time

---

## Configuration Validation

On startup, `config/validators.py` runs:

```python
def validate_config():
    """Verifies every config value is sensible. Crashes hard on failure."""
    assert 0 < PAPER_INITIAL_BALANCE <= 1_000_000
    assert TIER_TABLE[0]["min_bankroll"] <= PAPER_INITIAL_BALANCE
    assert all(t1["min_bankroll"] < t2["min_bankroll"] 
               for t1, t2 in zip(TIER_TABLE, TIER_TABLE[1:]))
    
    assert 0 < SHADOW_MODE_MIN_DAYS <= 90
    assert 0 < SHADOW_POOL_SIZE <= 100
    assert 0 < ACTIVE_POOL_SIZE <= SHADOW_POOL_SIZE
    assert 0 < SHADOW_MIN_CAPTURE_RATIO <= 1.0
    
    # Disqualifier sanity
    assert 0 < DQ_MIN_WIN_RATE < 1.0
    assert 0 < DQ_MIN_CLOSED_TRADES
    assert 0 < DQ_MAX_DRAWDOWN_PCT < 1.0
    
    # Scoring weights — positive factors should sum to roughly 1.0–1.5
    positive_weights = [W_LOG_TRADES, W_WIN_RATE_VS_CATEGORY_FLOOR, 
                        W_LOG_PROFIT_FACTOR, W_MONTHS_ACTIVE, W_DOMAIN_SCORE,
                        W_HOLD_TO_RESOLUTION_PCT, W_CONSISTENCY_SCORE,
                        W_CONVICTION_SIGNAL]
    assert 0.8 <= sum(positive_weights) <= 1.5
    
    # Negative weights should sum to small negative
    negative_weights = [W_ENTROPY, W_INSIDER_PROXIMITY, W_MAX_DRAWDOWN, W_CROWDING_PENALTY]
    assert -0.5 <= sum(negative_weights) <= 0
    
    # Category floors must be in [0.5, 0.9]
    for cat, floor in CATEGORY_WIN_RATE_FLOORS.items():
        assert 0.5 <= floor <= 0.9, f"Category floor for {cat} out of range"
    
    # Execution
    assert 0 < MAX_BUY_SLIPPAGE_PCT < 0.3
    assert 0 < MAX_SELL_SLIPPAGE_PCT < 0.3
    assert MIN_PRICE < MAX_PRICE
    assert MIN_HOURS_TO_RESOLUTION < MAX_HOURS_TO_RESOLUTION
    
    # Mode-specific
    if TRADING_MODE == "LIVE":
        assert os.getenv("POLYMARKET_PRIVATE_KEY")
        assert os.getenv("POLYMARKET_API_KEY")
        # ... etc
```

If any assertion fails, bot does NOT start. Error message is verbose and tells you exactly which value to fix.

---

## Time Handling

**Everything in UTC. Always.** No exceptions.

- DB timestamps: `TIMESTAMPTZ` columns, always UTC
- Display in dashboard: convert to user's local timezone client-side (JS)
- Cron-like schedules: defined in UTC (e.g., funnel runs at 12:00 UTC)
- Log timestamps: ISO 8601 with `Z` suffix

`core/clock.py` provides a single `now()` function — never use `datetime.now()` directly. This makes tests deterministic (can mock the clock).

---

## Data Retention

| Table | Retention | Reason |
|---|---|---|
| `wallets` | Forever | Need full history for rescoring |
| `signals` | 90 days hot, archived after | Volume gets large |
| `positions` | Forever | Audit trail |
| `equity_snapshots` | Forever (downsampled after 30d) | Long-term chart |
| `position_state_log` | 1 year | Audit |
| `api_call_log` | 7 days | Debug only |
| `notification_log` | 30 days | Dedup reference |

Archival: nightly job moves rows older than retention to `archive/` parquet files. Read access still possible via separate query.

---



---

## Quick Reference: v1 → v2.3 Diff

| Component | v1 | v2.1 | v2.2 | v2.3 |
|---|---|---|---|---|
| Watchlist source | Top 20 score | Funnel 200→20→5 | Funnel 200→25→5 + clusters | Same |
| Hard disqualifiers | None | 11 | 13 | 13 (unchanged) |
| Category WR floors | No | No | Yes | Yes (unchanged) |
| Scoring factors | 9 | 9 | 13 | 13 (unchanged) |
| Cluster detection | No | No | PolyTrack | **PolyTrack + DIY funder heuristic fallback** |
| Capture ratio | No | Implicit | ≥60% promote | Same + **exact formula spec'd** |
| Shadow validation | None | 14d | 21d | 21d (unchanged) |
| Exact metric formulas | No | No | No | **YES — all 12 formulas** |
| State machines | Implicit | Implicit | Implicit | **Explicit — all wallet + position transitions** |
| Error handling | Vague | Vague | Vague | **Per-error-type retry/backoff matrix + rate budget** |
| Web dashboard | No | No | No | **Full FastAPI + HTMX 7-page spec** |
| CLI | No | No | No | **Full command reference** |
| Tech stack | Implicit | Implicit | Partial | **Fully locked: Python/asyncio/Postgres/FastAPI/HTMX** |
| Project structure | No | No | No | **Full directory tree** |
| Backtesting | No | No | Mentioned | **Full walk-forward harness spec** |
| Testing | No | No | No | **Unit + integration + fixtures strategy** |
| Deployment | No | No | No | **systemd + Docker Compose** |
| Health/monitoring | Partial | Partial | Partial | **`/health` + Prometheus metrics + Grafana** |
| Config validation | No | No | No | **Startup `validate_config()` with all assertions** |
| Time handling | Implicit | Implicit | Implicit | **UTC everywhere, mockable `clock.py`** |
| Data retention | No | No | No | **Per-table retention + archival policy** |
| Execution filters | 11 | 5 | 5 | 5 (unchanged) |
| Min lead trade | $100 | $5 | $5 | $5 (unchanged) |
| Stop-loss | 20% | None | None | None (unchanged) |
| Position sizing | Fixed $5–10 | Fixed $5–10 | 10-tier ladder | 10-tier ladder (unchanged) |
| Bot copies HFT | Yes | No | No | No (unchanged) |

---

## Appendix: Research Sources

Every threshold, weight, and design decision in this spec is anchored to a primary source. Listed here so you (or the next person reading this) can verify or update as the landscape changes.

### Academic studies on copy trading and alpha decay
- **Shen et al. — "Copy Trading" (ResearchGate, 2018, updated 2024).** Randomized field experiment on crypto social trading platform. Finding: traders with increased follower count trade more frequently, use higher leverage, and *attain poorer performance*. Empirical basis for the `crowding_penalty` factor in scoring.
- **Di Mascio, Lines & Naik — "Alpha Decay" (SSRN 2580551, Inalytics/Columbia/LBS).** Documents that institutional alpha decays slowly (~12 months) and traders accumulate positions in iceberged increments — the same pattern Stand.trade describes Domer using. Basis for tolerating wallets with small individual trade sizes.
- **"Not All Factors Crowd Equally" (arXiv 2512.11913).** Game-theoretic model of factor crowding: α(t) = K / (1+λt), hyperbolic decay. Basis for the suspension trigger when capture ratio drops below 40%.
- **McLean & Pontiff (2016).** ~58% of anomaly returns decline post-publication. Confirms popularity → edge decay is a robust finding across asset classes.
- **Akey, Grégoire, Harvie & Martineau — "Who Wins and Who Loses In Prediction Markets?" (SSRN 6443103).** Top 1% of Polymarket users capture 76.5% of trading gains. Basis for tight disqualifier thresholds.
- **Gómez-Cram, Guo, Kung & Jensen — "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?" (SSRN, April 2026, n=1.72M accounts).** Only 3.14% of accounts qualify as "skilled winners." Basis for the 100-trade and 4-month minimums.

### Polymarket-specific operator sources
- **"The Oracle by Polymarket" — COPYCAT episode** (news.polymarket.com/p/copycat). Interview with Stand.trade's Ridgely. Source for: top-10 most-copied wallet breakdown, secondary/tertiary wallet practice, RN1 equity curve description, March 2026 fee change killing crypto bots.
- **"The Oracle" — COPYTRADE WARS** (news.polymarket.com/p/copytrade-wars). Source for: cat-and-mouse description, dormant-account-detection pattern, counter-trading concept.
- **"The Oracle" — Meet Your Market Maker.** Source for: anonymous market makers describing how they avoid copy detection.
- **"The Oracle" — This Tool Finds Polymarket Traders with 96% Win Rates** (Primo interview). Source for: category leaderboard importance, sidelined capital metric.
- **Alex P. ("0xmega") — Medium series** ("How To Find The BEST Polymarket Wallets To Copy Trade", "Best Copy Trading Bots 2026", "How To Copytrade On Polymarket"). Source for: 12.7% profitable rate, <100 monthly trades = likely human, 2–3 topic areas = real specialist signal.
- **LaikaLabs research** (laikalabs.ai/prediction-markets/top-polymarket-traders). Source for: 34.8% margin threshold, position sizing analysis as conviction signal, four-metric framework (62% WR, 55% ROI, -16% MDD, 4 categories, 350 trades).

### Cluster detection and on-chain analysis
- **PolyTrack** (polytrackhq.app). Documented Théo cluster of 11 wallets (Fredi9999, Theo4, PrincessCaro, Michie + 7 others). $9.99/week. Cluster detection is the unique feature.
- **Polysights** (polysights.xyz). 30+ custom metrics including Beta Insider Finder.
- **Apify Polymarket Whale Tracker** (apify.com/jy-labs). ML anomaly detection and whale clustering.

### Copy trading platforms (cross-asset, methodology transfer)
- **ZuluTrade ZuluRank Algorithm** — 15-factor evaluation weighting risk-adjusted returns above absolute performance. Basis for the multi-factor approach and the slippage simulator concept.
- **eToro Popular Investors** — Risk score, follower count, performance history methodology. Standard reference for trader-evaluation transparency.

### Polymarket data infrastructure
- **Polymarket Data API** — `/leaderboard`, `/positions`, `/trades`, `/activity` endpoints (docs.polymarket.com).
- **The Graph Polymarket subgraph** — historical aggregates, post-V2 migration (April 28, 2026).
- **Goldsky Turbo Pipelines** — real-time OrderFilled streaming on V2 CTF Exchange contract `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`.
- **Dune dashboards**: dune.com/rchen8/polymarket, dune.com/filarm/polymarket-activity, dune.com/lifewillbeokay/polymarket-clob-stats, dune.com/no__hive/terminal-1, dune.com/0xmmdreza/polymarket-wallet-tracker.
- **polymarket-apis Python SDK** (pypi.org/project/polymarket-apis) — unified V2 Clob + Gamma + Data + Web3 + WS + GraphQL clients with Pydantic validation.

### Category profitability
- **atomicwallet.io** "Most Profitable Polymarket Categories" — macro/finance is slower-moving and less noisy than politics/sports; basis for category-specific WR floors.
- **polymarkets.co.il** category breakdown — sports = 39% of platform volume, politics = 34%, crypto = highest market count. Basis for prioritizing soccer/politics/weather specialists over crypto.

### What I deliberately didn't use
- **Marketing claims from polycopytrade.space/.net/.pro** — vendor-published ROI ranges are unverified and likely inflated. Used only for shape of default configs, not for thresholds.
- **"Top 10 lists" without sample-size discussion** — Beachboy4's $6.12M one-day windfall is the perfect counter-example. The leaderboard rewards survivors, not skill.