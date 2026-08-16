"""
POST /api/projects/upload

Accepts a Python project as a ZIP archive, validates it, extracts it
into an isolated workspace, and persists project metadata to the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_optional_current_user
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Project, User
from backend.database.session import get_db
from backend.execution.workspace import WorkspaceError, WorkspaceManager, ZipValidationError
from backend.tools.git_tools import init_repo

logger = get_logger(__name__)

router = APIRouter(prefix=f"{settings.api_prefix}/projects", tags=["projects"])


class ProjectUploadResponse(BaseModel):
    project_id: str
    name: str
    file_count: int
    size_bytes: int
    workspace_id: str
    uploaded_at: str
    message: str


@router.post(
    "/upload",
    response_model=ProjectUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a Python project ZIP for repair",
)
async def upload_project(
    file: UploadFile = File(..., description="Python project as a .zip archive"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> ProjectUploadResponse:
    """
    Upload and validate a Python project ZIP.

    - Enforces size and format limits.
    - Prevents ZIP path traversal (Zip Slip).
    - Extracts into an isolated workspace.
    - Initialises a git snapshot so diffs can be computed later.
    - Persists project metadata to the database.
    """
    # ── File type guard ───────────────────────────────────────────────────────
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .zip files are accepted",
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {len(data):,} bytes exceeds the "
                f"{settings.max_upload_size_mb} MB limit"
            ),
        )

    # ── Workspace creation + extraction ───────────────────────────────────────
    workspace = WorkspaceManager.create(base_dir=settings.workspace_path)
    logger.info(
        "Created workspace %s for upload: %s", workspace.workspace_id, file.filename
    )

    try:
        project_path = workspace.extract_project(data)
        workspace.set_project_root(project_path)
    except ZipValidationError as exc:
        workspace.cleanup()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"ZIP validation failed: {exc}",
        ) from exc
    except WorkspaceError as exc:
        workspace.cleanup()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Extraction failed: {exc}",
        ) from exc

    # ── Git snapshot ──────────────────────────────────────────────────────────
    init_repo(project_path)

    # ── Count files ───────────────────────────────────────────────────────────
    file_count = sum(1 for _ in project_path.rglob("*.py"))

    # ── Persist to DB ─────────────────────────────────────────────────────────
    project_name = file.filename.removesuffix(".zip")
    project = Project(
        user_id=current_user.id if current_user else None,
        name=project_name,
        original_filename=file.filename,
        workspace_path=str(workspace.get_workspace_path()),
        file_count=file_count,
        size_bytes=len(data),
    )
    db.add(project)
    db.flush()  # get project.id before commit (session commits in get_db)

    logger.info(
        "Project uploaded: id=%s name=%r files=%d bytes=%d",
        project.id, project_name, file_count, len(data),
    )

    return ProjectUploadResponse(
        project_id=project.id,
        name=project_name,
        file_count=file_count,
        size_bytes=len(data),
        workspace_id=workspace.workspace_id,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        message=f"Project uploaded successfully. {file_count} Python file(s) found.",
    )
