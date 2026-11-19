# Fixsembly

> **Three Agents. One Verified Fix.**  
> *Self-Healing Multi-Agent Software Engineering System.*  
> **Red to green, automatically.**

Fixsembly is an autonomous software engineering platform that detects, analyzes, and repairs failing Python projects using a LangGraph-coordinated multi-agent workflow. It combines an **Architect**, **Coder**, and **Reviewer** agent with authoritative Pytest execution, Monaco-powered unified-patch inspection, real-time Server-Sent Events (SSE) telemetry, and strict anti-tampering security policies.

---

## 🎯 What Fixsembly Does

Fixsembly accepts a Python project with failing Pytest tests and autonomously works through a verification-gated repair loop:

```text
Upload Project ZIP
       ↓
Initial Pytest Assessment
       ↓
Architect Agent — Root Cause Analysis & Plan Formulation
       ↓
Coder Agent — Targeted Patch Synthesis (Strict Policy Guarded)
       ↓
Pytest Execution Backend — Verification Truth (Exit Code Gate)
       ↓
Reviewer Agent — Independent Audit & Regression Risk Gate
       ↓
Pass → Verified Fix Ready (.ZIP)  |  Fail → Next Repair Iteration
```

The system uses **actual Pytest exit codes** as the source of truth for test outcomes instead of trusting an LLM's claim that a fix works.

---

## 🤖 Multi-Agent Architecture

- **Architect Agent**: Read-only analysis agent that parses pytest failure diagnostics, error tracebacks, and directory structure to formulate a structured `ArchitecturePlan`.
- **Coder Agent**: Synthesizes minimal unified diff patches or surgical file writes. Includes an automated recovery fallback if diff headers are malformed.
- **Reviewer Agent**: Independent quality gate that audits Git diffs and before/after test results to assess regression risk.
- **Pytest Runner**: Bounded subprocess execution; Docker isolation is available when a Docker daemon and the configured sandbox image are provided. Production local execution is blocked.
- **LangGraph StateGraph**: Orchestrates agents, handles patch retries, and invokes loop detection to prevent infinite failing cycles.

---

## 🖥️ Technology Stack

### Frontend
- **Framework**: React 18+ (Pure JavaScript)
- **Bundler & Dev Server**: Vite
- **Styling**: Tailwind CSS (Cyber-engineering dark/light palette)
- **Routing**: React Router v6
- **Iconography**: Lucide React
- **Code & Diff Inspection**: Monaco Editor (`@monaco-editor/react`)
- **Real-Time Telemetry**: Server-Sent Events (SSE) via `useRunStream` hook with REST polling fallback

### Backend
- **API Framework**: FastAPI & Starlette
- **State Machine**: LangGraph (v1.2+) & LangChain Core
- **Database**: SQLAlchemy 2.0 ORM (SQLite for local dev, PostgreSQL for production)
- **Authentication**: JWT Bearer tokens + bcrypt password hashing & guest sessions
- **Testing Engine**: Subprocess Pytest runner with hard timeouts
- **Diff Tracking**: Ephemeral Git repository tracking

---

## 📁 Repository Structure

```text
Fixsembly/
├── backend/
│   ├── agents/          # Architect, Coder, Reviewer agents, schemas, policies, prompts
│   ├── api/             # FastAPI routers (runs, projects, auth, guests, health) & SSE stream
│   ├── context/         # Bounded context builder with prompt injection defenses
│   ├── core/            # Configuration settings, logging, and security
│   ├── database/        # SQLAlchemy models (Run, Project, Iteration, Event) & persistence
│   ├── execution/       # Workspace manager & sandboxed execution backends
│   ├── graph/           # LangGraph state machine, nodes, conditional routers, loop detector
│   ├── llm/             # LLM provider abstractions (Groq, Ollama, Mock)
│   ├── tools/           # Pytest runner, Git diff tools, and filesystem operations
│   └── main.py          # FastAPI application factory
├── frontend/            # React + Vite + Tailwind CSS SPA
│   ├── src/
│   │   ├── api/         # API client, run endpoints, auth, and SSE hook
│   │   ├── components/  # Navbar, Sidebar, AgentStepper, MonacoDiff, Terminal, ReviewAudit
│   │   ├── context/     # AuthContext (Guest + User) and ThemeContext
│   │   └── pages/       # Landing, Overview, NewRepair, RepairStudio, History, Health, Docs
│   ├── nginx.conf       # Production Nginx reverse-proxy configuration
│   └── package.json     # Frontend dependencies
├── frontend_legacy/     # Preserved legacy Streamlit frontend
├── demo_projects/       # Buggy calculator sample project & packaged ZIP
├── evaluation/          # Benchmark evaluation suite
├── tests/               # 22 test suites covering all backend phases & SSE streaming
├── Dockerfile           # Backend container
├── Dockerfile.frontend  # Multi-stage React + Nginx container
├── docker-compose.yml   # Multi-service stack (Postgres, FastAPI backend, React frontend)
└── pyproject.toml       # Ruff and Pytest configuration
```

---

## 🚀 Quick Start

### 1. Run via Docker Compose (local development)

```bash
docker compose up --build
```
- React Frontend: http://localhost:3000
- FastAPI Backend & Swagger Docs: http://localhost:8000/docs

### 2. Run Locally (trusted projects only)

**Start Backend:**
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Start Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 in your browser.

> **Execution safety:** the local runner executes uploaded Python tests inside the API service environment and is for trusted local projects only. Production deployments intentionally reject local execution. Enable public repairs only after connecting a separately isolated Docker or remote sandbox worker. The Render blueprint keeps the API and UI available but repair execution returns HTTP 503 until that worker is configured.

### Frontend deployment configuration

Set `VITE_BACKEND_URL` to the backend origin (for example, the HTTPS Render service URL) in the frontend hosting provider before building. The frontend accepts either a full URL or a host name.

---

## 🧪 Testing

Run backend test suites:
```bash
pytest -q
```

Test frontend utilities and build the React app:
```bash
cd frontend
npm ci
npm test
npm run build
```

### Docker sandbox image

Build the runner image before selecting `EXECUTION_BACKEND=docker`:
```bash
docker build -f Dockerfile.sandbox -t fixsembly-pytest-sandbox:latest .
```
The sandbox has Pytest preinstalled, runs without network access and mounts the uploaded project read-only. Project-specific third-party dependencies must already be available in the sandbox image; dependency installation from untrusted project archives is not performed automatically.

The Render blueprint deliberately keeps `EXECUTION_BACKEND=local` with `ENV=production`, so repair creation returns HTTP 503 until a separate isolated execution service is available. Do not remove this guard to make the UI appear functional.
