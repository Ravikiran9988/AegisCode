"""
SQLAlchemy ORM models for AegisCode.

Four tables:
    projects   – uploaded Python projects (metadata + path)
    runs       – a single repair session for a project
    iterations – one repair cycle within a run
    events     – fine-grained agent activity log (append-only)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ────────────────────────────────────────────────────────────────────────────
# User
# ────────────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    projects: Mapped[list[Project]] = relationship("Project", back_populates="user")
    runs: Mapped[list[Run]] = relationship("Run", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ────────────────────────────────────────────────────────────────────────────
# Project
# ────────────────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    workspace_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="projects")
    runs: Mapped[list[Run]] = relationship("Run", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


# ────────────────────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────────────────────

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending | running | passed | failed | error
    max_iterations: Mapped[int] = mapped_column(Integer, default=5)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="runs")
    project: Mapped[Project] = relationship("Project", back_populates="runs")
    iterations: Mapped[list[Iteration]] = relationship("Iteration", back_populates="run")
    events: Mapped[list[Event]] = relationship("Event", back_populates="run")

    def __repr__(self) -> str:
        return f"<Run id={self.id} status={self.status!r}>"


# ────────────────────────────────────────────────────────────────────────────
# Iteration
# ────────────────────────────────────────────────────────────────────────────

class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Agent outputs stored as JSON blobs (populated by later phases)
    architecture_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_changes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    test_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Quick-access fields
    tests_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="iterations")

    def __repr__(self) -> str:
        return f"<Iteration run={self.run_id} #={self.iteration_number}>"


# ────────────────────────────────────────────────────────────────────────────
# Event  (append-only log)
# ────────────────────────────────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    iteration_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g. tool_call | agent_output | error | status_change
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    run: Mapped[Run] = relationship("Run", back_populates="events")

    def __repr__(self) -> str:
        return f"<Event run={self.run_id} agent={self.agent!r} type={self.event_type!r}>"
