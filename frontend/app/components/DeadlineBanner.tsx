"use client";

// ---------------------------------------------------------------------------
// DeadlineBanner — shows the relevant IRS filing deadline based on visa type
// and the current date.
//
// Deadlines (2026):
//   Apr 15 — domestic filers + NRAs with US wages (Form 1040 / 1040-NR)
//   Jun 15 — NRAs without US wages (Form 1040-NR)
//   Oct 15 — extension deadline (all filers who filed Form 4868)
//
// Urgency tiers (days until deadline):
//   > 30 days  → green  (calm)
//   8–30 days  → amber  (heads-up)
//   ≤ 7 days   → red    (urgent)
// ---------------------------------------------------------------------------

const NRA_VISAS = new Set(["F-1", "J-1", "F1", "J1", "OPT", "CPT", "H-1B", "other"]);
const DOMESTIC_VISAS = new Set(["US_CITIZEN", "GREEN_CARD", "RESIDENT_ALIEN"]);

// Returns the relevant deadline date for the given visa type.
function getDeadline(visaType: string): { date: Date; label: string; note: string } {
  const year = new Date().getFullYear();

  if (!visaType || DOMESTIC_VISAS.has(visaType)) {
    return {
      date: new Date(`${year}-04-15`),
      label: "April 15",
      note: "Federal income tax filing deadline",
    };
  }

  if (NRA_VISAS.has(visaType)) {
    // NRAs with US wages use Apr 15; without wages use Jun 15.
    // We default to Apr 15 as the safe conservative choice since we don't
    // know at this point whether wages are present.
    return {
      date: new Date(`${year}-04-15`),
      label: "April 15",
      note: "Form 1040-NR filing deadline (NRA with US-source income)",
    };
  }

  return {
    date: new Date(`${year}-04-15`),
    label: "April 15",
    note: "Federal income tax filing deadline",
  };
}

function daysUntil(target: Date): number {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const t = new Date(target);
  t.setHours(0, 0, 0, 0);
  return Math.ceil((t.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export function DeadlineBanner({ visaType }: { visaType?: string }) {
  const { date, label, note } = getDeadline(visaType ?? "");
  const days = daysUntil(date);

  // Don't show banner if deadline has passed or more than 60 days away
  if (days < 0 || days > 60) return null;

  let color: string;
  let bg: string;
  let border: string;
  let urgencyLabel: string;

  if (days <= 7) {
    color = "#f87171";
    bg = "rgba(248,113,113,0.07)";
    border = "rgba(248,113,113,0.3)";
    urgencyLabel = days === 0 ? "TODAY" : `${days} day${days === 1 ? "" : "s"} left`;
  } else if (days <= 30) {
    color = "#fbbf24";
    bg = "rgba(251,191,36,0.07)";
    border = "rgba(251,191,36,0.3)";
    urgencyLabel = `${days} days left`;
  } else {
    color = "#34d399";
    bg = "rgba(52,211,153,0.05)";
    border = "rgba(52,211,153,0.2)";
    urgencyLabel = `${days} days left`;
  }

  return (
    <div
      className="flex items-center justify-between gap-4 rounded-xl px-4 py-2.5 text-xs"
      style={{ background: bg, border: `1px solid ${border}` }}
      role="status"
      aria-label={`Tax filing deadline: ${label}, ${urgencyLabel}`}
    >
      <span style={{ color }} className="font-mono font-semibold">
        ⏰ {label} deadline
      </span>
      <span className="text-slate-500 hidden sm:block truncate">{note}</span>
      <span
        className="font-mono font-bold flex-shrink-0"
        style={{ color }}
      >
        {urgencyLabel}
      </span>
    </div>
  );
}
