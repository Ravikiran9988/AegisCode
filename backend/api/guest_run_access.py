"""Guest-session authorization for repair-run endpoints.

Guest runs are intentionally not authenticated with JWTs. This middleware binds
all run access to the persistent guest session ID and prevents anonymous or
cross-guest access to run data.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.database.guest import Guest
from backend.database.models import Project, Run
from backend.database.session import SessionLocal


class GuestRunAccessMiddleware:
    """Enforce guest ownership for /api/runs endpoints."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/runs"):
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }

        # JWT-authenticated requests are authorized by the existing runs API.
        if headers.get("authorization"):
            await self.app(scope, receive, send)
            return

        guest_session_id = headers.get("x-guest-session-id")
        if not guest_session_id:
            await JSONResponse(
                {"detail": "Authentication or a valid guest session is required."},
                status_code=401,
            )(scope, receive, send)
            return

        app = scope.get("app")
        session_factory = getattr(getattr(app, "state", None), "db_session_factory", SessionLocal)
        db = session_factory()
        try:
            guest = db.query(Guest).filter(Guest.session_id == guest_session_id).first()
            if guest is None:
                await JSONResponse(
                    {"detail": "Invalid or expired guest session."},
                    status_code=401,
                )(scope, receive, send)
                return

            parts = [p for p in path.split("/") if p]
            run_id = None
            if len(parts) >= 3 and parts[0:2] == ["api", "runs"] and parts[2] not in {"active", "history"}:
                run_id = parts[2]

            method = scope.get("method", "GET").upper()

            # Run creation must use a project owned by the same guest session.
            if method == "POST" and path.rstrip("/") == "/api/runs":
                body = b""
                more_body = True
                while more_body:
                    message = await receive()
                    if message["type"] != "http.request":
                        break
                    body += message.get("body", b"")
                    more_body = message.get("more_body", False)

                async def replay_receive() -> Message:
                    nonlocal body
                    data, body = body, b""
                    return {"type": "http.request", "body": data, "more_body": False}

                try:
                    payload = json.loads(body.decode("utf-8")) if body else {}
                    project_id = payload.get("project_id")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    project_id = None

                project = db.get(Project, project_id) if project_id else None
                if project is None or project.guest_id != guest.id:
                    await JSONResponse(
                        {"detail": "You do not have permission to start a repair for this project."},
                        status_code=403,
                    )(scope, replay_receive, send)
                    return

                await self.app(scope, replay_receive, send)
                return

            # Individual run endpoints must belong to this guest.
            if run_id:
                run = db.get(Run, run_id)
                if run is None:
                    await JSONResponse({"detail": f"Run {run_id!r} not found."}, status_code=404)(scope, receive, send)
                    return
                if run.guest_id != guest.id:
                    await JSONResponse(
                        {"detail": "You do not have permission to access this repair run."},
                        status_code=403,
                    )(scope, receive, send)
                    return

            # History/active/list endpoints are served directly for guests so
            # the existing user-oriented query cannot accidentally expose other
            # guests' runs.
            if method == "GET" and path.rstrip("/") in {"/api/runs", "/api/runs/active", "/api/runs/history"}:
                from backend.api.runs import _format_run_summary

                query_params = parse_qs(
                    scope.get("query_string", b"").decode("latin-1")
                )
                try:
                    limit = max(1, min(int(query_params.get("limit", ["50"])[0]), 100))
                    offset = max(0, int(query_params.get("offset", ["0"])[0]))
                except ValueError:
                    limit, offset = 50, 0

                query = db.query(Run).filter(Run.guest_id == guest.id)
                if path.rstrip("/") == "/api/runs/active":
                    query = query.filter(Run.status.in_(("running", "pending")))
                else:
                    requested_status = query_params.get("status", [None])[0]
                    if requested_status:
                        query = query.filter(Run.status == requested_status)
                runs = (
                    query.order_by(Run.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
                await JSONResponse([_format_run_summary(r) for r in runs])(scope, receive, send)
                return

            await self.app(scope, receive, send)
        finally:
            db.close()
