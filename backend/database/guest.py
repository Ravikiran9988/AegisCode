"""Persistent guest-session records for AegisCode."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.models import Base


class Guest(Base):
    __tablename__ = "guests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    projects: Mapped[list] = relationship("Project", back_populates="guest")
    runs: Mapped[list] = relationship("Run", back_populates="guest")

    def __repr__(self) -> str:
        return f"<Guest id={self.id} name={self.name!r}>"
