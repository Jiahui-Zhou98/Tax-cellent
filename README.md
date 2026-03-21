# Tax-cellent

**A privacy-first, fully local tax document review system for international students and workers in the US.**

Upload your W-2, answer a few immigration questions, and get a step-by-step federal tax calculation — all running on your machine with zero data leaving your device.

---

## Project Description

Tax-cellent is a full-stack web application that helps international students and workers in the US understand their federal tax obligations. It combines local OCR, deterministic tax math, and on-device LLM inference to provide a transparent, step-by-step tax calculation — without sending any personal financial data to external servers.

The system extracts data from tax documents (W-2, 1099-NEC, 1099-INT), lets users verify every field, then runs 2025 IRS tax calculations in pure Python. A locally-running LLM adds plain-English explanations to each calculation step, but never produces or modifies any numbers.

---

## Project Objective

International students and workers in the US face unique tax challenges — FICA exemptions, treaty benefits, residency classification — yet most tax tools are cloud-based and require uploading sensitive documents to third-party servers.

Tax-cellent aims to:

1. **Protect privacy** — all processing (OCR, AI inference, tax math) runs 100% locally via Ollama.
2. **Ensure correctness** — tax calculations are deterministic Python code using IRS-published constants, not LLM-generated numbers.
3. **Build trust** — every calculation step cites its IRS rule reference and is expandable for inspection.
4. **Detect missed refunds** — automatically flags FICA taxes incorrectly withheld from F-1/J-1 students under IRC §3121(b)(19).

---

## Core Features

- **100% On-Device Processing** — OCR, LLM inference, and all tax math run locally. Nothing is sent to any external server.
- **Calculation Ledger** — a step-by-step table (Gross Wages → Standard Deduction → Taxable Income → Federal Tax → Balance) with inline expandable explanations and IRS rule citations.
- **FICA Refund Detection** — automatically flags Social Security and Medicare taxes incorrectly withheld from F-1/J-1 students (IRC §3121(b)(19)), with Form 843 filing guidance.
- **Human-in-the-Loop Verification** — all extracted fields are shown for review and editing before any calculation runs. Users control what goes into the engine.
- **Graceful LLM Fallback** — if Ollama is down, the ledger renders with template explanations. The numbers are always correct regardless of LLM availability.
- **Immigration Context Awareness** — a dedicated questionnaire captures visa type, US entry date, and days-present counts for residency classification.
- **Multi-Form OCR** — structure-aware extraction for W-2, 1099-NEC, and 1099-INT using opendataloader-pdf with spatial region zoning and confidence scoring.
- **2025 IRS Constants** — brackets, standard deduction ($14,600 single filer), FICA rates, and wage caps sourced from Rev. Proc. 2024-40.

---

## How It Works

