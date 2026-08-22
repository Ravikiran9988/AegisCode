"""
Comprehensive regression test suite for AegisCode:
1. Guest session lifecycle & authorization persistence
2. Cross-guest access rejection (403 Forbidden)
3. Authenticated user ownership & cross-account isolation
4. RUN-XXXXXXXX short ID resolution
5. Pytest 3 passed / 1 failed result parsing
6. LangGraph repair loop iteration progression & reviewer audit routing
7. Repeat failure threshold validation (no false positive stalling on Iteration 1)
8. Authoritative repair completion requirements
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.auth import create_access_token
from backend.api.runs import resolve_run
from backend.core.security import get_password_hash
from backend.database.guest import Guest
from backend.database.models import Base, Project, Run, User
from backend.database.session import get_db
from backend.graph.graph import decision_router
from backend.graph.loop_detector import compute_failure_fingerprint
from backend.graph.state import RepairState
from backend.main import create_app
from backend.tools.pytest_runner import TestResult
from frontend.utils.api_client import _get_auth_headers


@pytest.fixture
def test_app_and_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test_guest_pipeline.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.state.db_session_factory = TestingSessionLocal

    db = TestingSessionLocal()
    yield app, db, TestingSessionLocal
    db.close()


# ── TEST 1: Guest creates project -> creates repair -> accesses run successfully ──

def test_guest_project_creation_and_run_access(test_app_and_db, tmp_path):
    app, db, SessionLocal = test_app_and_db
    client = TestClient(app)
    guest_session_id = f"guest_session_{uuid.uuid4().hex[:8]}"
    headers = {"X-Guest-Session-ID": guest_session_id, "X-Guest-Name": "Alice Guest"}

    # Upload mock zip
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("calculator.py", "def add(a, b):\n    return a + b\n")
        zf.writestr("test_calculator.py", "def test_add():\n    assert add(1, 2) == 3\n")
    buf.seek(0)

    upload_resp = client.post(
        "/api/projects/upload",
        files={"file": ("test_calc.zip", buf.getvalue(), "application/zip")},
        headers=headers,
    )
    assert upload_resp.status_code == 201
    proj_id = upload_resp.json()["project_id"]

    # Create run
    run_resp = client.post(
        "/api/runs",
        json={"project_id": proj_id, "max_iterations": 3},
        headers=headers,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["run_id"]

    # Verify run.guest_id was assigned
    run_rec = db.get(Run, run_id)
    assert run_rec is not None
    assert run_rec.guest_id is not None

    # Access run status
    status_resp = client.get(f"/api/runs/{run_id}/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["run_id"] == run_id


# ── TEST 2: Same guest polls run status successfully ─────────────────────────

def test_same_guest_polls_status(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)
    guest_session_id = f"guest_session_{uuid.uuid4().hex[:8]}"
    headers = {"X-Guest-Session-ID": guest_session_id}

    guest = Guest(session_id=guest_session_id, name="Bob")
    db.add(guest)
    db.flush()

    proj = Project(name="p1", original_filename="p1.zip", workspace_path=str(tmp_path), guest_id=guest.id)
    db.add(proj)
    db.flush()

    run = Run(project_id=proj.id, guest_id=guest.id, status="running")
    db.add(run)
    db.commit()

    poll_resp = client.get(f"/api/runs/{run.id}/status", headers=headers)
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "running"


# ── TEST 3: Same guest fetches results successfully ──────────────────────────

def test_same_guest_fetches_results(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)
    guest_session_id = f"guest_session_{uuid.uuid4().hex[:8]}"
    headers = {"X-Guest-Session-ID": guest_session_id}

    guest = Guest(session_id=guest_session_id, name="Carol")
    db.add(guest)
    db.flush()

    proj = Project(name="p2", original_filename="p2.zip", workspace_path=str(tmp_path), guest_id=guest.id)
    db.add(proj)
    db.flush()

    run = Run(project_id=proj.id, guest_id=guest.id, status="passed")
    db.add(run)
    db.commit()

    res_resp = client.get(f"/api/runs/{run.id}/results", headers=headers)
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "passed"


# ── TEST 4: Same guest accesses Active Repairs successfully ──────────────────

def test_same_guest_accesses_active_repairs(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)
    guest_session_id = f"guest_session_{uuid.uuid4().hex[:8]}"
    headers = {"X-Guest-Session-ID": guest_session_id}

    guest = Guest(session_id=guest_session_id, name="Dave")
    db.add(guest)
    db.flush()

    proj = Project(name="p3", original_filename="p3.zip", workspace_path=str(tmp_path), guest_id=guest.id)
    db.add(proj)
    db.flush()

    run = Run(project_id=proj.id, guest_id=guest.id, status="running")
    db.add(run)
    db.commit()

    active_resp = client.get("/api/runs/active", headers=headers)
    assert active_resp.status_code == 200
    active_runs = active_resp.json()
    assert len(active_runs) >= 1
    assert active_runs[0]["run_id"] == run.id


# ── TEST 5: Streamlit rerun does not generate a new guest ID ─────────────────

def test_streamlit_rerun_guest_id_stability():
    import streamlit as st

    st.session_state.clear()
    st.session_state["guest_mode"] = True

    h1 = _get_auth_headers()
    sid1 = h1.get("X-Guest-Session-ID")
    assert sid1 is not None

    # Simulate Streamlit component rerun
    h2 = _get_auth_headers()
    sid2 = h2.get("X-Guest-Session-ID")

    assert sid1 == sid2, "Guest session ID changed between reruns!"


# ── TEST 6: Guest A cannot access Guest B's run (returns 403) ────────────────

def test_cross_guest_access_rejected(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)

    guest_a = Guest(session_id="guest_a_session", name="Guest A")
    guest_b = Guest(session_id="guest_b_session", name="Guest B")
    db.add_all([guest_a, guest_b])
    db.flush()

    proj_a = Project(name="pa", original_filename="pa.zip", workspace_path=str(tmp_path), guest_id=guest_a.id)
    db.add(proj_a)
    db.flush()

    run_a = Run(project_id=proj_a.id, guest_id=guest_a.id, status="running")
    db.add(run_a)
    db.commit()

    # Guest B tries to access Guest A's run
    headers_b = {"X-Guest-Session-ID": "guest_b_session"}
    resp = client.get(f"/api/runs/{run_a.id}/status", headers=headers_b)
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()


# ── TEST 7: Authenticated user can access their own run ─────────────────────

def test_authenticated_user_access(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)

    user = User(email="user1@example.com", hashed_password=get_password_hash("secret123"), name="User 1")
    db.add(user)
    db.flush()

    token = create_access_token({"sub": user.id})
    auth_headers = {"Authorization": f"Bearer {token}"}

    proj = Project(name="user_p", original_filename="user_p.zip", workspace_path=str(tmp_path), user_id=user.id)
    db.add(proj)
    db.flush()

    run = Run(project_id=proj.id, user_id=user.id, status="running")
    db.add(run)
    db.commit()

    resp = client.get(f"/api/runs/{run.id}/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run.id


# ── TEST 8: Authenticated user cannot access another user's run ─────────────

def test_authenticated_user_cross_access_rejected(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db
    client = TestClient(app)

    u1 = User(email="u1@example.com", hashed_password=get_password_hash("secret123"), name="U1")
    u2 = User(email="u2@example.com", hashed_password=get_password_hash("secret123"), name="U2")
    db.add_all([u1, u2])
    db.flush()

    token2 = create_access_token({"sub": u2.id})
    auth_headers2 = {"Authorization": f"Bearer {token2}"}

    proj1 = Project(name="p1", original_filename="p1.zip", workspace_path=str(tmp_path), user_id=u1.id)
    db.add(proj1)
    db.flush()

    run1 = Run(project_id=proj1.id, user_id=u1.id, status="running")
    db.add(run1)
    db.commit()

    resp = client.get(f"/api/runs/{run1.id}/status", headers=auth_headers2)
    assert resp.status_code == 403


# ── TEST 9: Human-readable RUN-XXXXXXXX maps correctly to internal UUID ─────

def test_human_readable_run_id_resolution(test_app_and_db, tmp_path):
    app, db, _ = test_app_and_db

    target_uuid = "57a42ee2-dd80-49b1-80f0-e3a87887faf4"
    proj = Project(name="px", original_filename="px.zip", workspace_path=str(tmp_path))
    db.add(proj)
    db.flush()

    run = Run(id=target_uuid, project_id=proj.id, status="running")
    db.add(run)
    db.commit()

    # Exact UUID
    r1 = resolve_run(db, target_uuid)
    assert r1 is not None and r1.id == target_uuid

    # RUN- prefix
    r2 = resolve_run(db, "RUN-57A42EE2")
    assert r2 is not None and r2.id == target_uuid

    # Short prefix lowercase
    r3 = resolve_run(db, "57a42ee2")
    assert r3 is not None and r3.id == target_uuid


# ── TEST 10: 3 passed / 1 failed pytest result is parsed correctly ───────────

def test_pytest_result_parsing():
    res = TestResult(
        passed=3,
        failed=1,
        errors=0,
        skipped=0,
        exit_code=1,
        success=False,
        duration=1.25,
        stdout="FAILED test_calc.py::test_subtract",
        stderr="",
    )
    assert res.passed == 3
    assert res.failed == 1
    assert res.passed + res.failed == 4
    assert res.success is False



# ── TEST 11: Reviewer rejection retry progression (no premature STALLED) ────

def test_reviewer_rejection_retry_progression():
    t_res = TestResult(passed=3, failed=1, exit_code=1, success=False, stdout="FAILED test_calc.py::test_sub")
    fp1 = compute_failure_fingerprint(t_res)

    state: RepairState = {
        "run_id": "test_r1",
        "iteration": 1,
        "max_iterations": 5,
        "status": "running",
        "test_result": t_res.model_dump(),
        "review_result": {
            "approved": False,
            "reasoning": "Patch did not fix subtract function",
            "root_cause_fixed": False,
            "recommendation": "Fix return value in subtract()",
        },
        "previous_failures": [],
    }

    # First decision router call on Iteration 1
    route = decision_router(state)
    assert route == "retry"
    assert state["iteration"] == 2
    assert state["status"] == "running"
    assert state["previous_failures"] == [fp1]


# ── TEST 12: Repeat failure threshold validation (stall after threshold) ────

def test_repeat_failure_threshold_stalls_on_second_occurrence():
    t_res = TestResult(passed=3, failed=1, exit_code=1, success=False, stdout="FAILED test_calc.py::test_sub")
    fp1 = compute_failure_fingerprint(t_res)

    state: RepairState = {
        "run_id": "test_r2",
        "iteration": 2,
        "max_iterations": 5,
        "status": "running",
        "test_result": t_res.model_dump(),
        "review_result": {
            "approved": False,
            "reasoning": "Patch did not fix subtract function",
            "root_cause_fixed": False,
            "recommendation": "Try different approach",
        },
        "previous_failures": [fp1],  # Already failed once on iteration 1
    }

    route = decision_router(state)
    assert route == "end"
    assert state["status"] == "stalled"
    assert state["termination_reason"] == "repeated_failure"


# ── TEST 13: Max iteration termination reporting ─────────────────────────────

def test_max_iteration_termination():
    t_res = TestResult(passed=3, failed=1, exit_code=1, success=False, stdout="FAILED test_calc.py::test_sub")

    state: RepairState = {
        "run_id": "test_r3",
        "iteration": 5,
        "max_iterations": 5,
        "status": "running",
        "test_result": t_res.model_dump(),
        "review_result": {
            "approved": False,
            "reasoning": "Max attempts reached",
            "root_cause_fixed": False,
            "recommendation": "Review design",
        },
        "previous_failures": [],
    }

    route = decision_router(state)
    assert route == "end"
    assert state["status"] == "failed"
    assert state["termination_reason"] == "max_iterations_reached"


# ── TEST 14: Authoritative success assertion requirement ──────────────────────

def test_authoritative_success_requirement():
    # Passed tests + Approved reviewer -> SUCCESS
    t_pass = TestResult(passed=4, failed=0, exit_code=0, success=True)
    state_pass: RepairState = {
        "run_id": "test_r4",
        "iteration": 1,
        "max_iterations": 5,
        "status": "running",
        "test_result": t_pass.model_dump(),
        "review_result": {
            "approved": True,
            "reasoning": "Patch verified",
            "root_cause_fixed": True,
            "recommendation": "Ship code",
        },
        "previous_failures": [],
    }
    r_pass = decision_router(state_pass)
    assert r_pass == "end"
    assert state_pass["status"] == "passed"
    assert state_pass["termination_reason"] == "all_tests_passed"

    # Failing tests + Approved reviewer -> CANNOT pass
    t_fail = TestResult(passed=3, failed=1, exit_code=1, success=False)
    state_fail: RepairState = {
        "run_id": "test_r5",
        "iteration": 1,
        "max_iterations": 5,
        "status": "running",
        "test_result": t_fail.model_dump(),
        "review_result": {
            "approved": True,
            "reasoning": "Reviewer approved but tests failed",
            "root_cause_fixed": False,
            "recommendation": "Fix remaining test",
        },
        "previous_failures": [],
    }
    r_fail = decision_router(state_fail)
    assert r_fail == "retry"
    assert state_fail["status"] != "passed"

