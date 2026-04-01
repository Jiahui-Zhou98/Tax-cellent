"use client";

import React from "react";

type Variant = "default" | "success" | "warning" | "danger";

const VARIANT_COLORS: Record<Variant, string> = {
  default: "var(--color-accent)",
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

const VARIANT_BG: Record<Variant, string> = {
  default: "rgba(0,113,227,0.06)",
  success: "rgba(52,199,89,0.06)",
  warning: "rgba(255,159,10,0.06)",
  danger: "rgba(255,59,48,0.06)",
};

export function SectionCard({
  title,
  variant = "default",
  children,
}: {
  title: string;
  variant?: Variant;
  children: React.ReactNode;
}) {
  const color = VARIANT_COLORS[variant];
  const bg = VARIANT_BG[variant];

  return (
    <div className="overflow-hidden rounded-xl" style={{ border: "1px solid var(--color-border)" }}>
      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{
          background: bg,
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ background: color }} />
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color }}>
          {title}
        </span>
      </div>
      <div className="space-y-2 p-3" style={{ background: "var(--color-surface)" }}>
        {children}
      </div>
    </div>
  );
}
