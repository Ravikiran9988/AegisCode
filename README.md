# AegisCode — Self-Healing Multi-Agent Software Engineering System

**AegisCode** is an end-to-end autonomous software engineering agent system that accepts Python projects containing failing `pytest` test suites, analyzes codebases, identifies root causes, applies targeted code repairs, executes test suites safely, audits git diffs for regressions, and iteratively repairs code until all tests pass or a maximum iteration limit is reached.

---

## 🌟 Key Features

- **Multi-Agent Orchestration**: Decoupled **Architect**, **Coder**, and **Reviewer** agents operating in a controlled **LangGraph** state graph loop.
- **Authoritative Pytest Feedback**: The system relies strictly on Pytest exit codes and outputs, never asking an LLM to "guess" if tests passed.
- **Strict Security & Test Protection**: Intercepts and blocks any agent attempts to modify test files (`tests/*`, `test_*.py`), configuration (`.env`), or escape workspace bounds.
- **Swappable LLM Provider Layer**: Native production integration with Groq (`openai/gpt-oss-120b`), hosted **OpenAI-compatible** APIs, local **Ollama** models for offline dev, and deterministic **Mock** providers for unit testing.
- **Isolated Sandbox Execution**: Swappable local subprocess execution and containerized **Docker** sandbox (`--network none`) backends.
- **Failure Loop Detection**: Deterministic failure fingerprinting halts stalled repair loops if identical test failures repeat.
- **Production Dashboard**: Interactive **Streamlit** dashboard displaying live metrics, step-by-step iteration timelines, git diffs, and reviewer assessments.

---

## 🏗️ Architecture Diagram

```
User (Browser)
     │
     ▼
Streamlit Frontend (Port 8501)
     │
     ▼  HTTP / REST API (CORS Restricted)
FastAPI Backend (Port 8000)
     │
     ├─────────────► SQLite / PostgreSQL Database
     │
     ├─────────────► LangGraph State Machine Loop
     │                   ├── Architect Agent (Analysis & Plan)
     │                   ├── Coder Agent (Targeted Patching)
     │                   └── Reviewer Agent (Audit & Regression Risk)
     │
     └─────────────► Docker / Local Sandbox (Pytest Execution)
```

---

## 🔄 LangGraph Repair Workflow

```
START
  │
  ▼
Initial Test Node (Fast-path exit if project already passes)
  │
  ▼
Architect Node (Analyzes traceback & generates ArchitecturePlan)
  │
  ▼
Coder Node (Generates CodeChange & evaluates security policy)
  │
  ▼
Test Node (Authoritative Pytest execution)
  │
  ▼
Reviewer Node (Independent audit & regression assessment)
  │
  ▼
Decision Router
  ├── Pass & Approved  --> END (status="passed")
  ├── Max Iterations   --> END (status="failed")
  ├── Repeated Failure --> END (status="stalled")
  └── Retry            --> ARCHITECT NODE (Iteration N+1)
```

---

## 🛠️ Technology Stack

- **Core**: Python 3.12, FastAPI, Pydantic v2
- **Orchestration**: LangGraph, LangChain Core
- **Database**: SQLite (Development) / PostgreSQL (Production), SQLAlchemy 2.0
- **LLM Abstraction**: Ollama REST API, OpenAI Chat Completions API
- **Execution & Sandbox**: Pytest, Docker Python SDK, GitPython
- **Frontend**: Streamlit, Requests

---

## 📁 Project Structure

```
Aegis/
├── backend/
│   ├── agents/            # Specialized agents (Architect, Coder, Reviewer) & security policies
│   ├── api/               # FastAPI REST endpoints (/health, /projects, /runs)
│   ├── context/           # Untrusted project context builder & token bounds
│   ├── core/              # Configuration (pydantic-settings) & logging
│   ├── database/          # SQLAlchemy models (Project, Run, Iteration, Event) & sessions
│   ├── execution/         # Workspace manager & Docker/Local backends
│   ├── graph/             # LangGraph state graph, nodes, & failure loop detector
│   ├── llm/               # Provider abstraction (Ollama, OpenAI-compatible, Mock)
│   └── tools/             # Pytest runner, filesystem tools, git tools
├── frontend/
│   └── app.py             # Streamlit dashboard
├── demo_projects/
│   └── buggy_calculator/  # Safe demo project for capstone video
├── docs/
│   └── DEPLOYMENT.md      # Detailed production deployment guide
├── tests/                 # Complete test suite (115+ tests across Phases 1–5)
├── Dockerfile             # Multi-stage FastAPI backend build
├── Dockerfile.frontend    # Streamlit frontend build
├── docker-compose.yml     # Local production stack (PostgreSQL + FastAPI + Streamlit)
├── pyproject.toml         # Dependencies & tool configuration
└── README.md
```

---

## ⚡ Quickstart — Local Setup

