"""Guest identity persistence API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.auth import get_optional_current_user
from backend.core.config import settings
from backend.database.guest import Guest
from backend.database.models import User
from backend.database.session import get_db

router = APIRouter(prefix=f"{settings.api_prefix}/guests", tags=["guests"])


class GuestIdentityRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    session_id: str = Field(min_length=8, max_length=255)


class GuestIdentityResponse(BaseModel):
    guest_id: str
    name: str
    created_at: str
    last_seen_at: str


@router.post(
    "",
    response_model=GuestIdentityResponse,
    status_code=status.HTTP_200_OK,
    summary="Persist or refresh a guest identity",
)
def persist_guest_identity(
    body: GuestIdentityRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> GuestIdentityResponse:
    """Persist a guest name without creating a registered user account."""
    if current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated users do not need a guest identity.",
        )

    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Guest name cannot be empty.",
        )

    guest = db.query(Guest).filter(Guest.session_id == body.session_id).first()
    now = datetime.now(timezone.utc)
    if guest is None:
        guest = Guest(name=name, session_id=body.session_id)
        db.add(guest)
    else:
        guest.name = name
        guest.last_seen_at = now

    db.commit()
    db.refresh(guest)

    return GuestIdentityResponse(
        guest_id=guest.id,
        name=guest.name,
        created_at=guest.created_at.isoformat(),
        last_seen_at=guest.last_seen_at.isoformat(),
    )
