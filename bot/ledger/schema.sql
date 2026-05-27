CREATE TABLE IF NOT EXISTS leaders (
  proxy TEXT PRIMARY KEY,
  rank INTEGER NOT NULL,
  score REAL NOT NULL,
  pnl_30d REAL NOT NULL DEFAULT 0,
  win_rate REAL NOT NULL DEFAULT 0,
  trade_count_30d INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  cluster_id TEXT,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_bankroll_cache (
  proxy TEXT PRIMARY KEY,
  bankroll_usd REAL NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_events (
  event_id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
  condition_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  outcome TEXT NOT NULL DEFAULT '',
  shares REAL NOT NULL,
  avg_price REAL NOT NULL,
  leader_proxy TEXT,
  redeemable INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (condition_id, token_id)
);

CREATE TABLE IF NOT EXISTS account_state (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  cash_usd REAL NOT NULL,
  equity_usd REAL NOT NULL,
  starting_equity_usd REAL NOT NULL DEFAULT 100,
  daily_pnl_usd REAL NOT NULL DEFAULT 0,
  kill_switch_triggered INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  stage TEXT NOT NULL,
  code TEXT NOT NULL,
  event_id TEXT,
  leader_proxy TEXT,
  condition_id TEXT,
  details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  candidates INTEGER NOT NULL,
  passed INTEGER NOT NULL,
  active INTEGER NOT NULL,
  standby INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  event_id TEXT,
  leader_proxy TEXT,
  condition_id TEXT,
  side TEXT NOT NULL,
  shares REAL NOT NULL,
  price REAL NOT NULL,
  notional REAL NOT NULL,
  mode TEXT NOT NULL,
  exchange_order_id TEXT
);

CREATE TABLE IF NOT EXISTS leader_pnl (
  leader_proxy TEXT PRIMARY KEY,
  realized_pnl REAL NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_cursors (
  proxy TEXT PRIMARY KEY,
  last_event_ts INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
