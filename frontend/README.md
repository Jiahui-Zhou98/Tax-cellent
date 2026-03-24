# Tax-cellent — Frontend

Next.js 16 / React 19 / TypeScript / Tailwind CSS v4 frontend for the Tax-cellent tax document review product.

## Development

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The backend must be running on port 8000. See the [root README](../README.md) for backend setup.

## Environment Variables

| Variable               | Default                   | Description                                   |
| ---------------------- | ------------------------- | --------------------------------------------- |
| `NEXT_PUBLIC_API_URL`  | `http://localhost:8000`   | Backend API base URL                          |

## Project Structure

```
app/
├── components/         # UI components (one file per step/feature)
│   ├── UploadStep.tsx          # Document upload dropzone
│   ├── ContextStep.tsx         # Immigration questionnaire
│   ├── ReviewStep.tsx          # Extracted field editor
│   ├── ValidationStep.tsx      # Rule-based validation results
│   ├── SettingsStep.tsx        # AI provider picker + API key input
│   ├── AnalysisStep.tsx        # Progress indicator
│   ├── ReportStep.tsx          # Calculation Ledger + FICA card
│   └── SectionCard.tsx         # Shared card wrapper
├── lib/
│   └── api.ts                  # Typed API client (all backend calls)
├── styles/
│   └── index.ts                # Shared style tokens (inputStyle, glowBtn)
└── page.tsx                    # Root step-machine orchestrator
```

## AI Provider Settings

`SettingsStep` lets users choose between Ollama (local, default) and cloud providers (OpenAI, Anthropic, Gemini). The available model lists and provider keys are defined in:

- **Frontend:** `components/SettingsStep.tsx` — `PROVIDER_MODELS` constant
- **Backend:** `app/api/review.py` — `PROVIDER_MODELS` allowlist

Both must be kept in sync. A `// SYNC:` comment marks both locations.

## Build

```bash
npm run build
npm start
```

## Linting

```bash
npm run lint
```
