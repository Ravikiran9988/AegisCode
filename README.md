# AegisCode

**Self-Healing Multi-Agent Software Engineering System**

AegisCode is an autonomous software engineering platform that detects, analyzes, and repairs failing Python projects using a LangGraph-based multi-agent workflow. It combines an Architect, Coder, and Reviewer agent with authoritative Pytest execution, code-diff inspection, observability, and security controls.

## 🚀 Live Demo

**Live Application:** https://aegiscode.kiranverse.tech/

**Demo Video:** https://www.loom.com/share/e73b17e338e84080a97be0ad2d2255ca

## 📦 Repository

**GitHub:** https://github.com/Ravikiran9988/AegisCode

## 🎯 What AegisCode Does

AegisCode accepts a Python project with failing Pytest tests and autonomously works through a repair loop:

```text
Upload Project
     ↓
Initial Pytest Run
     ↓
Architect — Analyze Failure & Plan Repair
     ↓
Coder — Apply Targeted Code Repair
     ↓
Pytest — Execute & Verify
     ↓
Reviewer — Audit Changes & Regression Risk
     ↓
Pass → Complete  |  Fail → Next Iteration
```

The system uses actual Pytest execution results as the source of truth instead of relying on the LLM to claim that a repair works.

## 🤖 Multi-Agent Architecture

- **Architect Agent** — analyzes failures, tracebacks, and project context and produces a repair plan.
- **Coder Agent** — applies targeted changes based on the repair plan.
- **Reviewer Agent** — independently reviews generated changes and checks for regression risks.
- **LangGraph Orchestration** — coordinates the agents and controls iterative repair decisions.

## 🖥️ Platform Features

- Control Center / Overview dashboard
- New Repair project upload workflow
- Active Repair live telemetry
- Repair History
- Agent observability
- Synthesized code diffs
- Pytest execution logs
- System health and telemetry
- Configuration and settings
- Architecture and documentation views

## 🔐 Security

AegisCode includes security-focused controls such as:

- Protected test/system files
- Path traversal prevention
- Prompt injection defenses
- Failure-loop detection
- Isolated execution
- Safe repair boundaries

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Backend:** FastAPI
- **Agent Orchestration:** LangGraph
- **LLM:** Groq-compatible LLM integration
- **Testing:** Pytest
- **Execution:** Docker / sandboxed execution
- **Language:** Python

## 📁 Project Structure

```text
AegisCode/
├── backend/          # FastAPI backend and repair workflow
├── frontend/         # Streamlit developer dashboard
├── demo_projects/    # Demonstration projects
├── evaluation/       # Evaluation and benchmarking
├── docs/             # Architecture and project documentation
├── Dockerfile
├── Dockerfile.frontend
├── docker-compose.yml
├── render.yaml
├── pyproject.toml
└── README.md
```

## 🎥 Demo

The live demonstration shows a deliberately broken Python project being uploaded, analyzed, repaired, tested, reviewed, and verified through the AegisCode workflow.

**Watch the 2-minute demo:** https://www.loom.com/share/e73b17e338e84080a97be0ad2d2255ca

## 🌐 Links

| Resource | Link |
|---|---|
| Live App | https://aegiscode.kiranverse.tech/ |
| GitHub | https://github.com/Ravikiran9988/AegisCode |
| Demo Video | https://www.loom.com/share/e73b17e338e84080a97be0ad2d2255ca |

## 👨‍💻 Author

**Medicharla Ravi Kiran**

GitHub: https://github.com/Ravikiran9988
