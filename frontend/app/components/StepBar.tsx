"use client";

const STEPS = ["Upload", "Context", "Review", "Validate", "Settings", "Analysis", "Report"];

export function StepBar({ current }: { current: number }) {
  return (
    <nav aria-label="Progress steps" className="flex items-start mb-12">
      {STEPS.map((label, i) => (
        <div key={i} className="flex items-start flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-2">
            {/* Circle */}
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-mono font-bold border transition-all duration-300"
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
              className="hidden md:block text-xs font-medium tracking-wide whitespace-nowrap"
              style={{
                color:
                  i === current
                    ? "#22d3ee"
                    : i < current
                    ? "#94a3b8"
                    : "#1e293b",
              }}
            >
              {label}
            </span>
          </div>

          {/* Connector line */}
          {i < STEPS.length - 1 && (
            <div
              className="flex-1 h-px mx-2 mt-[18px] transition-all duration-300"
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
