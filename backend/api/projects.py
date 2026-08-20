"""Project upload API with authenticated-user and guest-session ownership."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.api.auth import get_optional_current_user
from backend.core.config import settings
from backend.database.guest import Guest
from backend.database.models import Project, User
from backend.database.session import get_db
from backend.execution.workspace import WorkspaceError, WorkspaceManager, ZipValidationError
from backend.tools.git_tools import init_repo
router = APIRouter(prefix=f"{settings.api_prefix}/projects", tags=["projects"])
class ProjectUploadResponse(BaseModel):
    project_id: str
    name: str
    file_count: int
    size_bytes: int
    workspace_id: str
    uploaded_at: str
    message: str
@router.post("/upload", response_model=ProjectUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_project(
    file: UploadFile = File(..., description="Python project as a .zip archive"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    guest_session_id: str | None = Header(default=None, alias="X-Guest-Session-ID"),
    guest_name: str | None = Header(default=None, alias="X-Guest-Name"),
) -> ProjectUploadResponse:
    guest = None
    if current_user is None:
        if not guest_session_id or not guest_name or not guest_name.strip():
            raise HTTPException(status_code=401, detail="Authentication or a valid guest session is required.")
        guest = db.query(Guest).filter(Guest.session_id == guest_session_id).first()
        if guest is None:
            guest = Guest(name=guest_name.strip(), session_id=guest_session_id)
            db.add(guest); db.flush()
        else:
            guest.name = guest_name.strip(); guest.last_seen_at = datetime.now(timezone.utc)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=415, detail="Only .zip files are accepted")
    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File size {len(data):,} bytes exceeds the {settings.max_upload_size_mb} MB limit")
    workspace = WorkspaceManager.create(base_dir=settings.workspace_path)
    try:
        project_path = workspace.extract_project(data); workspace.set_project_root(project_path); init_repo(project_path)
    except ZipValidationError as exc:
        workspace.cleanup(); raise HTTPException(status_code=422, detail=f"ZIP validation failed: {exc}") from exc
    except WorkspaceError as exc:
        workspace.cleanup(); raise HTTPException(status_code=422, detail=f"Extraction failed: {exc}") from exc
    file_count = sum(1 for _ in project_path.rglob("*.py")); project_name = file.filename.removesuffix(".zip")
    project = Project(user_id=current_user.id if current_user else None, guest_id=guest.id if guest else None, name=project_name, original_filename=file.filename, workspace_path=str(workspace.get_workspace_path()), file_count=file_count, size_bytes=len(data))
    db.add(project); db.flush(); db.commit()
    return ProjectUploadResponse(project_id=project.id, name=project_name, file_count=file_count, size_bytes=len(data), workspace_id=workspace.workspace_id, uploaded_at=datetime.now(timezone.utc).isoformat(), message=f"Project uploaded successfully. {file_count} Python file(s) found.")
