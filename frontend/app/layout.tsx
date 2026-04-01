import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tax-cellent — U.S. Tax Filing for International Students",
  description:
    "File your U.S. taxes as an international student or non-resident alien. Upload your W-2 or 1099, review extracted fields, and generate Form 1040-NR and Form 8843 — all processed locally, nothing sent to the cloud.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className="min-h-screen"
        style={{ backgroundColor: "var(--color-bg)", color: "var(--color-text-primary)" }}
      >
        {/* Header */}
        <header
          className="sticky top-0 z-50 border-b px-6 py-4 backdrop-blur-md"
          style={{
            borderColor: "var(--color-border)",
            backgroundColor: "rgba(255,255,255,0.85)",
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Logo mark */}
              <div
                className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl font-mono text-sm font-bold"
                style={{
                  background: "linear-gradient(135deg, #0071E3 0%, #34C759 100%)",
                  color: "#FFFFFF",
                }}
              >
                TC
              </div>
              <div>
                <h1
                  className="text-xl font-bold tracking-tight"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  Tax-cellent
                </h1>
                <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  U.S. Tax Filing for International Students
                </p>
              </div>
            </div>

            {/* Status badge */}
            <div
              className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs"
              style={{
                borderColor: "rgba(52,199,89,0.3)",
                backgroundColor: "rgba(52,199,89,0.08)",
              }}
            >
              <span
                className="animate-pulse-glow h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: "var(--color-success)" }}
              />
              <span className="font-mono" style={{ color: "var(--color-success)" }}>
                ALL LOCAL
              </span>
            </div>
          </div>
        </header>

        {children}
      </body>
    </html>
  );
}