```
PDF / Image
    │
    ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  OCR Engine     │───▶│  Human Review UI │───▶│  Tax Engine (Python) │
│  (local)        │    │  (verify fields) │    │  deterministic math  │
└─────────────────┘    └──────────────────┘    └──────────┬──────────┘
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

**Key design principle:** the tax engine does all arithmetic in pure Python using 2025 IRS constants. The LLM only adds plain-English explanations — it never produces numbers. If the LLM is unavailable, the ledger still renders correctly with template fallbacks.

---

## Tech Stack

| Layer             | Technology                                        |
| ----------------- | ------------------------------------------------- |
| Frontend          | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend           | FastAPI, Python 3.10+, Pydantic v2                |
| OCR / PDF Parsing | pdfplumber + opendataloader-pdf (structure-aware) |
| LLM Inference     | Ollama (local), model: `qwen3:8b`                 |
| Containerization  | Podman / Docker Compose                           |

---

## Project Structure

```
Tax-cellent/
├── backend/
│   ├── app/
│   │   ├── api/                        # FastAPI routes
│   │   │   ├── health.py               #   GET /health — Ollama status check
│   │   │   ├── upload.py               #   POST /api/upload — OCR + field extraction
│   │   │   └── review.py               #   POST /api/confirm, /api/analyze, /api/context
│   │   ├── core/
│   │   │   └── config.py               # Pydantic settings (Ollama URL, model, paths)
│   │   ├── prompts/
│   │   │   ├── field_extraction.txt     # LLM prompt for legacy field extraction fallback
│   │   │   └── tax_analysis.txt         # LLM prompt for step-by-step explanations
│   │   ├── schemas/
│   │   │   └── document.py             # Pydantic models (TaxReport, CalculationStep, …)
│   │   ├── services/
│   │   │   ├── candidate_extractor.py  # Structure-aware field extraction from PDF JSON
│   │   │   ├── extraction_service.py   # Field extraction pipeline (structured → LLM → regex)
│   │   │   ├── llm_client.py           # Ollama HTTP client (chat, chat_json)
│   │   │   ├── pdf_parser.py           # PDF/image text extraction (opendataloader + OCR)
│   │   │   ├── tax_engine.py           # Deterministic 2025 IRS tax math (no LLM)
│   │   │   ├── tax_advisor.py          # LLM explanation service (batch, one call)
│   │   │   └── validation_service.py   # Rule-based field validation
│   │   └── storage/
│   │       └── session_store.py        # File-based session persistence
│   ├── tests/
│   │   └── test_engine.py             # 17 unit tests for tax engine (no LLM required)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── lib/
│   │   │   └── api.ts                 # TypeScript API client
│   │   ├── globals.css                # Global styles
│   │   ├── layout.tsx                 # Root layout with header
│   │   └── page.tsx                   # Full UI — 6-step wizard
│   ├── Dockerfile
│   └── package.json
├── podman-compose.yml                 # Dev container setup
├── podman-compose.prod.yml            # Production container setup
├── start_dev.sh                       # One-command dev launcher
├── TODOS.md                           # Post-hackathon design debt tracker
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Ollama** — [install here](https://ollama.com), then pull the required models:

```bash
ollama pull qwen3:8b
ollama pull deepseek-ocr
```

### Quick Start (one command)

```bash
git clone https://github.com/Jiahui-Zhou98/Tax-cellent.git
cd Tax-cellent

# Start Ollama in a separate terminal
ollama serve

# Start backend + frontend
./start_dev.sh
```

### Manual Setup

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Access Points

| Service            | URL                        |
| ------------------ | -------------------------- |
| Frontend           | http://localhost:3000      |
| Backend API        | http://localhost:8000      |
| API Docs (Swagger) | http://localhost:8000/docs |

### Container Deploy (Podman / Docker)

Requires Ollama running on the host. Podman rootless uses `host.containers.internal` to reach it automatically.

```bash
podman-compose up --build
# or
docker compose up --build
```

### Configuration

Create `backend/.env` to override defaults:

```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_A=qwen3:8b
OCR_MODEL=deepseek-ocr
UPLOAD_DIR=/tmp/taxdebate_uploads
SESSION_DIR=/tmp/taxdebate_sessions
MAX_FILE_SIZE_MB=20
```

## Screenshots

> _Screenshots will be added here. The UI follows a 6-step wizard flow:_

| Step               | Screen                                                                         |
| ------------------ | ------------------------------------------------------------------------------ |
| 01 — Upload        | Dark dropzone with drag-and-drop support for PDF/image files                   |
| 02 — Context       | Immigration questionnaire (visa type, entry date, days present)                |
| 03 — Review Fields | Grouped field editor with confidence scores and inline editing                 |
| 04 — Validation    | Rule-based check results with severity badges (PASS / WARN / FAIL)             |
| 05 — Analysis      | Animated spinner with rotating IRS-rule hints                                  |
| 06 — Report        | Calculation Ledger with expandable rows, outcome banner, and FICA Handoff Card |

---

## Privacy

- **No external network calls** — all OCR and LLM inference run via Ollama on your machine.
- **Ephemeral storage** — uploaded files go to `/tmp/taxdebate_uploads` and session state to `/tmp/taxdebate_sessions`, both cleared on reboot by default.
- **AI guardrails** — the LLM explainer prompt explicitly forbids the model from producing dollar amounts or recalculating numbers.

---

## License

This project is licensed under the [MIT License](LICENSE).
