import type { AnalysisPreferences } from "./api";

export const ANALYSIS_PROVIDER_OPTIONS: {
  value: AnalysisPreferences["provider"];
  label: string;
  hint: string;
  placeholder: string;
}[] = [
  {
    value: "ollama",
    label: "Local (Ollama)",
    hint: "Runs fully on your machine — no data leaves your device.",
    placeholder: "Optional override, e.g. qwen3:8b",
  },
  {
    value: "openai",
    label: "ChatGPT / OpenAI",
    hint: "Uses the OpenAI API key configured in the backend.",
    placeholder: "Optional override, e.g. gpt-5.2",
  },
  {
    value: "anthropic",
    label: "Claude / Anthropic",
    hint: "Uses the Anthropic API key configured in the backend.",
    placeholder: "Optional override, e.g. claude-sonnet-4-20250514",
  },
  {
    value: "gemini",
    label: "Gemini / Google",
    hint: "Uses the Gemini API key configured in the backend.",
    placeholder: "Optional override, e.g. gemini-3-flash-preview",
  },
];
