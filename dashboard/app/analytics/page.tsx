"use client";

import { useQuery } from "@tanstack/react-query";
import { api, EquityPoint, ClosedPosition } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

function fmt$(n: number) { return `$${n.toFixed(2)}`; }
function fmtPct(n: number) { return `${(n * 100).toFixed(1)}%`; }

function useEquityChart(canvasRef: React.RefObject<HTMLCanvasElement | null>, data: EquityPoint[]) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;
    const PAD = { top: 20, right: 20, bottom: 32, left: 64 };

    ctx.clearRect(0, 0, W, H);

    const vals = data.map(d => d.equity_usd);
    const minV = Math.min(...vals) * 0.99;
    const maxV = Math.max(...vals) * 1.01;
    const minT = data[0].ts;
    const maxT = data[data.length - 1].ts;

    function xOf(ts: number) {
      return PAD.left + ((ts - minT) / (maxT - minT || 1)) * (W - PAD.left - PAD.right);
    }
    function yOf(v: number) {
      return PAD.top + (1 - (v - minV) / (maxV - minV || 1)) * (H - PAD.top - PAD.bottom);
    }

    // Grid lines
    ctx.strokeStyle = "#1e2030";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = PAD.top + (i / 4) * (H - PAD.top - PAD.bottom);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(W - PAD.right, y);
      ctx.stroke();
      const v = maxV - (i / 4) * (maxV - minV);
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "right";
      ctx.fillText(fmt$(v), PAD.left - 8, y + 4);
    }

    // Gradient fill
    const grad = ctx.createLinearGradient(0, PAD.top, 0, H - PAD.bottom);
    grad.addColorStop(0, "rgba(99,102,241,0.25)");
    grad.addColorStop(1, "rgba(99,102,241,0.0)");

    ctx.beginPath();
    ctx.moveTo(xOf(data[0].ts), yOf(data[0].equity_usd));
    data.forEach(d => ctx.lineTo(xOf(d.ts), yOf(d.equity_usd)));
    ctx.lineTo(xOf(data[data.length - 1].ts), H - PAD.bottom);
    ctx.lineTo(xOf(data[0].ts), H - PAD.bottom);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.moveTo(xOf(data[0].ts), yOf(data[0].equity_usd));
    data.forEach(d => ctx.lineTo(xOf(d.ts), yOf(d.equity_usd)));
    ctx.stroke();

    // Latest dot
    const last = data[data.length - 1];
    ctx.beginPath();
    ctx.arc(xOf(last.ts), yOf(last.equity_usd), 4, 0, Math.PI * 2);
    ctx.fillStyle = "#6366f1";
    ctx.fill();

  }, [data, canvasRef]);
}

export default function AnalyticsPage() {
  const { data: equity } = useQuery({ queryKey: ["equity"], queryFn: api.getEquityCurve, refetchInterval: 10000 });
  const { data: closed } = useQuery({ queryKey: ["closed"], queryFn: api.getClosedPositions });
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEquityChart(canvasRef, equity ?? []);

  const trades = closed ?? [];
  const totalPnl = trades.reduce((s: number, p: ClosedPosition) => s + p.realized_pnl_usd, 0);
  const wins = trades.filter((p: ClosedPosition) => p.realized_pnl_usd > 0);
  const losses = trades.filter((p: ClosedPosition) => p.realized_pnl_usd <= 0);
  const avgWin = wins.length > 0 ? wins.reduce((s, p) => s + p.realized_pnl_usd, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? losses.reduce((s, p) => s + p.realized_pnl_usd, 0) / losses.length : 0;
  const profitFactor = avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;
  const winRate = trades.length > 0 ? wins.length / trades.length : 0;

  // P&L distribution buckets
  const buckets = [
    { label: "<-$5", count: trades.filter(p => p.realized_pnl_usd < -5).length, color: "#ef4444" },
    { label: "-$5 to $0", count: trades.filter(p => p.realized_pnl_usd >= -5 && p.realized_pnl_usd < 0).length, color: "#f97316" },
    { label: "$0 to $2", count: trades.filter(p => p.realized_pnl_usd >= 0 && p.realized_pnl_usd < 2).length, color: "#84cc16" },
    { label: "$2 to $5", count: trades.filter(p => p.realized_pnl_usd >= 2 && p.realized_pnl_usd < 5).length, color: "#10b981" },
    { label: ">$5", count: trades.filter(p => p.realized_pnl_usd >= 5).length, color: "#6366f1" },
  ];
  const maxBucket = Math.max(...buckets.map(b => b.count), 1);

  return (
    <div>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0", marginBottom: 24 }}>Analytics</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Total P&L", value: fmt$(totalPnl), color: totalPnl >= 0 ? "#10b981" : "#ef4444" },
          { label: "Win Rate", value: fmtPct(winRate), color: "#e2e8f0" },
          { label: "Profit Factor", value: profitFactor.toFixed(2), color: profitFactor >= 1.5 ? "#10b981" : profitFactor >= 1 ? "#f59e0b" : "#ef4444" },
          { label: "Avg Win / Avg Loss", value: `${fmt$(avgWin)} / ${fmt$(avgLoss)}`, color: "#e2e8f0" },
        ].map(({ label, value, color }) => (
          <div key={label} className="card">
            <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>{label}</div>
            <div style={{ color, fontSize: 18, fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Equity Curve */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16 }}>
          Equity Curve
        </div>
        {(equity ?? []).length < 2 ? (
          <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: 12 }}>
            Collecting equity snapshots…
          </div>
        ) : (
          <canvas ref={canvasRef} style={{ width: "100%", height: 220, display: "block" }} />
        )}
      </div>

      {/* P&L Distribution */}
      <div className="card">
        <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16 }}>
          P&L Distribution
        </div>
        {trades.length === 0 ? (
          <div style={{ color: "#64748b", fontSize: 12 }}>No closed trades yet</div>
        ) : (
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", height: 120 }}>
            {buckets.map(({ label, count, color }) => (
              <div key={label} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <div style={{ fontSize: 11, color: "#94a3b8" }}>{count}</div>
                <div style={{
                  width: "100%",
                  height: Math.max(4, (count / maxBucket) * 80),
                  background: color,
                  borderRadius: "3px 3px 0 0",
                  opacity: 0.85,
                  transition: "height 0.3s",
                }} />
                <div style={{ fontSize: 10, color: "#64748b", whiteSpace: "nowrap" }}>{label}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
