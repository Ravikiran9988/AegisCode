"""
SQLAlchemy ORM models for AegisCode.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, event, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    full_name: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    projects: Mapped[list[Project]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship("Run", back_populates="user", cascade="all, delete-orphan")

    @property
    def nickname(self) -> str:
        return self.name or self.full_name or ""

    @nickname.setter
    def nickname(self, value: str) -> None:
        self.name = value
        self.full_name = value


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id: Mapped[str | None] = mapped_column(ForeignKey("guests.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    workspace_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    user: Mapped[User | None] = relationship("User", back_populates="projects")
    guest: Mapped[Guest | None] = relationship("Guest", back_populates="projects")
    runs: Mapped[list[Run]] = relationship("Run", back_populates="project", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id: Mapped[str | None] = mapped_column(ForeignKey("guests.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    max_iterations: Mapped[int] = mapped_column(Integer, default=5)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0)
    final_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped[User | None] = relationship("User", back_populates="runs")
    guest: Mapped[Guest | None] = relationship("Guest", back_populates="runs")
    project: Mapped[Project] = relationship("Project", back_populates="runs")
    iterations: Mapped[list[Iteration]] = relationship("Iteration", back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list[Event]] = relationship("Event", back_populates="run", cascade="all, delete-orphan")


@event.listens_for(Run, "before_insert")
def _inherit_project_guest_ownership(_mapper, connection, target: Run) -> None:
    """Ensure a run inherits the guest owner of its project."""
    if target.guest_id is not None or target.user_id is not None:
        return
    guest_id = connection.execute(
        select(Project.guest_id).where(Project.id == target.project_id)
    ).scalar_one_or_none()
    if guest_id is not None:
        target.guest_id = guest_id


class Iteration(Base):
    __tablename__ = "iterations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    architecture_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_changes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    test_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tests_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    run: Mapped[Run] = relationship("Run", back_populates="iterations")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    iteration_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    run: Mapped[Run] = relationship("Run", back_populates="events")