### 1. Prerequisites
- Python 3.10 – 3.12
- Git
- (Optional) Ollama or Docker

### 2. Installation
```bash
git clone https://github.com/your-username/aegiscode.git
cd aegiscode

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Environment Setup
```bash
cp .env.example .env
```

### 4. Running Local Backend & Frontend
Start FastAPI Backend:
```bash
uvicorn backend.main:app --reload --port 8000
```

Start Streamlit Frontend:
```bash
streamlit run frontend/app.py --server.port 8501
```

Access the Streamlit Dashboard at `http://localhost:8501`.

---

## 🦙 Ollama Setup

To run locally with open-weights models via Ollama:

1. Install Ollama from [ollama.ai](https://ollama.ai).
2. Pull the recommended coding model:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
3. Ensure `.env` contains:
   ```ini
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen2.5-coder:7b
   ```

---

## 🔌 REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application & database health check |
| `POST` | `/api/projects/upload` | Upload & extract Python project ZIP |
| `GET` | `/api/projects` | List uploaded projects |
| `POST` | `/api/runs` | Create a repair run & run initial tests |
| `POST` | `/api/runs/{id}/repair` | Trigger autonomous LangGraph repair loop |
| `GET` | `/api/runs/{id}/status` | Get real-time status & iteration metrics |
| `GET` | `/api/runs/{id}/results` | Get full test results & iteration breakdown |

---

## 🔒 Security Architecture

- **Path Traversal Protection**: Rejects all `../`, absolute, or symlink paths pointing outside workspace boundaries.
- **Test Protection Engine**: `PolicyViolationError` blocks Coder agent from altering test suites (`tests/*`, `test_*.py`).
- **Prompt Injection Defense**: Untrusted codebase content & tracebacks wrapped in `<untrusted_...>` delimiters.
- **Docker Isolation**: Containers run non-root with `--network none` and 512MB RAM caps.

---

## 📊 Evaluation & Benchmark Results

AegisCode includes an automated evaluation framework (`backend/evaluation/evaluator.py`) that benchmarks repair performance across deterministic project datasets:

| Benchmark Category | Benchmark ID & Name | Difficulty | Expected Termination | Observed Status | Duration |
|---|---|:---:|:---:|:---:|---:|
| **Arithmetic Bug** | `01_arithmetic_bug` | Easy | `all_tests_passed` | **PASSED** | 9.11s |
| **Logic Bug** | `02_logic_bug` | Easy | `all_tests_passed` | **PASSED** | 8.39s |
| **Multi-Bug Project** | `03_multi_bug` | Medium | `all_tests_passed` | **STALLED** | 10.66s |
| **Syntax Error** | `04_syntax_error` | Easy | `repeated_failure` | **STALLED** | 11.95s |
| **Unfixable Contract** | `05_unfixable_bug` | Easy | `repeated_failure` | **STALLED** | 11.08s |
| **Policy Violation** | `06_policy_violation` | Easy | `policy_violation` | **SAFE STOP** | 3.73s |

---

## 🛡️ Security Evaluation Matrix

| Security Threat | Security Control Mechanism | Verification Status |
|---|---|:---:|
| **Zip Slip Path Traversal** | Path boundary validation & absolute path rejection | **BLOCKED** |
| **Test Suite Modification** | Policy engine guards `tests/*`, `test_*.py`, `conftest.py` | **SAFE STOP** |
| **System File Tampering** | Protected file list guards `.env`, `.git/`, `Dockerfile` | **SAFE STOP** |
| **Prompt Injection Attacks** | Untrusted content enclosed in `<untrusted_...>` tags | **PASSIVE DATA** |
| **Infinite Repair Loops** | SHA256 failure fingerprinting & loop detector | **TERMINATED** |
| **Container Breakout** | Docker non-root execution & `--network none` flag | **ISOLATED** |

---

## 🎬 Capstone Demo & Live Application

- **Live Application URL**: [Placeholder — Live Demo App Link]
- **Public REST API**: [Placeholder — Live FastAPI Health Endpoint]
- **Demo Video (2:30 mins)**: [Placeholder — Video Demo Link]

### Video Demonstration Script Outline
- **0:00 – 0:20**: Introduction & Problem Statement
- **0:20 – 0:40**: 3-Tier Architecture & LangGraph Graph Overview
- **0:40 – 1:00**: Uploading broken `buggy_calculator.zip`
- **1:00 – 1:30**: Autonomous execution (Architect Plan → Coder Patch → Pytest Execution)
- **1:30 – 1:50**: Independent Reviewer audit & Git Diff inspection
- **1:50 – 2:30**: Security controls, benchmark metrics & summary

---

## 🧪 Testing & Verification

Run complete test suite across all 5 phases:

```bash
python -m pytest -v
```

Run linting checks:

```bash
python -m ruff check backend/ frontend/ tests/
```
