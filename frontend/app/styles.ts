import type React from "react";

export const card: React.CSSProperties = {
  background: "rgba(13,20,36,0.7)",
  border: "1px solid rgba(255,255,255,0.07)",
  backdropFilter: "blur(12px)",
};

export function glowBtn(color = "rgba(59,130,246,0.45)"): React.CSSProperties {
  return { boxShadow: `0 0 22px ${color}` };
}

export const inputStyle: React.CSSProperties = {
  background: "rgba(13,20,36,0.6)",
  border: "1px solid rgba(71,85,105,0.4)",
  borderRadius: "0.5rem",
  color: "#e2e8f0",
  padding: "0.5rem 0.75rem",
  width: "100%",
  fontSize: "0.875rem",
  // outline is intentionally omitted — focus ring handled by globals.css
};
