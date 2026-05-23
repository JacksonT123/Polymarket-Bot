# Polymarket Copy Bot v2.2 — Complete Build Specification

This is the exhaustive spec for the bot. Every behavior, every number, every rule. Built from primary research across working copy operators (Polycopy, Polycopybot, Polycule, Polycop, Stand.trade, PolyTrack), academic studies (Shen et al. on follower-count alpha decay; Akey/Grégoire/Harvie/Martineau SSRN 6443103 on profit concentration; Gómez-Cram et al. April 2026 on skilled trader minority; LBS Alpha Decay paper; McLean & Pontiff on post-publication decay), and Polymarket's own newsletter "The Oracle" (Stand.trade Ridgely interview, Primo interview on category leaderboards). Calibrated to a $100 paper-trading account with a 10-tier ladder up to $100k+.

---

## What This Bot Is

A faithful copy-trading bot for Polymarket. It auto-discovers and ranks specialist wallets through a two-stage funnel, then mirrors their buys with fixed-size positions. It exits when the lead trader exits. It does not invent its own strategy. It does not use percentage stop-losses. It does not try to predict outcomes.

The bot has one job: **see what a qualified lead trader does, do the same thing scaled down, exit when they exit.**

---

## Core Philosophy (Read This First)

Three rules that override everything else:

**Rule 1: Mirror exits, never percentage stops.** A position bought at $0.60 that drifts to $0.48 looks like a 20% loss but might resolve at $1.00. Binary markets oscillate. The lead trader decides when the thesis is dead — not a fixed percentage.

**Rule 2: Pick humans, not bots.** HFT crypto bots dominate Polymarket's 5-minute and 15-minute markets (55–62% of volume). You cannot copy them — by the time you fill, the edge is gone. The auto-rank funnel has to disqualify them at the gate, not score them.

**Rule 3: Minimal filtering at execution.** Working copy bots execute 10–25% of detected signals. The previous version executed 0.5%. The filters were fighting each other because the watchlist was full of uncopyable wallets generating uncopyable signals. v2.1 fixes this upstream — by the time a signal reaches the filter chain, it's already from a wallet worth copying. Execution filters drop to 5.

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

Wallets failing shadow validation stay in shadow another 14 days or get dropped from the pool after 2 failed cycles.

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
| Parameter | Value |
|---|---|
| Fixed trade size | $5 (at $100 bankroll) |
| Max open positions | 10 |
| Max slippage on buy | 10% |
| Max slippage on sell | 15% |
| Thesis-broken override | Close if -40% AND lead inactive 24h+ |
| Hard time stop | 90 days |

