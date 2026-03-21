# Tax-cellent Local

A **privacy-first, fully local** tax document review system for international students and workers in the US. Upload your W-2, answer a few immigration questions, and get a step-by-step federal tax calculation — with no data ever leaving your machine.

---

## How It Works

```
PDF / Image
    │
    ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  OCR Engine │───▶│  Human Review UI │───▶│  Tax Engine (Python) │
│  (local)    │    │  (verify fields) │    │  deterministic math  │
└─────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                       │ numbers
                                                       ▼
                                           ┌─────────────────────┐
                                           │  LLM Explainer      │
                                           │  (plain English)    │
                                           └──────────┬──────────┘
                                                       │
                                                       ▼
                                           ┌─────────────────────┐
                                           │  Calculation Ledger │
                                           │  + FICA Handoff Card│
                                           └─────────────────────┘
```

**The key design principle:** the tax engine does all arithmetic in pure Python using 2025 IRS constants. The LLM only adds plain-English explanations — it never produces numbers. If the LLM is unavailable, the ledger still renders with correct numbers and template fallbacks.

---

## Features

- **Local-first by default** — OCR, extraction, validation, and tax math stay local. The final explanation layer can now use Ollama or an optional cloud provider.
- **Calculation Ledger** — a step-by-step table (Gross Wages → Standard Deduction → Taxable Income → Federal Tax → Balance) with inline expandable explanations and IRS rule citations.
- **FICA Refund Detection** — automatically flags Social Security and Medicare taxes incorrectly withheld from F-1/J-1 students (IRC §3121(b)(19)), with Form 843 guidance.
- **Human-in-the-loop verification** — extracted fields are shown for review and editing before any calculation runs.
- **Provider choice at analysis time** — users can choose a local Ollama model or a cloud provider such as OpenAI, Claude, or Gemini for the final step explanations.
- **Graceful LLM fallback** — if the explainer call fails, the ledger renders with template explanations. The numbers are always correct.
- **2025 IRS constants** — brackets, standard deduction ($14,600), FICA rates and wage caps sourced from Rev. Proc. 2024-40.

---

## Demo Scenario

To showcase the FICA detection feature during a demo:

| Field | Value |
|---|---|
| Form type | W-2 |
| Box 1 — Wages | $52,000 |
| Box 2 — Federal withheld | $8,000 |
| Box 4 — Social Security withheld | $3,224 |
| Box 6 — Medicare withheld | $754 |
| Visa type | F-1 |
| First US entry year | 2024 |

**Expected output:** $3,750.50 estimated federal refund + amber FICA Handoff Card citing IRC §3121(b)(19) and Form 843.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.10+, Pydantic v2 |
| OCR | pdfplumber + opendataloader-pdf |
| LLM inference | Ollama by default, optional OpenAI / Claude / Gemini for report explanations |
| Default explanation model | `qwen3:8b` locally, provider defaults configurable in `backend/.env` |
| Containerization | Podman / Docker Compose |

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Ollama** — [install](https://ollama.com) then pull the model:

```bash
ollama pull qwen3:8b
```

---

## Quickstart

```bash
git clone https://github.com/Jiahui-Zhou98/Hackathon-tax.git
cd Hackathon-tax

# Start Ollama in a separate terminal
ollama serve

# Start backend + frontend
./start_dev.sh
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

---

## Manual Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Configuration

Create `backend/.env` to override defaults:

```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_A=qwen3:8b
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.2
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash-preview
UPLOAD_DIR=/tmp/taxdebate_uploads
SESSION_DIR=/tmp/taxdebate_sessions
MAX_FILE_SIZE_MB=20
```

Cloud keys are optional. If they are absent, the app still works with local Ollama and deterministic template fallbacks.

---

## Container Deploy (Podman / Docker)

Requires Ollama running on the host. Podman rootless uses `host.containers.internal` to reach it automatically.

```bash
podman-compose up --build
# or
docker compose up --build
```

---

## Project Structure

```
taxdebate/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (upload, review, health)
│   │   ├── core/           # Config (pydantic-settings)
│   │   ├── prompts/        # LLM system prompts
│   │   ├── schemas/        # Pydantic models (CalculationStep, TaxReport, …)
│   │   ├── services/
│   │   │   ├── tax_engine.py     # Deterministic 2025 IRS math (no LLM)
│   │   │   ├── tax_advisor.py    # Batch LLM explanation call
│   │   │   └── validation_service.py
│   │   └── storage/        # File-based session store
│   ├── tests/
│   │   └── test_engine.py  # 17 unit tests — no LLM required
│   └── requirements.txt
├── frontend/
│   └── app/
│       ├── lib/api.ts      # API client
│       └── page.tsx        # Full UI (6-step wizard)
├── podman-compose.yml
├── start_dev.sh
└── TODOS.md
```

---

## Running Tests

The tax engine tests are pure Python — no Ollama required:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_engine.py -v
```

All 17 tests cover the demo scenario (F-1, FICA flags), H-1B (no FICA flag), missing fields (unknown outcome), and 2025 bracket math.

---

## Supported Forms

| Form | Status |
|---|---|
| W-2 | Full support |
| 1099-NEC | OCR extraction only (calculation pending) |
| 1099-INT | OCR extraction only (calculation pending) |

---

## Privacy

- By default, OCR and LLM inference run via Ollama on your machine. If a user explicitly selects OpenAI, Claude, or Gemini for the analysis explanation step, that prompt is sent to the chosen cloud provider.
- Uploaded files are written to `/tmp/taxdebate_uploads` and session state to `/tmp/taxdebate_sessions` — both cleared on reboot by default.
- The LLM explainer prompt explicitly forbids the model from producing dollar amounts or recalculating numbers.
