# AegisCode Production Deployment Guide

This guide details step-by-step instructions for configuring, deploying, and maintaining **AegisCode** in production environments.

---

## Architecture Overview

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
     │                   ├── Architect Agent
     │                   ├── Coder Agent
     │                   └── Reviewer Agent
     │
     └─────────────► Docker / Local Sandbox (Pytest Execution)
```

---

## 1. Environment Configuration

Copy `.env.example` to `.env` in production:

```bash
cp .env.example .env
```

### Essential Production Environment Variables

| Variable | Recommended Value | Description |
|---|---|---|
| `ENV` | `production` | Enables production security mode |
| `DEBUG` | `false` | Disables verbose debug logging |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/dbname` | PostgreSQL connection string |
| `LLM_PROVIDER` | `openai_compatible` or `ollama` | Provider selection |
| `OPENAI_API_KEY` | `sk-...` | Hosted LLM API Key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Hosted provider endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Target model for reasoning & coding |
| `CORS_ORIGINS` | `https://your-frontend.onrender.com` | Allowed CORS origins |
| `BACKEND_URL` | `https://your-backend.onrender.com/api` | Streamlit backend endpoint |
| `EXECUTION_BACKEND` | `docker` or `local` | Sandbox backend choice |

---

## 2. Local Production Testing with Docker Compose

Run the entire 3-tier architecture locally with PostgreSQL:

```bash
docker-compose up --build
```

Services launched:
- **PostgreSQL**: `localhost:5432`
- **FastAPI Backend**: `localhost:8000`
- **Streamlit Frontend**: `localhost:8501`

---

## 3. Cloud Deployment (Render / Railway / Fly.io)

AegisCode includes a pre-configured `render.yaml` blueprint.

### 1-Click Deployment on Render
1. Push your repository to GitHub.
2. Connect your repository to [Render.com](https://render.com).
3. Create a **New Blueprint Instance** using `render.yaml`.
4. Set your `OPENAI_API_KEY` environment secret in the Render Dashboard.

---

## 4. Sandbox Security Model

Uploaded Python code **never** executes directly on the host application process in production mode:
- **Container Isolation**: `DockerExecutionBackend` executes code inside ephemeral `python:3.11-slim` containers.
- **Network Restriction**: Containers run with `--network none` to prevent data exfiltration.
- **Resource Constraints**: Strict RAM (512MB), CPU, and execution timeout (60s) limits.
- **Test Protection Policy**: The security engine blocks any agent attempts to modify test files (`tests/*`, `test_*.py`, `conftest.py`) or system configurations (`.env`, `Dockerfile`).

---

## 5. Verification & Monitoring

Check health status:

```bash
curl -X GET https://your-backend.onrender.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "app_name": "AegisCode",
  "version": "0.1.0",
  "database": "connected",
  "llm_provider": "openai_compatible"
}
```
