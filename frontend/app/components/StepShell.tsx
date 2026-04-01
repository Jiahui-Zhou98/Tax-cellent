"use client";

import { type ReactNode } from "react";
import { shadowMd } from "../styles";

const STEP_LABELS = ["Upload", "Context", "Review", "Validate", "Settings", "Analysis", "Report"];

interface StepShellProps {
  children: ReactNode;
  step: number;        // 0-indexed
  onBack?: () => void; // omit → no Previous button
  onNext?: () => void; // omit → no Next button
  nextLabel?: string;  // defaults to "Continue"
  loading?: boolean;   // true → Next button disabled
}

export function StepShell({
  children,
  step,
  onBack,
  onNext,
  nextLabel = "Continue",
  loading = false,
}: StepShellProps) {
  const label = STEP_LABELS[step] ?? "";
  const total = STEP_LABELS.length;
  const progressPct = ((step + 1) / total) * 100;

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col"
      style={{
        background: "var(--color-surface)",
        boxShadow: shadowMd,
        border: "1px solid var(--color-border)",
      }}
    >
      {/* Progress header */}
      <div
        className="px-6 pt-5 pb-4"
        style={{ borderBottom: "1px solid var(--color-border)" }}
      >
        <div className="flex items-center justify-between mb-2">
          <span
            className="text-xs font-medium uppercase tracking-wide"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {label}
          </span>
          <span
            className="text-xs font-medium"
            style={{ color: "var(--color-text-secondary)" }}
          >
            {step + 1} of {total}
          </span>
        </div>
        {/* Progress track */}
        <div
          className="h-0.5 w-full rounded-full"
          style={{ background: "var(--color-border)" }}
        >
          <div
            className="h-0.5 rounded-full transition-all duration-500"
            style={{
              width: `${progressPct}%`,
              background: "var(--color-accent)",
            }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-6 flex-1">
        {children}
      </div>

      {/* Nav footer — only if at least one button is present */}
      {(onBack || onNext) && (
        <div
          className="px-6 py-4 flex items-center justify-end gap-3"
          style={{ borderTop: "1px solid var(--color-border)" }}
        >
          {onBack && (
            <button
              onClick={onBack}
              disabled={loading}
              className="transition-colors disabled:opacity-40"
              style={{
                background: "transparent",
                color: "var(--color-text-primary)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                padding: "8px 20px",
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              Previous
            </button>
          )}
          {/* Separator between buttons */}
          {onBack && onNext && (
            <div
              className="h-5 w-px"
              style={{ background: "var(--color-border)" }}
            />
          )}
          {onNext && (
            <button
              onClick={onNext}
              disabled={loading}
              className="transition-opacity disabled:opacity-40"
              style={{
                background: loading ? "#AEAEB2" : "var(--color-accent)",
                color: "#FFFFFF",
                border: "none",
                borderRadius: "8px",
                padding: "8px 20px",
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: loading ? "not-allowed" : "pointer",
              }}
              onMouseEnter={(e) => {
                if (!loading) (e.currentTarget as HTMLButtonElement).style.background = "var(--color-accent-hover)";
              }}
              onMouseLeave={(e) => {
                if (!loading) (e.currentTarget as HTMLButtonElement).style.background = "var(--color-accent)";
              }}
            >
              {loading ? "Loading…" : nextLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
