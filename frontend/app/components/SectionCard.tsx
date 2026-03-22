"use client";

import React from "react";

export function SectionCard({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <div
        className="px-4 py-2.5 flex items-center gap-2"
        style={{ background: "rgba(15,23,42,0.8)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: accent }} />
        <span className="text-xs font-mono tracking-widest uppercase" style={{ color: accent }}>
          {title}
        </span>
      </div>
      <div className="p-3 space-y-2" style={{ background: "rgba(13,20,36,0.5)" }}>
        {children}
      </div>
    </div>
  );
}
