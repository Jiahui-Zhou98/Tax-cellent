"use client";

import {
  Upload,
  User,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  BarChart2,
  FileText,
  Check,
} from "lucide-react";

const STEPS = [
  { label: "Upload", icon: Upload },
  { label: "Context", icon: User },
  { label: "Review", icon: Search },
  { label: "Validate", icon: ShieldCheck },
  { label: "Settings", icon: SlidersHorizontal },
  { label: "Analysis", icon: BarChart2 },
  { label: "Report", icon: FileText },
];

export function StepSidebar({ current }: { current: number }) {
  return (
    <aside className="step-sidebar" aria-label="Progress steps">
      {STEPS.map(({ label, icon: Icon }, i) => {
        const isCompleted = i < current;
        const isActive = i === current;
        const isPending = i > current;

        const circleStyle: React.CSSProperties = isActive
          ? {
              background: "var(--color-accent)",
              color: "#FFFFFF",
              border: "none",
            }
          : isCompleted
            ? {
                background: "var(--color-success)",
                color: "#FFFFFF",
                border: "none",
              }
            : {
                background: "var(--color-bg)",
                color: "#AEAEB2",
                border: "1px solid var(--color-border)",
              };

        const iconColor = isActive || isCompleted ? "#FFFFFF" : "#AEAEB2";

        return (
          <div key={i} className="step-sidebar-item flex w-full">
            {/* Circle column with thread */}
            <div className="flex flex-shrink-0 flex-col items-center">
              <div
                className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300${isActive ? "animate-step-halo" : ""}`}
                style={circleStyle}
                aria-label={
                  isCompleted
                    ? `Step ${i + 1}: ${label}, completed`
                    : isActive
                      ? `Step ${i + 1}: ${label}, current`
                      : `Step ${i + 1}: ${label}`
                }
                aria-current={isActive ? "step" : undefined}
              >
                {isCompleted ? (
                  <Check size={16} color="#FFFFFF" strokeWidth={2.5} />
                ) : (
                  <Icon size={14} color={iconColor} strokeWidth={1.8} />
                )}
              </div>

              {/* Thread segment — connects to next step */}
              {i < STEPS.length - 1 && (
                <div
                  className="step-sidebar-thread w-px flex-1 transition-colors duration-300"
                  style={{
                    minHeight: 20,
                    background: isCompleted ? "var(--color-success)" : "var(--color-border)",
                  }}
                />
              )}
            </div>

            {/* Label */}
            <div
              className="step-sidebar-label pt-2 pb-1"
              style={{ paddingBottom: i < STEPS.length - 1 ? 20 : 0 }}
            >
              <span
                className="block text-xs font-medium tracking-wide uppercase"
                style={{
                  color: isActive
                    ? "var(--color-accent)"
                    : isCompleted
                      ? "var(--color-success)"
                      : "var(--color-text-secondary)",
                }}
              >
                {label}
              </span>
              {isActive && (
                <span
                  className="mt-0.5 block text-xs"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  Step {i + 1} of {STEPS.length}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </aside>
  );
}
