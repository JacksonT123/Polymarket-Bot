const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8787";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export const api = {
  getState:            () => get<BotState>("/api/state"),
  getPositions:        () => get<Position[]>("/api/positions/open"),
  getClosedPositions:  () => get<ClosedPosition[]>("/api/positions/closed"),
  getEquityCurve:      () => get<EquityPoint[]>("/api/positions/pnl"),
  getLeaders:          () => get<Leader[]>("/api/leaders"),
  getLeader:           (proxy: string) => get<LeaderDetail>(`/api/leaders/${proxy}`),
  getSettings:         () => get<BotSettings>("/api/settings"),
  postSettings:        (body: Partial<BotSettings>) => post<BotSettings>("/api/settings", body),
  getKillSwitch:       () => get<KillSwitchState>("/api/kill-switch"),
  postKillSwitch:      (active: boolean) =>
    post<KillSwitchState>("/api/kill-switch", active
      ? { action: "trigger", reason: "manual" }
      : { action: "reset" }),
};

export interface BotState {
  mode: string;
  kill_switch_triggered: boolean;
  kill_switch_reason: string | null;
  equity_usd: number;
  cash_usd: number;
  open_positions_usd: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  total_trades: number;
  win_rate: number;
  paper_gate_passed: boolean;
  daily_loss_usd: number;
  fill_rate: number;
}

export interface Position {
  condition_id: string;
  token_id: string;
  outcome: string;
  side: string;
  shares: number;
  cost_usd: number;
  avg_entry_price: number;
  current_price: number | null;
  current_value_usd: number | null;
  unrealized_pnl_usd: number | null;
  opened_at_ts: number;
  leader_ranks: number[] | null;
}

export interface ClosedPosition {
  condition_id: string;
  token_id: string;
  outcome: string;
  side: string;
  shares: number;
  cost_usd: number;
  avg_entry_price: number;
  exit_price: number | null;
  proceeds_usd: number | null;
  realized_pnl_usd: number;
  closed_at_ts: number;
  exit_reason: string | null;
}

export interface EquityPoint {
  ts: number;
  equity_usd: number;
  cash_usd: number;
  positions_usd: number;
}

export interface Leader {
  proxy_address: string;
  rank: number;
  score: number | null;
  roi: number | null;
  win_rate: number | null;
  total_volume_usd: number | null;
  active_markets: number | null;
  is_active: boolean;
}

export interface LeaderDetail {
  leader: Leader;
  recent_signals: Signal[];
}

export interface Signal {
  id: string;
  detected_at: number;
  condition_id: string;
  side: string;
  leader_price: number;
  leader_size: number;
  status: string;
}

export interface BotSettings {
  mode: string;
  base_trade_usd: number;
  max_position_pct: number;
  kill_switch_daily_loss_usd: number;
  aggregation_window_secs: number;
  max_position_age_hours: number;
  stop_loss_enabled: boolean;
}

export interface KillSwitchState {
  active: boolean;
  triggered_at: number | null;
  reason: string | null;
}
