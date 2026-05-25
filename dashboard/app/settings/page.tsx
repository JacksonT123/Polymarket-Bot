"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, BotSettings } from "@/lib/api";
import { useState, useEffect } from "react";

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <label style={{ display: "block", color: "#94a3b8", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
        {label}
      </label>
      {children}
      {hint && <div style={{ color: "#334155", fontSize: 10, marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "#0d0d14",
  border: "1px solid #1e2030",
  borderRadius: 4,
  color: "#e2e8f0",
  padding: "6px 10px",
  fontSize: 12,
  width: "100%",
  outline: "none",
  fontFamily: "monospace",
};

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const { data: state } = useQuery({ queryKey: ["state"], queryFn: api.getState });
  const { data: ks } = useQuery({ queryKey: ["kill-switch"], queryFn: api.getKillSwitch });

  const [form, setForm] = useState<Partial<BotSettings>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (s: Partial<BotSettings>) => api.postSettings(s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const ksMutation = useMutation({
    mutationFn: (active: boolean) => api.postKillSwitch(active),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["kill-switch"] });
      qc.invalidateQueries({ queryKey: ["state"] });
    },
  });

  function set(k: keyof BotSettings, v: string | number | boolean) {
    setForm(f => ({ ...f, [k]: v }));
  }

  const isLive = state?.mode === "LIVE";
  const ksActive = ks?.active ?? state?.kill_switch_triggered ?? false;

  return (
    <div>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0", marginBottom: 24 }}>Settings</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
        {/* Trading config */}
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 20 }}>
              Trading Parameters
            </div>

            <Field label="Mode" hint="Switch to LIVE only after paper gate passes">
              <select
                value={form.mode ?? "PAPER"}
                onChange={e => set("mode", e.target.value)}
                style={{ ...inputStyle, width: "auto" }}
              >
                <option value="PAPER">PAPER</option>
                <option value="LIVE">LIVE</option>
              </select>
            </Field>

            <Field label="Base Trade Size (USD)" hint="Fixed dollar per trade before rank multiplier">
              <input
                type="number"
                min={1}
                max={100}
                step={0.5}
                value={form.base_trade_usd ?? 5}
                onChange={e => set("base_trade_usd", parseFloat(e.target.value))}
                style={inputStyle}
              />
            </Field>

            <Field label="Max Position Size (% of bankroll)" hint="Hard cap per open position">
              <input
                type="number"
                min={1}
                max={25}
                step={0.5}
                value={form.max_position_pct != null ? form.max_position_pct * 100 : 10}
                onChange={e => set("max_position_pct", parseFloat(e.target.value) / 100)}
                style={inputStyle}
              />
            </Field>

            <Field label="Kill Switch Daily Loss (USD)" hint="Auto-halt when daily loss exceeds this">
              <input
                type="number"
                min={10}
                max={500}
                step={5}
                value={form.kill_switch_daily_loss_usd ?? 40}
                onChange={e => set("kill_switch_daily_loss_usd", parseFloat(e.target.value))}
                style={inputStyle}
              />
            </Field>

            <Field label="Aggregation Window (seconds)" hint="How long to buffer signals before placing order">
              <input
                type="number"
                min={10}
                max={300}
                step={10}
                value={form.aggregation_window_secs ?? 120}
                onChange={e => set("aggregation_window_secs", parseInt(e.target.value))}
                style={inputStyle}
              />
            </Field>

            <Field label="Max Position Age (hours)" hint="Auto-close positions older than this">
              <input
                type="number"
                min={1}
                max={720}
                step={1}
                value={form.max_position_age_hours ?? 168}
                onChange={e => set("max_position_age_hours", parseInt(e.target.value))}
                style={inputStyle}
              />
            </Field>

            <Field label="Stop Loss Enabled">
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={form.stop_loss_enabled ?? false}
                  onChange={e => set("stop_loss_enabled", e.target.checked)}
                  style={{ accentColor: "#6366f1", width: 16, height: 16 }}
                />
                <span style={{ color: "#94a3b8", fontSize: 12 }}>
                  {form.stop_loss_enabled ? "Enabled" : "Disabled (mirror-exit model)"}
                </span>
              </label>
            </Field>

            <button
              onClick={() => saveMutation.mutate(form)}
              disabled={saveMutation.isPending}
              style={{
                background: saved ? "#0f2a1a" : "#1a1a2e",
                border: `1px solid ${saved ? "#10b981" : "#6366f1"}`,
                color: saved ? "#10b981" : "#6366f1",
                borderRadius: 4, padding: "8px 20px", fontSize: 12,
                cursor: saveMutation.isPending ? "not-allowed" : "pointer",
                fontWeight: 600, transition: "all 0.2s",
              }}
            >
              {saveMutation.isPending ? "Saving…" : saved ? "✓ Saved" : "Save Settings"}
            </button>
          </div>
        </div>

        {/* Kill switch + status */}
        <div>
          <div className="card" style={{ marginBottom: 16, borderColor: ksActive ? "#ef4444" : "#1e2030" }}>
            <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16 }}>
              Kill Switch
            </div>

            <div style={{
              background: ksActive ? "#2a0f0f" : "#0f2a1a",
              border: `1px solid ${ksActive ? "#ef4444" : "#10b981"}`,
              borderRadius: 6, padding: "12px 16px", marginBottom: 16,
              display: "flex", alignItems: "center", gap: 12,
            }}>
              <div style={{
                width: 10, height: 10, borderRadius: "50%",
                background: ksActive ? "#ef4444" : "#10b981",
                boxShadow: `0 0 8px ${ksActive ? "#ef4444" : "#10b981"}`,
              }} />
              <span style={{ color: ksActive ? "#ef4444" : "#10b981", fontWeight: 700, fontSize: 13 }}>
                {ksActive ? "KILL SWITCH ACTIVE — Trading halted" : "Trading active"}
              </span>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                onClick={() => ksMutation.mutate(true)}
                disabled={ksActive || ksMutation.isPending}
                style={{
                  flex: 1, background: "#2a0f0f", border: "1px solid #ef4444",
                  color: "#ef4444", borderRadius: 4, padding: "8px", fontSize: 12,
                  cursor: ksActive ? "not-allowed" : "pointer", fontWeight: 600,
                  opacity: ksActive ? 0.5 : 1,
                }}
              >
                Trigger Kill Switch
              </button>
              <button
                onClick={() => ksMutation.mutate(false)}
                disabled={!ksActive || ksMutation.isPending}
                style={{
                  flex: 1, background: "#0f2a1a", border: "1px solid #10b981",
                  color: "#10b981", borderRadius: 4, padding: "8px", fontSize: 12,
                  cursor: !ksActive ? "not-allowed" : "pointer", fontWeight: 600,
                  opacity: !ksActive ? 0.5 : 1,
                }}
              >
                Reset Kill Switch
              </button>
            </div>
          </div>

          <div className="card">
            <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16 }}>
              Bot Status
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[
                { label: "Mode", value: state?.mode ?? "—", color: isLive ? "#10b981" : "#60a5fa" },
                { label: "Equity", value: state ? `$${state.equity_usd.toFixed(2)}` : "—", color: "#e2e8f0" },
                { label: "Paper Gate", value: state?.paper_gate_passed ? "PASSED" : "Pending", color: state?.paper_gate_passed ? "#10b981" : "#f59e0b" },
                { label: "Total Trades", value: state?.total_trades ?? "—", color: "#e2e8f0" },
                { label: "Daily Loss", value: state ? `$${state.daily_loss_usd.toFixed(2)}` : "—", color: (state?.daily_loss_usd ?? 0) > 30 ? "#ef4444" : "#94a3b8" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: "#64748b", fontSize: 12 }}>{label}</span>
                  <span style={{ color, fontSize: 12, fontWeight: 600, fontFamily: "monospace" }}>{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
