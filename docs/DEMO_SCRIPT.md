# AegisCode 2:30 Minute Capstone Demonstration Script

**Title**: AegisCode — Self-Healing Multi-Agent Software Engineering System  
**Presenter**: Senior Software / AI Engineer  
**Target Duration**: 2 minutes 30 seconds  

---

## ⏱️ Video Timeline & Script

### 0:00 – 0:20 | Introduction & Problem Statement
* **Visual**: Streamlit Frontend Title Screen (`http://localhost:8501`).
* **Audio**: "Welcome to AegisCode — an autonomous, self-healing multi-agent software engineering system built with LangGraph, FastAPI, Streamlit, and Pytest. Traditional LLM code tools require constant human intervention or hallucinate test passes. AegisCode accepts Python projects with failing pytest suites, isolates the workspace, and orchestrates specialized agents to repair bugs autonomously."

### 0:20 – 0:40 | System Architecture
* **Visual**: Architecture Diagram tab / README diagram display.
* **Audio**: "AegisCode follows a strict 3-tier architecture. FastAPI powers the REST backend, SQLite/PostgreSQL tracks state, and LangGraph manages state graph transitions. Uploaded project code never runs directly on the main host; pytest is executed inside an isolated sandbox with authoritative exit codes."

### 0:40 – 1:00 | Project Upload & Initial Failure Detection
* **Visual**: Drag-and-drop `demo_projects/buggy_calculator.zip` into Streamlit. Click "Upload & Initialize", then "Start Autonomous Repair Graph".
* **Audio**: "Let's upload a buggy calculator project containing failing pytest unit tests. AegisCode unpacks the archive into an isolated workspace, initializes Git snapshot tracking, and executes an initial test pass, confirming 2 failing tests."

### 1:00 – 1:30 | Multi-Agent Repair Loop (Architect → Coder → Test)
* **Visual**: Live Iteration Timeline in Streamlit dashboard updating in real-time.
* **Audio**: "The LangGraph graph invokes the **Architect Agent** to analyze the failing stack trace and produce an `ArchitecturePlan`. Next, the **Coder Agent** generates a targeted patch for `calculator.py`. Security policies intercept and verify that no test files or `.env` files are altered. The **Test Node** then executes Pytest, capturing standard output."

### 1:30 – 1:50 | Independent Reviewer Audit
* **Visual**: Reviewer tab expanding in Streamlit showing Git Diff and Approval badge (`APPROVED: True`).
* **Audio**: "Before accepting the repair, the **Reviewer Agent** independently audits the Git diff against initial test logs to assess regression risk. Since all pytest tests pass and the reviewer approves, the decision router terminates the state machine with status `PASSED`."

### 1:50 – 2:10 | Verification & Git Diff Inspection
* **Visual**: Streamlit Git Diff viewer displaying fixed `subtract` and `multiply` functions.
* **Audio**: "Here we see the exact Git diff applied by AegisCode. The buggy math operators were cleanly repaired without modifying any test assertions."

### 2:10 – 2:30 | Security Controls & Evaluation Summary
* **Visual**: Evaluation metrics table & security matrix.
* **Audio**: "AegisCode enforces strict security controls: Zip Slip path traversal protection, prompt injection resistance, loop fingerprint detection, and test protection policies. In benchmark evaluations, AegisCode achieves a 100% success rate on clean algorithmic repair tasks. Thank you!"
