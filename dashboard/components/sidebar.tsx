"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",            label: "Overview" },
  { href: "/positions",   label: "Positions" },
  { href: "/closed",      label: "Closed" },
  { href: "/leaders",     label: "Leaders" },
  { href: "/analytics",   label: "Analytics" },
  { href: "/logs",        label: "Live Logs" },
  { href: "/settings",    label: "Settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside style={{
      width: 200,
      background: "#0d0d14",
      borderRight: "1px solid #1e2030",
      display: "flex",
      flexDirection: "column",
      padding: "24px 0",
      flexShrink: 0,
    }}>
      <div style={{ padding: "0 20px 24px", color: "#6366f1", fontWeight: 700, fontSize: 15 }}>
        ◈ POLYBOT
      </div>
      {NAV.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          style={{
            display: "block",
            padding: "8px 20px",
            color: path === href ? "#e2e8f0" : "#64748b",
            textDecoration: "none",
            background: path === href ? "#1e2030" : "transparent",
            borderLeft: path === href ? "2px solid #6366f1" : "2px solid transparent",
            fontSize: 13,
            transition: "all 0.15s",
          }}
        >
          {label}
        </Link>
      ))}
    </aside>
  );
}
