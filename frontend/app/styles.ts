import type React from "react";

export const card: React.CSSProperties = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "12px",
  boxShadow: "0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)",
};

export const shadowSm = "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)";
export const shadowMd = "0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)";
export const shadowLg = "0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06)";
export const shadowActive = "0 0 0 3px rgba(0,113,227,0.15)";

export const inputStyle: React.CSSProperties = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "0.5rem",
  color: "var(--color-text-primary)",
  padding: "0.5rem 0.75rem",
  width: "100%",
  fontSize: "0.875rem",
  // outline is intentionally omitted — focus ring handled by globals.css
};

export const btnPrimary: React.CSSProperties = {
  background: "var(--color-accent)",
  color: "#FFFFFF",
  border: "none",
  borderRadius: "8px",
  padding: "8px 20px",
  fontSize: "0.875rem",
  fontWeight: 500,
  cursor: "pointer",
};

export const btnGhost: React.CSSProperties = {
  background: "transparent",
  color: "var(--color-text-primary)",
  border: "1px solid var(--color-border)",
  borderRadius: "8px",
  padding: "8px 20px",
  fontSize: "0.875rem",
  fontWeight: 500,
  cursor: "pointer",
};
