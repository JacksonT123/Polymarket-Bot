-- Polymarket Bot — SQLite Schema
-- WAL mode enabled by db.py on connection open.
-- All timestamps are Unix seconds (INTEGER).
-- Two parallel ledgers: paper_* and live_* — never merged.

-- ── Leader discovery ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leader_candidates (
    proxy_address       TEXT    PRIMARY KEY,
    first_seen_at       INTEGER NOT NULL,
    last_updated_at     INTEGER NOT NULL,
    trades_30d          INTEGER,
    trade_freq          REAL,
    win_rate            REAL,
    realized_pnl_30d    REAL,
    wash_score          REAL,
    score               REAL,
    excluded_reason     TEXT
);

CREATE TABLE IF NOT EXISTS leader_rosters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT    NOT NULL,
    proxy_address   TEXT    NOT NULL,
    rank            INTEGER NOT NULL,
    tier            TEXT    NOT NULL CHECK(tier IN ('active','standby')),
    score           REAL    NOT NULL,
    score_delta     REAL,
    status          TEXT    NOT NULL DEFAULT 'active' CHECK(status IN ('active','cold','paused')),
    cold_since_ts   INTEGER,
    UNIQUE(snapshot_date, proxy_address)
);
CREATE INDEX IF NOT EXISTS idx_roster_date  ON leader_rosters(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_roster_proxy ON leader_rosters(proxy_address);

CREATE TABLE IF NOT EXISTS cluster_graph (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_eoa        TEXT    NOT NULL,
    to_eoa          TEXT    NOT NULL,
    amount_usdc     REAL    NOT NULL,
    hop_ts          INTEGER NOT NULL,
    discovered_at   INTEGER NOT NULL
);

-- ── Event log + outbox (for WS fanout) ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    trace_id    TEXT,
    event_name  TEXT    NOT NULL,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);

CREATE TABLE IF NOT EXISTS events_outbox (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,
    payload     TEXT,
    created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_outbox_id ON events_outbox(id);

-- ── Leader signals ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS leader_signals (
    id              TEXT    PRIMARY KEY,  -- UUID from SignalEvent.id
    detected_at     INTEGER NOT NULL,
    leader_proxy    TEXT    NOT NULL,
    leader_rank     INTEGER,
    condition_id    TEXT    NOT NULL,
    token_id        TEXT    NOT NULL,
    outcome         TEXT    NOT NULL,
    side            TEXT    NOT NULL CHECK(side IN ('BUY','SELL')),
    leader_price    REAL    NOT NULL,
    leader_size     REAL    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','executed','skipped','aggregated'))
);
CREATE INDEX IF NOT EXISTS idx_signals_leader ON leader_signals(leader_proxy);
CREATE INDEX IF NOT EXISTS idx_signals_market ON leader_signals(condition_id);
CREATE INDEX IF NOT EXISTS idx_signals_ts     ON leader_signals(detected_at);

-- ── Paper ledger ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS paper_trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id     TEXT    NOT NULL UNIQUE,
    created_at          INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    condition_id        TEXT    NOT NULL,
    token_id            TEXT    NOT NULL,
    outcome             TEXT    NOT NULL,
    side                TEXT    NOT NULL,
    limit_price         REAL    NOT NULL,
    size_shares         REAL    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'PENDING'
                            CHECK(status IN ('PENDING','SUBMITTED','FILLED','REJECTED','EXPIRED'))
);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_ts     ON paper_trades(created_at);

