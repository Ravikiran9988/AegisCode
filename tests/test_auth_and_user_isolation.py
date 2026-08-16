"""
Unit & Integration Tests for Phase 1 Authentication and User Isolation.
Verifies registration, login, token validation, protected routes, and data isolation.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from backend.database.models import Base, Project, Run
from backend.database.session import get_db
from backend.main import app

# In-memory test database with StaticPool so all connections share the same memory DB
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_database():
    """Create fresh in-memory schema for each test function."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestSecurityCore:
    def test_password_hashing_and_verification(self):
        pwd = "SecurePassword123!"
        hashed = get_password_hash(pwd)
        assert hashed != pwd
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword123!", hashed) is False
        assert verify_password("", hashed) is False

    def test_jwt_token_generation_and_decoding(self):
        payload = {"sub": "user-uuid-123", "email": "test@kiranverse.tech"}
        token = create_access_token(payload)
        assert isinstance(token, str)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-uuid-123"
        assert decoded["email"] == "test@kiranverse.tech"

    def test_jwt_token_invalid_signature(self):
        invalid_token = "invalid.token.string"
        assert decode_access_token(invalid_token) is None


class TestAuthAPI:
    def test_register_user_success_with_full_name(self, client: TestClient):
        payload = {
            "full_name": "Ada Lovelace",
            "email": "ada@kiranverse.tech",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "ada@kiranverse.tech"
        assert data["user"]["full_name"] == "Ada Lovelace"
        assert data["user"]["name"] == "Ada Lovelace"

    def test_register_user_success_with_auth_alias_route(self, client: TestClient):
        payload = {
            "full_name": "Katherine Johnson",
            "email": "kjohnson@kiranverse.tech",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "kjohnson@kiranverse.tech"

    def test_register_user_invalid_email_format(self, client: TestClient):
        payload = {
            "full_name": "Ada Lovelace",
            "email": "not-an-email",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "valid email" in res.json()["detail"].lower()

    def test_register_user_mismatched_passwords(self, client: TestClient):
        payload = {
            "full_name": "Ada Lovelace",
            "email": "ada@kiranverse.tech",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "Passwords do not match" in res.json()["detail"]

    def test_register_user_short_password(self, client: TestClient):
        payload = {
            "full_name": "Ada Lovelace",
            "email": "ada@kiranverse.tech",
            "password": "short",
            "confirm_password": "short",
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code in (400, 422)

    def test_register_duplicate_email_rejected_with_409(self, client: TestClient):
        payload = {
            "full_name": "Ada Lovelace",
            "email": "ada@kiranverse.tech",
            "password": "Password123!",
            "confirm_password": "Password123!",
        }
        res1 = client.post("/api/auth/register", json=payload)
        assert res1.status_code == 201

        res2 = client.post("/api/auth/register", json=payload)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]

    def test_login_user_success(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={
                "full_name": "Alan Turing",
                "email": "alan@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        login_res = client.post(
            "/api/auth/login",
            json={"email": "alan@kiranverse.tech", "password": "Password123!"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "alan@kiranverse.tech"
        assert data["user"]["full_name"] == "Alan Turing"

    def test_login_user_via_auth_alias_route(self, client: TestClient):
        # Login via /auth/login alias
        client.post(
            "/api/auth/register",
            json={
                "full_name": "Claude Shannon",
                "email": "shannon@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        login_res = client.post(
            "/auth/login",
            json={"email": "shannon@kiranverse.tech", "password": "Password123!"},
        )
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

    def test_login_invalid_password(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={
                "name": "Alan Turing",
                "email": "alan@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        login_res = client.post(
            "/api/auth/login",
            json={"email": "alan@kiranverse.tech", "password": "WrongPassword123!"},
        )
        assert login_res.status_code == 401
        assert "Invalid email or password" in login_res.json()["detail"]

    def test_get_current_user_profile(self, client: TestClient):
        reg = client.post(
            "/api/auth/register",
            json={
                "name": "Grace Hopper",
                "email": "grace@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        ).json()
        token = reg["access_token"]

        me_res = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["name"] == "Grace Hopper"
        assert me_data["email"] == "grace@kiranverse.tech"

    def test_get_current_user_unauthorized_without_token(self, client: TestClient):
        res = client.get("/api/auth/me")
        assert res.status_code == 401


class TestUserDataIsolation:
    def _create_zip_buffer(self) -> io.BytesIO:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("test_sample.py", "def test_sample(): assert 1 == 1\n")
        buf.seek(0)
        return buf

    def test_user_runs_isolated_between_accounts(self, client: TestClient):
        reg_a = client.post(
            "/api/auth/register",
            json={
                "name": "User Alpha",
                "email": "alpha@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        ).json()
        token_a = reg_a["access_token"]
        user_a_id = reg_a["user"]["id"]

        reg_b = client.post(
            "/api/auth/register",
            json={
                "name": "User Beta",
                "email": "beta@kiranverse.tech",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        ).json()
        token_b = reg_b["access_token"]

        db = TestingSessionLocal()
        proj_a = Project(
            user_id=user_a_id,
            name="alpha-project",
            original_filename="alpha.zip",
            workspace_path="/tmp/test-alpha",
            file_count=2,
            size_bytes=100,
        )
        db.add(proj_a)
        db.flush()

        run_a = Run(
            user_id=user_a_id,
            project_id=proj_a.id,
            status="passed",
            max_iterations=5,
            current_iteration=1,
        )
        db.add(run_a)
        db.commit()
        run_a_id = run_a.id
        db.close()

        res_a = client.get("/api/runs", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.status_code == 200
        runs_a = res_a.json()
        assert len(runs_a) == 1
        assert runs_a[0]["run_id"] == run_a_id

        res_b = client.get("/api/runs", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.status_code == 200
        runs_b = res_b.json()
        assert len(runs_b) == 0

        res_b_direct = client.get(
            f"/api/runs/{run_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res_b_direct.status_code == 403
