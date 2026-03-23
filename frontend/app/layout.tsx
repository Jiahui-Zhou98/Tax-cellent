import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tax-cellent",
  description: "Privacy-first local tax document review",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen text-slate-100" style={{ backgroundColor: "#060b14" }}>
        {/* Header */}
        <header
          className="border-b px-6 py-4 sticky top-0 z-50 backdrop-blur-md"
          style={{
            borderColor: "rgba(255,255,255,0.06)",
            backgroundColor: "rgba(6,11,20,0.85)",
          }}
        >
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Logo mark */}
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-mono font-bold"
                style={{
                  background: "linear-gradient(135deg, #0ea5e9 0%, #22d3ee 100%)",
                  color: "#060b14",
                  boxShadow: "0 0 16px rgba(34,211,238,0.35)",
                }}
              >
                TC
              </div>
              <div>
                <h1 className="text-sm font-semibold text-white tracking-wide">
                  Tax-cellent
                </h1>
                <p className="text-xs text-slate-600">
                  Privacy-first · On-device AI
                </p>
              </div>
            </div>

            {/* Status badge */}
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border"
              style={{
                borderColor: "rgba(16,185,129,0.12)",
                backgroundColor: "rgba(16,185,129,0.05)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-glow"
              />
              <span className="text-emerald-400 font-mono">ALL LOCAL</span>
            </div>
          </div>
        </header>

        <main className="max-w-3xl mx-auto px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