### Portfolio-level
| Parameter | Value |
|---|---|
| Max capital deployed | 50% of bankroll ($50 at $100) |
| Reserve | 50% of bankroll always available |
| Max same-day NEW positions | 5 (prevents cascade on one wallet's bad day) |
| Max correlation to single market | 1 position per (market_id, side) — enforced by dedup |

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

# ─── Wallet Funnel ──────────────────────────────────
CANDIDATE_POOL_SIZE         = 200     # Stage A: leaderboard pull
SHADOW_POOL_SIZE            = 20      # Stage D: top 20 after scoring
ACTIVE_POOL_SIZE            = 5       # Stage F: max active wallets
SHADOW_MODE_MIN_DAYS        = 14
SHADOW_MIN_SIMULATED_COPIES = 20
SHADOW_MAX_SINGLE_LOSS_PCT  = 0.15

# ─── Hard Disqualifiers ─────────────────────────────
DQ_MAX_5MIN_CRYPTO_PCT      = 0.30
DQ_MAX_15MIN_CRYPTO_PCT     = 0.30
DQ_MIN_CLOSED_TRADES        = 50
DQ_MIN_MONTHS_ACTIVE        = 4
DQ_MAX_TRADES_PER_DAY       = 50
DQ_MIN_TRADES_PER_DAY       = 0.3
DQ_MAX_SINGLE_MARKET_PNL    = 0.60    # one-shot wonder
DQ_MAX_CATEGORY_DIVERSITY   = 8
DQ_MIN_AVG_HOLD_MINUTES     = 30
DQ_MIN_WIN_RATE             = 0.55

# ─── Scoring Weights ────────────────────────────────
W_LOG_TRADES                = 0.15
W_WIN_RATE                  = 0.20
W_LOG_PROFIT_FACTOR         = 0.15
W_MONTHS_ACTIVE             = 0.10
W_DOMAIN_SCORE              = 0.20
W_HOLDING_TIME              = 0.10
W_ENTROPY                   = -0.05
W_INSIDER_FLAG              = -0.05
W_MAX_DRAWDOWN              = -0.10

# ─── Execution Filters ──────────────────────────────
MIN_LEAD_TRADE_USD          = 5
MIN_MARKET_VOLUME_24H_USD   = 5000
MIN_PRICE                   = 0.05
MAX_PRICE                   = 0.95
MAX_HOURS_TO_RESOLUTION     = 60 * 24    # 60 days
MIN_HOURS_TO_RESOLUTION     = 2

# ─── Order Placement ────────────────────────────────
MAX_BUY_SLIPPAGE_PCT        = 0.10
MAX_SELL_SLIPPAGE_PCT       = 0.15
ORDER_RETRY_PHASES          = 3
ORDER_PHASE_1_TOLERANCE     = 0.00    # FOK at exact price
ORDER_PHASE_2_TOLERANCE     = 0.02    # FOK ±2%
ORDER_PHASE_3_TOLERANCE     = 0.10    # Market with max-slippage

# ─── Exits ──────────────────────────────────────────
EXIT_MODE                   = "mirror_lead"
THESIS_BROKEN_THRESHOLD     = -0.40
THESIS_BROKEN_LEAD_QUIET_H  = 24
HARD_TIME_STOP_DAYS         = 90

# ─── Circuit Breakers ───────────────────────────────
DAILY_LOSS_HALT_PCT         = 0.15
WEEKLY_LOSS_HALT_PCT        = 0.25
PERMANENT_HALT_DRAWDOWN_PCT = 0.40
WALLET_CONSEC_LOSS_LIMIT    = 3

# ─── Polling Intervals ──────────────────────────────
ACTIVITY_POLL_S             = 15
POSITION_PRICE_UPDATE_S     = 30
WALLET_HEALTH_CHECK_S       = 86400      # daily Stage A–D rerun
SHADOW_REVIEW_S             = 86400      # daily promotion check
ACTIVE_REVIEW_S             = 604800     # weekly active-pool review

# ─── Mode ───────────────────────────────────────────
TRADING_MODE                = "PAPER"
```

---

## Database Schema

### `wallets`
```sql
id, address, alias, status, 
  -- status: candidate | disqualified | shadow | active | suspended | dropped
disqualified_reason,
composite_score,
win_rate, closed_trades_count, months_active,
primary_category, category_diversity_count,
avg_holding_minutes, max_drawdown_pct, single_market_pnl_pct,
volume_5min_crypto_pct, volume_15min_crypto_pct,
last_trade_at, shadow_started_at, activated_at, suspended_at,
shadow_copies_count, shadow_pnl_usd,
consecutive_losses_for_bot,
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
- Implement v2.1 spec including full funnel
- Let Stage A–D run for 3 days; observe which wallets land in shadow pool
- Manually inspect the top 20 — do they look like real specialists?
- **Success criteria**: shadow pool contains ≥ 10 wallets that pass eyeball test
- **Failure mode**: shadow pool dominated by Théo-cluster or named bots → tighten hard disqualifiers

### Stage 2: Shadow Validation (Weeks 2–4)
- Let shadow pool run paper trades for 14+ days
- Watch which wallets generate good simulated copy P&L vs bad
- **Success criteria**: ≥ 3 wallets pass shadow promotion criteria
- **Failure mode**: <3 pass → loosen Stage E thresholds OR funnel is rejecting too aggressively

### Stage 3: Active Paper (Weeks 4–8)
- Top 5 promoted wallets become active
- 4 weeks of paper trading with real signal-to-execution measurement
- Daily review: per-wallet P&L, signal-to-exec ratio, slippage vs lead
- **Success criteria**: signal-to-execution ratio 10–25%; bot captures ≥ 60% of unweighted average net return of active leads over 50+ trades
- **Failure mode**: capture <40% → slippage problem or wallet-selection problem (re-check funnel)

### Stage 4: Micro-Live (Weeks 9–12)
- Only proceed if Stage 3 succeeded AND legal question resolved
- $25 real capital, $2 fixed trades
- Validate plumbing, real fees, real slippage
- **Success criteria**: 50+ live trades, technical reliability >95%, measured slippage within ±50% of paper assumptions

### Stage 5: Scale Decision (Week 13+)
| Stage 4 result | Action |
|---|---|
| Net positive, capture ≥80% of leads | Scale to $100, then $500 over 2 months |
| Net flat (±5%) | Stay at $25–$100; study weak spots |
| Net negative | Shelve. Strategy works for paper, not live — likely slippage/latency you can't fix |

**Hard caps regardless of success:**
- Never scale faster than 2× per quarter
- Never run more than 5 active wallets
- Never raise `MAX_TRADE_SIZE_USD` above 10% of bankroll

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

SHADOW POOL: 14 wallets tracking
  - 3 candidates close to promotion (shadow P&L > $0)
  - 2 candidates flagged for drop (shadow P&L < -$10)

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
- **No bypassing shadow mode.** Even hand-picked candidates go through 14-day shadow first.

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

## Quick Reference: v1 → v2.2 Diff

| Component | v1 | v2.1 | v2.2 |
|---|---|---|---|
| Watchlist source | Top 20 by 9-factor score | Funnel: 200 → 20 shadow → 5 active | **Funnel: 200 → 25 shadow → 5 active + bench, with cluster detection** |
| Hard disqualifiers | None | 11 | **13 (added cluster size, ROI floor, tightened thresholds)** |
| Category-specific win rate floors | No | No | **Yes — 56% to 65% depending on category** |
| Scoring factors | 9 | 9 | **13 (added consistency, conviction, counter-trade, crowding penalty)** |
| Cluster detection | No | No | **Yes (PolyTrack integration, $9.99/wk)** |
| Capture ratio measurement | No | Implicit | **Explicit — required ≥ 60% for promotion** |
| Shadow validation period | None | 14 days | **21 days** |
| Counter-trading known losers | No | No | **Yes — inverted score for high-volume losers** |
| Crowding penalty (popularity hurts edge) | No | No | **Yes — academic-backed (Shen et al.)** |
| Re-score cadence | Every 6 hours | Daily | Daily |
| Execution filters | 11 | 5 | 5 (unchanged) |
| Min lead trade size | $100 | $5 | $5 (unchanged) |
| Stop-loss | 20% fixed | None | None (unchanged) |
| Position sizing | Fixed $5–$10 | Fixed $5–$10 | 10-tier ladder $5 → $2,000 (added in v2.1) |
| Bot can copy HFT crypto | Yes | No | No (unchanged) |

---

That's the spec. Auto-ranking is preserved and made smarter: hard disqualifiers at the gate to kill HFT bots and one-shot wonders, composite scoring on the survivors, mandatory shadow-mode validation before any real signal flows. Build to this and the 1,400/7/0 pattern will not repeat.

When you're ready to start coding, say the word — wallet funnel module first, then polling loop, then filter chain, then execution engine.

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