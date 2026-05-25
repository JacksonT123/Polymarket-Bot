"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { useEffect, useState } from "react";
import { eventBus, WsEvent } from "@/lib/ws";

function fmt$(n: number) { return `$${n.toFixed(2)}`; }
function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%`; }

export default function OverviewPage() {
  const { data, refetch } = useQuery({ queryKey: ["state"], queryFn: api.getState });
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    return eventBus.subscribe((ev: WsEvent) => {
      setLogs((prev) => [`[${new Date(ev.ts * 1000).toISOString()}] ${ev.type}`, ...prev].slice(0, 50));
      refetch();
    });
  }, [refetch]);

  const s = data;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>Overview</h1>
        {s?.kill_switch_triggered && (
          <span style={{ background: "#ef4444", color: "#fff", padding: "2px 8px", borderRadius: 4, fontSize: 11 }}>
            KILL SWITCH ACTIVE
          </span>
        )}
        {s && (
          <span style={{
            background: s.mode === "PAPER" ? "#1e3a5f" : "#1a2e1a",
            color: s.mode === "PAPER" ? "#60a5fa" : "#10b981",
            padding: "2px 8px", borderRadius: 4, fontSize: 11,
          }}>
            {s.mode}
          </span>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        <StatCard label="Equity" value={s ? fmt$(s.equity_usd) : "—"} />
        <StatCard
          label="Realized P&L"
          value={s ? fmt$(s.realized_pnl_usd) : "—"}
          color={s ? (s.realized_pnl_usd >= 0 ? "green" : "red") : "default"}
        />
        <StatCard label="Win Rate" value={s ? fmtPct(s.win_rate) : "—"} />
        <StatCard label="Total Trades" value={s?.total_trades ?? "—"} />
        <StatCard label="Open Positions $" value={s ? fmt$(s.open_positions_usd) : "—"} />
        <StatCard label="Daily Loss" value={s ? fmt$(s.daily_loss_usd) : "—"} color={s && s.daily_loss_usd > 30 ? "red" : "default"} />
        <StatCard label="Fill Rate" value={s ? fmtPct(s.fill_rate) : "—"} />
        <StatCard label="Paper Gate" value={s?.paper_gate_passed ? "PASSED" : "Pending"} color={s?.paper_gate_passed ? "green" : "yellow"} />
      </div>

      <div className="card">
        <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
          Live Event Feed
        </div>
        <div style={{ maxHeight: 320, overflow: "auto", fontSize: 11 }}>
          {logs.length === 0 ? (
            <span style={{ color: "#64748b" }}>Waiting for events…</span>
          ) : (
            logs.map((l, i) => (
              <div key={i} style={{ color: "#94a3b8", borderBottom: "1px solid #1e2030", padding: "3px 0" }}>{l}</div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