CREATE TABLE IF NOT EXISTS paper_fills (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id     TEXT    NOT NULL UNIQUE,
    exchange_order_id   TEXT,
    status              TEXT    NOT NULL,
    filled_shares       REAL    NOT NULL DEFAULT 0,
    avg_price           REAL    NOT NULL DEFAULT 0,
    fee_usd             REAL    NOT NULL DEFAULT 0,
    filled_at_ts        INTEGER,
    reject_reason       TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_fills_ts ON paper_fills(filled_at_ts);

CREATE TABLE IF NOT EXISTS paper_positions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id        TEXT    NOT NULL,
    token_id            TEXT    NOT NULL,
    outcome             TEXT    NOT NULL,
    side                TEXT    NOT NULL DEFAULT 'BUY',
    shares              REAL    NOT NULL,
    cost_usd            REAL    NOT NULL,
    avg_entry_price     REAL    NOT NULL,
    exit_price          REAL,
    proceeds_usd        REAL,
    opened_at_ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    closed_at_ts        INTEGER,
    is_open             INTEGER NOT NULL DEFAULT 1,
    realized_pnl        REAL,
    exit_reason         TEXT,
    signal_ids_json     TEXT,
    leader_ranks_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_paper_pos_open   ON paper_positions(is_open);
CREATE INDEX IF NOT EXISTS idx_paper_pos_market ON paper_positions(condition_id);

-- ── Live ledger (mirrors paper schema) ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS live_trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id     TEXT    NOT NULL UNIQUE,
    created_at          INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    condition_id        TEXT    NOT NULL,
    token_id            TEXT    NOT NULL,
    outcome             TEXT    NOT NULL,
    side                TEXT    NOT NULL,
    limit_price         REAL    NOT NULL,
    size_shares         REAL    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'PENDING'
                            CHECK(status IN ('PENDING','SUBMITTED','FILLED','REJECTED','EXPIRED'))
);
CREATE INDEX IF NOT EXISTS idx_live_trades_status ON live_trades(status);
CREATE INDEX IF NOT EXISTS idx_live_trades_ts     ON live_trades(created_at);

CREATE TABLE IF NOT EXISTS live_fills (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id     TEXT    NOT NULL UNIQUE,
    exchange_order_id   TEXT,
    status              TEXT    NOT NULL,
    filled_shares       REAL    NOT NULL DEFAULT 0,
    avg_price           REAL    NOT NULL DEFAULT 0,
    fee_usd             REAL    NOT NULL DEFAULT 0,
    filled_at_ts        INTEGER,
    reject_reason       TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_fills_ts ON live_fills(filled_at_ts);

CREATE TABLE IF NOT EXISTS live_positions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id        TEXT    NOT NULL,
    token_id            TEXT    NOT NULL,
    outcome             TEXT    NOT NULL,
    side                TEXT    NOT NULL DEFAULT 'BUY',
    shares              REAL    NOT NULL,
    cost_usd            REAL    NOT NULL,
    avg_entry_price     REAL    NOT NULL,
    exit_price          REAL,
    proceeds_usd        REAL,
    opened_at_ts        INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    closed_at_ts        INTEGER,
    is_open             INTEGER NOT NULL DEFAULT 1,
    realized_pnl        REAL,
    exit_reason         TEXT,
    signal_ids_json     TEXT,
    leader_ranks_json   TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_pos_open   ON live_positions(is_open);
CREATE INDEX IF NOT EXISTS idx_live_pos_market ON live_positions(condition_id);

-- ── Equity snapshots ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    mode            TEXT    NOT NULL,
    total_equity    REAL    NOT NULL,
    cash_balance    REAL    NOT NULL,
    position_value  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_equity_mode_ts ON equity_snapshots(mode, ts);

-- ── Bot control ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bot_settings (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS kill_switch (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    triggered           INTEGER NOT NULL DEFAULT 0,
    triggered_at        INTEGER,
    reason              TEXT,
    daily_loss_usd      REAL    NOT NULL DEFAULT 0,
    daily_loss_limit_usd REAL   NOT NULL DEFAULT 40
);
INSERT OR IGNORE INTO kill_switch(id) VALUES(1);

CREATE TABLE IF NOT EXISTS bot_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  INTEGER NOT NULL,
    stopped_at  INTEGER,
    mode        TEXT    NOT NULL,
    start_equity REAL,
    stop_equity  REAL
);
