"use client";

import { useQuery } from "@tanstack/react-query";
import { api, Position } from "@/lib/api";
import { useEffect } from "react";
import { eventBus, WsEvent } from "@/lib/ws";

function fmt$(n: number) { return `$${n.toFixed(2)}`; }
function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%`; }
function fmtShares(n: number) { return n.toFixed(4); }

const cell: React.CSSProperties = {
  padding: "10px 12px",
  borderBottom: "1px solid #1e2030",
  fontSize: 12,
  color: "#94a3b8",
  whiteSpace: "nowrap",
};

const header: React.CSSProperties = {
  padding: "8px 12px",
  fontSize: 11,
  color: "#64748b",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  borderBottom: "1px solid #1e2030",
  background: "#0d0d14",
};

export default function PositionsPage() {
  const { data, refetch } = useQuery({ queryKey: ["positions"], queryFn: api.getPositions });

  useEffect(() => {
    return eventBus.subscribe((_ev: WsEvent) => { refetch(); });
  }, [refetch]);

  const positions = data ?? [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>Open Positions</h1>
        <span style={{ background: "#1e2030", color: "#94a3b8", padding: "2px 8px", borderRadius: 4, fontSize: 11 }}>
          {positions.length} open
        </span>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Market", "Outcome", "Side", "Shares", "Avg Entry", "Current", "Cost", "Value", "Unreal P&L", "Leaders", "Age"].map(h => (
                  <th key={h} style={header}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={11} style={{ ...cell, textAlign: "center", color: "#64748b", padding: 32 }}>
                    No open positions
                  </td>
                </tr>
              ) : (
                positions.map((p: Position) => {
                  const unrealized = p.unrealized_pnl_usd ?? 0;
                  const pnlColor = unrealized > 0 ? "#10b981" : unrealized < 0 ? "#ef4444" : "#94a3b8";
                  const ageMs = Date.now() - p.opened_at_ts * 1000;
                  const ageH = Math.floor(ageMs / 3600000);
                  const ageLabel = ageH < 24 ? `${ageH}h` : `${Math.floor(ageH / 24)}d`;
                  const shortId = p.condition_id.slice(0, 8) + "…";

                  return (
                    <tr key={p.condition_id + p.outcome} style={{ transition: "background 0.1s" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "#13131f")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ ...cell, color: "#e2e8f0", fontFamily: "monospace" }}>{shortId}</td>
                      <td style={{ ...cell, color: "#e2e8f0" }}>{p.outcome}</td>
                      <td style={{ ...cell }}>
                        <span style={{
                          background: p.side === "BUY" ? "#0f2a1a" : "#2a0f0f",
                          color: p.side === "BUY" ? "#10b981" : "#ef4444",
                          padding: "2px 6px", borderRadius: 3, fontSize: 10, fontWeight: 700,
                        }}>
                          {p.side}
                        </span>
                      </td>
                      <td style={cell}>{fmtShares(p.shares)}</td>
                      <td style={cell}>{fmtPct(p.avg_entry_price)}</td>
                      <td style={cell}>{p.current_price != null ? fmtPct(p.current_price) : "—"}</td>
                      <td style={cell}>{fmt$(p.cost_usd)}</td>
                      <td style={cell}>{p.current_value_usd != null ? fmt$(p.current_value_usd) : "—"}</td>
                      <td style={{ ...cell, color: pnlColor, fontWeight: 600 }}>
                        {p.unrealized_pnl_usd != null ? fmt$(p.unrealized_pnl_usd) : "—"}
                      </td>
                      <td style={{ ...cell, fontFamily: "monospace", fontSize: 10 }}>
                        {p.leader_ranks?.join(", ") ?? "—"}
                      </td>
                      <td style={cell}>{ageLabel}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {positions.length > 0 && (
        <div style={{ display: "flex", gap: 24, marginTop: 16 }}>
          <div style={{ color: "#64748b", fontSize: 11 }}>
            Total cost:{" "}
            <span style={{ color: "#e2e8f0" }}>
              {fmt$(positions.reduce((s, p) => s + p.cost_usd, 0))}
            </span>
          </div>
          <div style={{ color: "#64748b", fontSize: 11 }}>
            Total unrealized P&L:{" "}
            <span style={{
              color: positions.reduce((s, p) => s + (p.unrealized_pnl_usd ?? 0), 0) >= 0 ? "#10b981" : "#ef4444"
            }}>
              {fmt$(positions.reduce((s, p) => s + (p.unrealized_pnl_usd ?? 0), 0))}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
