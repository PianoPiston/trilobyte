"""FastAPI transport layer and safe optional SPA hosting."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import Settings
from .contextdev import validate_watch_url
from .db import Database
from .github import GitHubError
from .remediation import RemediationError
from .repository import RepositoryError
from .service import DriftService, signal_sort
from .util import safe_excerpt, stable_id, utcnow


class SignalRequest(BaseModel):
    signal_id: str = Field(min_length=1, max_length=200)


class RepositoryRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class ActionRequest(BaseModel):
    status: Literal["done", "pending"]


class WatchRequest(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    title: str = Field(default="", max_length=80)


class SignalStateRequest(BaseModel):
    state: Literal["acknowledged", "resolved", "monitoring", "needs_action"]


class ReleaseDecisionRequest(BaseModel):
    decision: Literal["ready", "hold"]
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)


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
            app.state.release_lock = asyncio.Lock()
            app.state.last_release_requested = float("-inf")

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

            async def periodic_releases():
                while True:
                    await asyncio.sleep(config.release_poll_interval_seconds)
                    try:
                        await gated_release(lambda: app.state.service.refresh_releases(), force=True)
                    except HTTPException:
                        pass
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        db.add_activity("watcher", "Release event poll failed", type(exc).__name__)

            watcher = asyncio.create_task(periodic_watch()) if config.watch_interval_seconds > 0 and not config.offline else None
            release_watcher = asyncio.create_task(periodic_releases()) if config.release_poll_interval_seconds > 0 and not config.offline else None
            app.state.watcher = watcher
            app.state.release_watcher = release_watcher
            try:
                yield
            finally:
                for task in (watcher, release_watcher):
                    if task:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                db.close()

    app = FastAPI(title="DriftCI", version="2.0.0", lifespan=lifespan)

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

    async def gated_release(operation, force: bool = False):
        """Release polling shares the full-scan lock to avoid duplicate source work."""
        release_lock, scan_lock = app.state.release_lock, app.state.scan_lock

        def check_cooldown():
            if force:
                return
            elapsed = asyncio.get_running_loop().time() - app.state.last_release_requested
            remaining = config.release_manual_cooldown_seconds - elapsed
            if remaining > 0:
                retry = max(1, int(remaining + .5))
                raise HTTPException(429, f"Release metadata was refreshed recently. Retry in {retry} seconds.", headers={"Retry-After": str(retry)})

        if release_lock.locked():
            raise HTTPException(429, "A release refresh is already in progress.", headers={"Retry-After": "3"})
        if scan_lock.locked():
            raise HTTPException(429, "A full source scan is in progress. Retry shortly.", headers={"Retry-After": "3"})
        check_cooldown()
        async with release_lock:
            async with scan_lock:
                check_cooldown()
                app.state.last_release_requested = asyncio.get_running_loop().time()
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
        payload["watcher"] = {"enabled": config.watch_interval_seconds > 0 and not config.offline, "interval_seconds": config.watch_interval_seconds, "scan_cooldown_seconds": config.scan_cooldown_seconds, "implementation": "local polling with independent Context.dev cache and credit budget"}
        payload["release_stream"].update({
            "enabled": config.release_poll_interval_seconds > 0 and not config.offline,
            "sse_path": "/api/events/stream", "webhook_path": "/api/github/webhook" if config.release_webhook_secret else None,
            "status_cache_ttl_seconds": config.status_cache_ttl_seconds, "status_hot_ttl_seconds": config.status_hot_ttl_seconds,
        })
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

    @app.post("/api/releases/refresh")
    async def refresh_releases(request: Request):
        return await gated_release(lambda: service(request).refresh_releases())

    @app.post("/api/releases/{pr_id}/decision")
    def release_decision(pr_id: str, body: ReleaseDecisionRequest, request: Request):
        if not re.fullmatch(r"pr-[1-9][0-9]{0,8}", pr_id):
            raise HTTPException(404, "Release pull request not found")
        try:
            return service(request).record_release_decision(pr_id, body.decision, body.reviewer, body.note)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/releases/{pr_id}/report")
    def release_report(pr_id: str, request: Request):
        if not re.fullmatch(r"pr-[1-9][0-9]{0,8}", pr_id):
            raise HTTPException(404, "Release pull request not found")
        try:
            filename, report = service(request).release_report(pr_id)
            return PlainTextResponse(report, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/events/stream")
    async def event_stream(request: Request, after: int = Query(0, ge=0, le=9_223_372_036_854_775_807)):
        """Replay and follow monotonically sequenced events; never synthesize web changes."""
        if request.headers.get("last-event-id"):
            try:
                after = int(request.headers["last-event-id"])
            except ValueError as exc:
                raise HTTPException(400, "Last-Event-ID must be the numeric event cursor") from exc
            if after < 0:
                raise HTTPException(400, "Last-Event-ID must be non-negative")

        async def stream():
            cursor = after
            ticks = 0
            yield ": release stream connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                rows = request.app.state.service.db.list_release_events(cursor, limit=200)
                for event in rows:
                    cursor = event["seq"]
                    summary = {key: event.get(key) for key in ("seq", "kind", "title", "pr_number", "signal_id", "baseline", "source")}
                    yield f"id: {cursor}\nevent: update\ndata: {json.dumps(summary, ensure_ascii=False)}\n\n"
                await asyncio.sleep(1)
                ticks += 1
                if ticks >= 15:
                    ticks = 0
                    yield ": keepalive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @app.post("/api/github/webhook")
    async def github_webhook(request: Request):
        """Authenticate, bound and deduplicate a hook before reconciling GitHub state."""
        if not config.release_webhook_secret or config.offline:
            raise HTTPException(503, "GitHub webhooks require DRIFTCI_GITHUB_WEBHOOK_SECRET and live mode")
        declared = request.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > 512_000:
            raise HTTPException(413, "Webhook payload exceeds 512 KB")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 512_000:
                raise HTTPException(413, "Webhook payload exceeds 512 KB")
        supplied = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(config.release_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(401, "Invalid webhook signature")
        delivery = request.headers.get("X-GitHub-Delivery", "")
        event_name = request.headers.get("X-GitHub-Event", "")
        if not re.fullmatch(r"[a-fA-F0-9-]{8,100}", delivery):
            raise HTTPException(400, "Missing or invalid X-GitHub-Delivery")
        if event_name not in {"ping", "pull_request", "pull_request_review", "check_run", "check_suite", "status"}:
            return {"accepted": True, "ignored_event": safe_excerpt(event_name, 60)}
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(400, "Webhook body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(400, "Webhook body must be a JSON object")
        repository = (payload.get("repository") or {}).get("full_name")
        if event_name != "ping" and repository != service(request).db.workspace().get("repository"):
            raise HTTPException(409, "Webhook repository does not match the connected workspace")
        delivery_id = stable_id("event", "github-delivery", delivery)
        db = service(request).db
        if db.has_release_event(delivery_id):
            return {"accepted": True, "duplicate": True, "delivery": delivery}
        pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
        number = pr.get("number")
        pr_number = number if isinstance(number, int) and not isinstance(number, bool) and number > 0 else None
        if event_name != "ping":
            result = await gated_release(lambda: service(request).refresh_releases(pr_number))
            release_source = next((source for source in result["sources"] if source["id"] == "src-github-releases"), None)
            if release_source and release_source.get("status") == "error":
                raise HTTPException(502, "GitHub reconciliation failed; this delivery was not marked complete and can be retried")
        now = utcnow()
        db.add_release_event({
            "id": delivery_id, "kind": "webhook", "title": "Verified GitHub webhook received",
            "detail": f"{event_name} delivery reconciled{(' for PR #' + str(pr_number)) if pr_number else ''}.",
            "occurred_at": now, "received_at": now, "pr_id": f"pr-{pr_number}" if pr_number else None,
            "pr_number": pr_number, "url": pr.get("html_url"), "head_sha": (pr.get("head") or {}).get("sha") if isinstance(pr.get("head"), dict) else None,
            "source": "GitHub webhook", "mode": "verified", "baseline": False, "delivery": delivery,
        })
        return {"accepted": True, "duplicate": False, "delivery": delivery, "pr_number": pr_number}

    @app.post("/api/signals/{ident}/state")
    def signal_state(ident: str, body: SignalStateRequest, request: Request):
        try:
            return service(request).update_signal_state(ident, body.state)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/watches")
    async def add_watch(body: WatchRequest, request: Request):
        try:
            validate_watch_url(body.url, body.title)
            return await gated_scan(lambda: service(request).add_watch(body.url, body.title))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RemediationError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete("/api/watches/{key}")
    def remove_watch(key: str, request: Request):
        try:
            return service(request).remove_watch(key)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

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
            return await gated_scan(lambda: asyncio.wait_for(
                service(request).connect(body.url),
                timeout=config.repository_connect_timeout_seconds,
            ))
        except RepositoryError as exc:
            raise HTTPException(400, str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(504, "Repository connection exceeded its time budget. No complete scan was reported; retry with supported manifests or adjust the server source budgets.") from exc

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
