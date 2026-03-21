# TaxDebate Local

A **privacy-first, fully local** tax document review system for international students and workers in the US. Upload your W-2, answer a few immigration questions, and get a step-by-step federal tax calculation — with no data ever leaving your machine.

---

## How It Works

```
PDF / Image
    │
    ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  OCR Engine     │───▶│  Human Review UI │───▶│  Tax Engine (Python)│
│  (local)        │    │  (verify fields) │    │  deterministic math │
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

**The key design principle:** the tax engine does all arithmetic in pure Python using 2025 IRS constants. The LLM only adds plain-English explanations — it never produces numbers. If the LLM is unavailable, the ledger still renders with correct numbers and template fallbacks.

---

## Features

- **100% on-device** — OCR, LLM inference, and all tax math run locally via Ollama. Nothing is sent to any external server.
- **Calculation Ledger** — a step-by-step table (Gross Wages → Standard Deduction → Taxable Income → Federal Tax → Balance) with inline expandable explanations and IRS rule citations.
- **FICA Refund Detection** — automatically flags Social Security and Medicare taxes incorrectly withheld from F-1/J-1 students (IRC §3121(b)(19)), with Form 843 guidance.
- **Human-in-the-loop verification** — extracted fields are shown for review and editing before any calculation runs.
- **Graceful LLM fallback** — if Ollama is down, the ledger renders with template explanations. The numbers are always correct.
- **2025 IRS constants** — brackets, standard deduction ($14,600), FICA rates and wage caps sourced from Rev. Proc. 2024-40.

---

## Demo Scenario

To showcase the FICA detection feature during a demo:

| Field                            | Value   |
| -------------------------------- | ------- |
| Form type                        | W-2     |
| Box 1 — Wages                    | $52,000 |
| Box 2 — Federal withheld         | $8,000  |
| Box 4 — Social Security withheld | $3,224  |
| Box 6 — Medicare withheld        | $754    |
| Visa type                        | F-1     |
| First US entry year              | 2024    |

**Expected output:** $3,750.50 estimated federal refund + amber FICA Handoff Card citing IRC §3121(b)(19) and Form 843.

---

## Tech Stack

| Layer                 | Technology                                        |
| --------------------- | ------------------------------------------------- |
| Frontend              | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| Backend               | FastAPI, Python 3.10+, Pydantic v2                |
| OCR                   | pdfplumber + opendataloader-pdf                   |
| LLM inference         | Ollama (local)                                    |
| Tax explanation model | `qwen3:8b`                                        |
| Containerization      | Podman / Docker Compose                           |

---

## Prerequisites

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

---

## Configuration

Create `backend/.env` to override defaults:

```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_A=qwen3:8b
UPLOAD_DIR=/tmp/taxdebate_uploads
SESSION_DIR=/tmp/taxdebate_sessions
MAX_FILE_SIZE_MB=20
```

---

## Container Deploy (Podman / Docker)

Pre-built images are published to [GitHub Container Registry](https://github.com/Jiahui-Zhou98/Tax-cellent/pkgs/container/) on every push to `main`.

### Option A — Use pre-built images (recommended)

No need to clone the repo or install Python/Node locally.

```bash
# 1. Make sure Ollama is running
ollama serve
ollama pull qwen3:8b
ollama pull deepseek-ocr

# 2. Download the production compose file
curl -O https://raw.githubusercontent.com/Jiahui-Zhou98/Tax-cellent/main/podman-compose.prod.yml

# 3. Start the services
podman-compose -f podman-compose.prod.yml up
# or with Docker:
docker compose -f podman-compose.prod.yml up
```

Then visit http://localhost:3000.

### Option B — Build from source

```bash
git clone https://github.com/Jiahui-Zhou98/Tax-cellent.git
cd Tax-cellent

ollama serve   # in a separate terminal

podman-compose up --build
# or
docker compose up --build
```

> **Note:** Podman rootless uses `host.containers.internal` to reach Ollama on the host automatically. If using Docker on Linux, you may need `--add-host=host.containers.internal:host-gateway` or set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

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

- No network calls to external APIs — all OCR and LLM inference run via Ollama on your machine.
- Uploaded files are written to `/tmp/taxdebate_uploads` and session state to `/tmp/taxdebate_sessions` — both cleared on reboot by default.
- The LLM explainer prompt explicitly forbids the model from producing dollar amounts or recalculating numbers.
