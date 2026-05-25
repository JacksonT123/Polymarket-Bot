"use client";

import { useQuery } from "@tanstack/react-query";
import { api, Leader } from "@/lib/api";
import { useState } from "react";

function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%`; }
function fmt$(n: number) { return `$${n.toFixed(0)}`; }
function fmtAddr(addr: string) { return addr.slice(0, 6) + "…" + addr.slice(-4); }

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
  cursor: "pointer",
  userSelect: "none",
};

type SortKey = "rank" | "roi" | "win_rate" | "total_volume_usd" | "active_markets";

export default function LeadersPage() {
  const { data } = useQuery({ queryKey: ["leaders"], queryFn: api.getLeaders, refetchInterval: 30000 });
  const [sort, setSort] = useState<SortKey>("rank");
  const [asc, setAsc] = useState(true);

  const leaders = (data ?? []).slice().sort((a: Leader, b: Leader) => {
    const av = a[sort] ?? 0;
    const bv = b[sort] ?? 0;
    return asc ? (av as number) - (bv as number) : (bv as number) - (av as number);
  });

  function toggleSort(key: SortKey) {
    if (sort === key) setAsc(!asc);
    else { setSort(key); setAsc(key === "rank"); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sort !== k) return <span style={{ color: "#1e2030" }}> ↕</span>;
    return <span style={{ color: "#6366f1" }}> {asc ? "↑" : "↓"}</span>;
  }

  function tierBadge(rank: number) {
    if (rank <= 10) return { label: "A", bg: "#1a1a2e", color: "#6366f1" };
    if (rank <= 20) return { label: "B", bg: "#1a1f2e", color: "#60a5fa" };
    return { label: "C", bg: "#1e2030", color: "#94a3b8" };
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0" }}>Leader Roster</h1>
        <span style={{ background: "#1e2030", color: "#94a3b8", padding: "2px 8px", borderRadius: 4, fontSize: 11 }}>
          {leaders.length} tracked
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Tier A (ranks 1–10)", count: leaders.filter((l: Leader) => l.rank <= 10).length, color: "#6366f1" },
          { label: "Tier B (ranks 11–20)", count: leaders.filter((l: Leader) => l.rank > 10 && l.rank <= 20).length, color: "#60a5fa" },
          { label: "Tier C (ranks 21–30)", count: leaders.filter((l: Leader) => l.rank > 20).length, color: "#94a3b8" },
        ].map(({ label, count, color }) => (
          <div key={label} className="card">
            <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>{label}</div>
            <div style={{ color, fontSize: 24, fontWeight: 700 }}>{count}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={header} onClick={() => toggleSort("rank")}>Rank<SortIcon k="rank" /></th>
                <th style={header}>Tier</th>
                <th style={header}>Address</th>
                <th style={header} onClick={() => toggleSort("roi")}>ROI<SortIcon k="roi" /></th>
                <th style={header} onClick={() => toggleSort("win_rate")}>Win Rate<SortIcon k="win_rate" /></th>
                <th style={header} onClick={() => toggleSort("total_volume_usd")}>Volume<SortIcon k="total_volume_usd" /></th>
                <th style={header} onClick={() => toggleSort("active_markets")}>Active Markets<SortIcon k="active_markets" /></th>
                <th style={header}>Score</th>
                <th style={header}>Status</th>
              </tr>
            </thead>
            <tbody>
              {leaders.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ ...cell, textAlign: "center", color: "#64748b", padding: 32 }}>
                    No leaders loaded — run daily discovery job
                  </td>
                </tr>
              ) : (
                leaders.map((l: Leader) => {
                  const tier = tierBadge(l.rank);
                  return (
                    <tr key={l.proxy_address}
                      onMouseEnter={e => (e.currentTarget.style.background = "#13131f")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ ...cell, color: "#e2e8f0", fontWeight: 700, fontSize: 14 }}>#{l.rank}</td>
                      <td style={cell}>
                        <span style={{ background: tier.bg, color: tier.color, padding: "2px 8px", borderRadius: 3, fontSize: 11, fontWeight: 700 }}>
                          {tier.label}
                        </span>
                      </td>
                      <td style={{ ...cell, fontFamily: "monospace", color: "#e2e8f0" }}>
                        {fmtAddr(l.proxy_address)}
                      </td>
                      <td style={{ ...cell, color: (l.roi ?? 0) >= 0 ? "#10b981" : "#ef4444", fontWeight: 600 }}>
                        {l.roi != null ? (l.roi >= 0 ? "+" : "") + fmtPct(l.roi) : "—"}
                      </td>
                      <td style={cell}>{l.win_rate != null ? fmtPct(l.win_rate) : "—"}</td>
                      <td style={cell}>{l.total_volume_usd != null ? fmt$(l.total_volume_usd) : "—"}</td>
                      <td style={{ ...cell, textAlign: "center" }}>{l.active_markets ?? "—"}</td>
                      <td style={{ ...cell, color: "#6366f1", fontWeight: 600 }}>
                        {l.score != null ? l.score.toFixed(3) : "—"}
                      </td>
                      <td style={cell}>
                        <span style={{
                          background: l.is_active ? "#0f2a1a" : "#1e2030",
                          color: l.is_active ? "#10b981" : "#64748b",
                          padding: "2px 6px", borderRadius: 3, fontSize: 10,
                        }}>
                          {l.is_active ? "ACTIVE" : "STANDBY"}
                        </span>
                      </td>
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
