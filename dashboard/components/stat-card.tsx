interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: "green" | "red" | "yellow" | "default";
}

export function StatCard({ label, value, sub, color = "default" }: StatCardProps) {
  const colors = {
    green: "#10b981",
    red: "#ef4444",
    yellow: "#f59e0b",
    default: "#e2e8f0",
  };
  return (
    <div className="card">
      <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: colors[color], fontSize: 24, fontWeight: 700, lineHeight: 1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ color: "#64748b", fontSize: 11, marginTop: 6 }}>{sub}</div>
      )}
    </div>
  );
}
