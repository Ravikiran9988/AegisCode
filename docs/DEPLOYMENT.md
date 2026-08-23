# AegisCode Production Deployment Guide

This guide details configuring and maintaining **AegisCode** in a production environment.

---

## Architecture Overview

```
User (Browser)
     │
     ▼
Streamlit Frontend
     │
     ▼  HTTP / REST API
FastAPI Backend
     │
     ├─────────────► PostgreSQL Database
     ├─────────────► LangGraph State Machine Loop
     │                   ├── Architect Agent
     │                   ├── Coder Agent
     │                   └── Reviewer Agent
     └─────────────► Local / Docker execution sandbox
```

---

## 1. Environment Configuration

Copy `.env.example` for local development or configure the same variables in your deployment environment. Never commit API keys.

### Essential Production Environment Variables

| Variable | Recommended Value | Description |
|---|---|---|
| `ENV` | `production` | Enables production validation |
| `DEBUG` | `false` | Disables verbose debug behavior |
| `DATABASE_URL` | PostgreSQL connection string | Persistent application database |
| `LLM_PROVIDER` | `openai_compatible` | Hosted OpenAI-compatible provider |
| `OPENAI_API_KEY` | deployment secret | Groq/API key; never commit it |
| `OPENAI_BASE_URL` | provider base URL | Configurable; do not hardcode in frontend |
| `OPENAI_MODEL` | `openai/gpt-oss-120b` | Default hosted model |
| `ARCHITECT_MODEL` | `openai/gpt-oss-20b` | Faster planning model |
| `CODER_MODEL` | `openai/gpt-oss-120b` | Strongest coding model |
| `REVIEWER_MODEL` | `openai/gpt-oss-20b` | Faster audit model |
| `CORS_ORIGINS` | actual frontend origin(s) | Allowed browser origins |
| `BACKEND_URL` | actual FastAPI base URL | Frontend-to-backend connection setting |
| `EXECUTION_BACKEND` | `local` or `docker` | Sandbox backend choice |

For Northflank, set these values in the service Environment/Secrets configuration. The repository intentionally does not contain a production backend URL.

### Recommended Groq role split

AegisCode supports per-agent model overrides. Using GPT-OSS 20B for Architect/Reviewer and GPT-OSS 120B for Coder reduces latency and avoids spending the entire daily token budget on every agent role while preserving the strongest model for code generation.

---

## 2. Local Testing

Run the backend and frontend locally with the environment configured from `.env.example`.

```bash
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py
```

Set:

```text
BACKEND_URL=http://localhost:8000
```

---

## 3. Northflank Deployment

AegisCode is deployment-platform agnostic and uses environment variables for all service endpoints.

### Backend service

Configure:

- `DATABASE_URL` — persistent PostgreSQL database
- `OPENAI_API_KEY` — secret
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `ARCHITECT_MODEL`
- `CODER_MODEL`
- `REVIEWER_MODEL`
- `CORS_ORIGINS`
- `EXECUTION_BACKEND`
- `WORKSPACE_BASE_DIR`

The backend stores uploaded project archives persistently and can re-hydrate local workspaces after container restarts.

### Frontend service

Configure only the backend connection through:

```text
BACKEND_URL=<your actual FastAPI service URL>
```

Do not place the backend URL in application source code.

---

## 4. Repair Execution Flow

The repair lifecycle is:

```text
Upload ZIP
   ↓
Persistent project archive + local workspace
   ↓
Create Run + baseline pytest
   ↓
Start background LangGraph repair
   ↓
Architect → Coder → targeted/full pytest → Reviewer
   ↓
Verified patch or bounded retry/termination
```

The frontend gives the run-creation request enough time for the bounded baseline pytest operation and reports transport errors instead of silently converting them to a generic connection failure.

---

## 5. Sandbox Security Model

Uploaded Python code is executed through the configured execution backend. The workspace manager enforces path containment and archive validation, while the repair policy prevents agents from modifying protected test/system files.

For production workloads that require stronger tenant isolation, use the Docker execution backend or an equivalent isolated execution service.

---

## 6. Verification & Monitoring

Check health status with the configured backend URL:

```bash
curl "$BACKEND_URL/health"
```

Expected response includes database and LLM availability information.
