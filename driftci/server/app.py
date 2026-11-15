"""FastAPI transport layer and safe optional SPA hosting."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .config import Settings
from .db import Database
from .github import GitHubError
from .remediation import RemediationError
from .repository import RepositoryError
from .service import DriftService, signal_sort


class SignalRequest(BaseModel):
    signal_id: str = Field(min_length=1, max_length=200)


class RepositoryRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class ActionRequest(BaseModel):
    status: Literal["done", "pending"]


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(config.db_path, config.example_dir)
        headers = {"User-Agent": "DriftCI/1.0 (+read-only source intelligence)", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=config.request_timeout, follow_redirects=False, transport=transport, headers=headers) as http:
            app.state.service = DriftService(db, config, http)
            app.state.scan_lock = asyncio.Lock()
            app.state.last_scan_requested = float("-inf")

            async def periodic_watch():
                while True:
                    await asyncio.sleep(config.watch_interval_seconds)
                    try:
                        await gated_scan(lambda: app.state.service.scan(), force=True)
                    except HTTPException:
                        pass  # A browser-triggered scan already owns the shared lock.
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        db.add_activity("watcher", "Scheduled source refresh failed", type(exc).__name__)

            watcher = asyncio.create_task(periodic_watch()) if config.watch_interval_seconds > 0 and not config.offline else None
            app.state.watcher = watcher
            try:
                yield
            finally:
                if watcher:
                    watcher.cancel()
                    with suppress(asyncio.CancelledError):
                        await watcher
                db.close()

    app = FastAPI(title="DriftCI", version="1.0.0", lifespan=lifespan)

    async def gated_scan(operation, force: bool = False):
        """Serialize network refreshes and rate-limit public callers without leaking credentials."""
        lock = app.state.scan_lock

        def check_cooldown():
            if force:
                return
            elapsed = asyncio.get_running_loop().time() - app.state.last_scan_requested
            remaining = config.scan_cooldown_seconds - elapsed
            if remaining > 0:
                raise HTTPException(429, f"A source scan ran recently. Retry in {max(1, int(remaining + .5))} seconds.", headers={"Retry-After": str(max(1, int(remaining + .5)))})

        if lock.locked():
            raise HTTPException(429, "A source scan is already in progress. Retry shortly.", headers={"Retry-After": "3"})
        check_cooldown()
        async with lock:
            check_cooldown()
            app.state.last_scan_requested = asyncio.get_running_loop().time()
            return await operation()

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    def service(request: Request) -> DriftService:
        return request.app.state.service

    @app.get("/api/health")
    def health(request: Request):
        payload = service(request).health()
        payload["watcher"] = {"enabled": config.watch_interval_seconds > 0 and not config.offline, "interval_seconds": config.watch_interval_seconds, "scan_cooldown_seconds": config.scan_cooldown_seconds}
        return payload

    @app.get("/api/bootstrap")
    def bootstrap(request: Request):
        return service(request).bootstrap()

    @app.get("/api/signals")
    def signals(request: Request, kind: Literal["deprecation", "vulnerability", "api", "pricing", "status"] | None = Query(None), severity: Literal["critical", "high", "medium", "low", "info"] | None = Query(None)):
        rows = service(request).db.list_signals()
        return sorted((row for row in rows if (kind is None or row["kind"] == kind) and (severity is None or row["severity"] == severity)), key=signal_sort)

    @app.get("/api/signals/{ident}")
    def signal(ident: str, request: Request):
        row = service(request).db.get_signal(ident)
        if not row:
            raise HTTPException(404, "Signal not found")
        return row

    @app.post("/api/scan")
    async def scan(request: Request):
        return await gated_scan(lambda: service(request).scan())

    @app.post("/api/demo/replay")
    def replay(request: Request):
        return service(request).replay()

    @app.post("/api/demo/reset")
    def reset(request: Request):
        return service(request).reset_demo()

    @app.get("/api/incidents")
    def incidents(request: Request):
        return service(request).incident_payload()

    @app.get("/api/incidents/{ident}/report")
    def incident_report(ident: str, request: Request):
        try:
            report = service(request).incident_report(ident)
            return PlainTextResponse(report, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{ident.replace("/", "_")}-incident.md"'})
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/incidents/{ident}/actions/{action_id}")
    def incident_action(ident: str, action_id: str, body: ActionRequest, request: Request):
        try:
            return service(request).update_incident_action(ident, action_id, body.status)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/remediations")
    def remediate(body: SignalRequest, request: Request):
        try:
            return service(request).create_remediation(body.signal_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/remediations")
    def remediation_list(request: Request):
        return service(request).db.list_remediations()

    @app.get("/api/remediations/{ident}")
    def remediation(ident: str, request: Request):
        row = service(request).db.get_remediation(ident)
        if not row:
            raise HTTPException(404, "Remediation not found")
        return row

    @app.post("/api/remediations/{ident}/approve")
    def approve(ident: str, request: Request):
        try:
            return service(request).approve(ident)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/remediations/{ident}/patch")
    def patch(ident: str, request: Request):
        try:
            filename, content = service(request).export_patch(ident)
            return PlainTextResponse(content, media_type="text/x-patch", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/remediations/{ident}/open-pr")
    async def open_pr(ident: str, request: Request):
        try:
            return await service(request).open_pr(ident)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc
        except GitHubError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.post("/api/repositories/connect")
    async def connect(body: RepositoryRequest, request: Request):
        try:
            return await gated_scan(lambda: service(request).connect(body.url))
        except RepositoryError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.delete("/api/workspace")
    def workspace(request: Request):
        return service(request).reset_demo()

    dist = config.web_dist.resolve()
    if dist.is_dir() and (dist / "index.html").is_file():
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(404)
            candidate = (dist / full_path).resolve()
            if candidate.is_relative_to(dist) and candidate.is_file():
                return FileResponse(candidate)
            if Path(full_path).suffix:
                raise HTTPException(404)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app
