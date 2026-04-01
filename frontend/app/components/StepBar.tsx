"use client";

const STEPS = ["Upload", "Context", "Review", "Validate", "Settings", "Analysis", "Report"];

export function StepBar({ current }: { current: number }) {
  return (
    <nav aria-label="Progress steps" className="mb-12 flex items-start">
      {STEPS.map((label, i) => (
        <div key={i} className="flex flex-1 items-start last:flex-none">
          <div className="flex flex-col items-center gap-2">
            {/* Circle */}
            <div
              className="flex h-9 w-9 items-center justify-center rounded-full border font-mono text-xs font-bold transition-all duration-300"
              aria-label={
                i < current
                  ? `Step ${i + 1}: ${label}, completed`
                  : i === current
                    ? `Step ${i + 1}: ${label}, current`
                    : `Step ${i + 1}: ${label}`
              }
              aria-current={i === current ? "step" : undefined}
              style={
                i === current
                  ? {
                      background: "#22d3ee",
                      borderColor: "#67e8f9",
                      color: "#060b14",
                      boxShadow: "0 0 20px rgba(34,211,238,0.55)",
                    }
                  : i < current
                    ? {
                        background: "rgba(34,211,238,0.1)",
                        borderColor: "rgba(34,211,238,0.5)",
                        color: "#22d3ee",
                      }
                    : {
                        background: "rgba(6,11,20,0.3)",
                        borderColor: "rgba(30,41,59,0.5)",
                        color: "#1e3a5f",
                      }
              }
            >
              {i < current ? "✓" : `0${i + 1}`}
            </div>
            {/* Label */}
            <span
              className="text-[10px] font-medium tracking-wide whitespace-nowrap md:text-xs"
              style={{
                color: i === current ? "#22d3ee" : i < current ? "#94a3b8" : "#1e293b",
              }}
            >
              {label}
            </span>
          </div>

          {/* Connector line */}
          {i < STEPS.length - 1 && (
            <div
              className="mx-2 mt-[18px] h-px flex-1 transition-all duration-300"
              style={{
                background:
                  i < current
                    ? "linear-gradient(90deg, rgba(34,211,238,0.6), rgba(34,211,238,0.2))"
                    : "rgba(30,41,59,0.8)",
              }}
            />
          )}
        </div>
      ))}
    </nav>
  );
}
