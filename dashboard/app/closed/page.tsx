"use client";

import { useQuery } from "@tanstack/react-query";
import { api, ClosedPosition } from "@/lib/api";

function fmt$(n: number) { return `$${n.toFixed(2)}`; }
function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%`; }
function fmtTs(ts: number) {
  return new Date(ts * 1000).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

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

export default function ClosedPage() {
  const { data } = useQuery({ queryKey: ["closed"], queryFn: api.getClosedPositions });
  const positions = data ?? [];

  const totalPnl = positions.reduce((s: number, p: ClosedPosition) => s + p.realized_pnl_usd, 0);
  const wins = positions.filter((p: ClosedPosition) => p.realized_pnl_usd > 0).length;
  const winRate = positions.length > 0 ? wins / positions.length : 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>Closed Trades</h1>
        <span style={{ background: "#1e2030", color: "#94a3b8", padding: "2px 8px", borderRadius: 4, fontSize: 11 }}>
          {positions.length} trades
        </span>
      </div>

      {positions.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Total P&L", value: fmt$(totalPnl), color: totalPnl >= 0 ? "#10b981" : "#ef4444" },
            { label: "Win Rate", value: fmtPct(winRate), color: "#e2e8f0" },
            { label: "Wins", value: wins, color: "#10b981" },
            { label: "Losses", value: positions.length - wins, color: "#ef4444" },
          ].map(({ label, value, color }) => (
            <div key={label} className="card">
              <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
                {label}
              </div>
              <div style={{ color, fontSize: 22, fontWeight: 700 }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Market", "Outcome", "Side", "Shares", "Avg Entry", "Exit Price", "Cost", "Proceeds", "P&L", "Closed", "Exit Reason"].map(h => (
                  <th key={h} style={header}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={11} style={{ ...cell, textAlign: "center", color: "#64748b", padding: 32 }}>
                    No closed trades yet
                  </td>
                </tr>
              ) : (
                positions.map((p: ClosedPosition, i: number) => {
                  const pnl = p.realized_pnl_usd;
                  const pnlColor = pnl > 0 ? "#10b981" : pnl < 0 ? "#ef4444" : "#94a3b8";
                  const shortId = p.condition_id.slice(0, 8) + "…";

                  return (
                    <tr key={i}
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
                      <td style={cell}>{p.shares.toFixed(4)}</td>
                      <td style={cell}>{fmtPct(p.avg_entry_price)}</td>
                      <td style={cell}>{p.exit_price != null ? fmtPct(p.exit_price) : "—"}</td>
                      <td style={cell}>{fmt$(p.cost_usd)}</td>
                      <td style={cell}>{p.proceeds_usd != null ? fmt$(p.proceeds_usd) : "—"}</td>
                      <td style={{ ...cell, color: pnlColor, fontWeight: 600 }}>
                        {pnl >= 0 ? "+" : ""}{fmt$(pnl)}
                      </td>
                      <td style={{ ...cell, fontSize: 11 }}>{fmtTs(p.closed_at_ts)}</td>
                      <td style={{ ...cell, fontSize: 10, color: "#64748b" }}>{p.exit_reason ?? "—"}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
