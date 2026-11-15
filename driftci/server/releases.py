"""Bounded GitHub pull-request ingestion with conditional HTTP and durable events."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import httpx

from .config import Settings
from .db import Database
from .repository import parse_github, safe_relative_path
from .util import safe_excerpt, stable_id, utcnow

_SHA = re.compile(r"^[0-9a-fA-F]{40,64}$")


class ReleaseError(RuntimeError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _integer(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _timestamp(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2000:
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else None


def check_summary(checks: list[dict]) -> dict:
    """Reduce GitHub check states without conflating missing and successful checks."""
    pending = sum(check.get("status") != "completed" for check in checks)
    failed = sum(check.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required", "startup_failure"} for check in checks)
    state = "failed" if failed else "pending" if pending else "passed" if checks else "none"
    return {"state": state, "total": len(checks), "pending": pending, "failed": failed, "passed": sum(check.get("conclusion") in {"success", "neutral", "skipped"} for check in checks)}


class ReleaseWatcher:
    def __init__(self, db: Database, settings: Settings, http: httpx.AsyncClient):
        self.db = db
        self.settings = settings
        self.http = http

    def health(self) -> dict:
        state = self.db.get_meta("github_release_health", {})
        return {
            **state,
            "poll_interval_seconds": self.settings.release_poll_interval_seconds,
            "webhook_configured": bool(self.settings.release_webhook_secret),
            "implementation": "verified webhooks with ETag polling fallback" if self.settings.release_webhook_secret else "public ETag polling; webhooks require a configured secret",
            "credential_usage": "GitHub token is sent only to api.github.com; a separate secret verifies webhooks",
        }

    async def _quota(self) -> dict:
        """Read GitHub's core quota, whose endpoint does not consume that quota."""
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "DriftCI/2.0"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        try:
            async with self.http.stream("GET", "https://api.github.com/rate_limit", headers=headers) as response:
                if response.status_code != 200:
                    return {}
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 64_000:
                        return {}
                core = json.loads(content).get("resources", {}).get("core", {})
                remaining, reset = _integer(core.get("remaining"), -1), _integer(core.get("reset"))
                if remaining < 0 or not reset:
                    return {}
                health = self.db.get_meta("github_release_health", {})
                health.update({"rate_limit_remaining": remaining, "rate_limit_reset_epoch": reset, "rate_limit_reset_at": datetime.fromtimestamp(reset, timezone.utc).isoformat().replace("+00:00", "Z")})
                self.db.set_meta("github_release_health", health)
                return core
        except (httpx.HTTPError, UnicodeError, ValueError, AttributeError):
            return {}

    async def _get(self, url: str) -> tuple[object, str]:
        """Retrieve one bounded API document; a persistent ETag makes quiet polls cheap."""
        if urlparse(url).hostname != "api.github.com":
            raise ValueError("Release metadata is restricted to api.github.com")
        health = self.db.get_meta("github_release_health", {})
        waiting = max(0, _integer(health.get("retry_not_before_epoch")) - int(time.time()))
        if waiting:
            deadline = datetime.fromtimestamp(_integer(health.get("retry_not_before_epoch")), timezone.utc).isoformat().replace("+00:00", "Z")
            raise ReleaseError(f"GitHub retry window is active until {deadline}. Retained release evidence is not current.", waiting)
        etags = self.db.get_meta("github_release_etags", {})
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "DriftCI/2.0"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        if etags.get(url):
            headers["If-None-Match"] = etags[url][:300]
        key = "github-release:" + url
        self.db.increment_meta("github_release_requests")
        try:
            async with self.http.stream("GET", url, headers=headers) as response:
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset = response.headers.get("X-RateLimit-Reset")
                health = self.db.get_meta("github_release_health", {})
                if remaining and remaining.isdigit() and len(remaining) <= 20:
                    health["rate_limit_remaining"] = int(remaining)
                if reset and reset.isdigit() and len(reset) <= 20:
                    health["rate_limit_reset_epoch"] = int(reset)
                    health["rate_limit_reset_at"] = datetime.fromtimestamp(int(reset), timezone.utc).isoformat().replace("+00:00", "Z")
                exhausted = remaining == "0"
                if exhausted:
                    retry_after = max(60, _integer(health.get("rate_limit_reset_epoch")) - int(time.time()))
                    health["retry_after_seconds"] = retry_after
                    health["retry_not_before_epoch"] = max(_integer(health.get("retry_not_before_epoch")), int(time.time()) + retry_after)
                else:
                    health.pop("retry_not_before_epoch", None)
                    health.pop("retry_after_seconds", None)
                self.db.set_meta("github_release_health", health)
                if response.status_code == 304:
                    cached = self.db.cache_get(key)
                    if cached is None:
                        raise ReleaseError("GitHub returned 304 without a retained response")
                    return cached.get("body"), "cached"
                if response.status_code == 404:
                    raise ReleaseError("GitHub repository or pull request was not found. It may be private, renamed or removed; retained workspace evidence is not current.")
                if response.status_code in {403, 429}:
                    if not exhausted or not _integer(reset):
                        core = await self._quota()
                        health = self.db.get_meta("github_release_health", {})
                        exhausted = _integer(core.get("remaining"), 1) == 0
                    retry_value = response.headers.get("Retry-After") or ""
                    retry_after = int(retry_value) if retry_value.isdigit() and len(retry_value) <= 20 else 0
                    if not retry_after:
                        retry_after = max(60, _integer(health.get("rate_limit_reset_epoch")) - int(time.time())) if exhausted else min(3600, max(60, _integer(health.get("retry_after_seconds"), 30) * 2))
                    retry_after = min(86400, max(1, retry_after))
                    health["retry_after_seconds"] = retry_after
                    health["retry_not_before_epoch"] = max(_integer(health.get("retry_not_before_epoch")), int(time.time()) + retry_after)
                    self.db.set_meta("github_release_health", health)
                    raise ReleaseError("GitHub API rate limit reached. Retained release evidence is still available; retry later or configure a least-privilege token.", retry_after)
                if response.status_code >= 400:
                    raise ReleaseError(f"GitHub release metadata returned HTTP {response.status_code}")
                declared = response.headers.get("Content-Length", "")
                if declared.isdigit() and int(declared) > 2_000_000:
                    raise ReleaseError("GitHub release metadata exceeded its 2 MB bound")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 2_000_000:
                        raise ReleaseError("GitHub release metadata exceeded its 2 MB bound")
                body = json.loads(chunks)
                if not isinstance(body, (dict, list)):
                    raise ReleaseError("GitHub returned an invalid release document")
                now = utcnow()
                self.db.cache_set(key, time.time(), {"body": body, "retrieved_at": now})
                if response.headers.get("ETag"):
                    etags[url] = response.headers["ETag"][:300]
                    self.db.set_meta("github_release_etags", etags)
                return body, "live"
        except httpx.HTTPError as exc:
            raise ReleaseError(f"GitHub release request failed: {type(exc).__name__}") from exc
        except (UnicodeError, ValueError) as exc:
            raise ReleaseError("GitHub returned invalid release metadata") from exc

    def _event(self, kind: str, pr: dict, title: str, detail: str, dedupe: str, *, baseline: bool = False, occurred_at: str | None = None, extra: dict | None = None) -> dict:
        repository = self.db.workspace().get("repository", "")
        return {
            "id": stable_id("event", repository, str(pr["number"]), dedupe),
            "kind": kind, "title": safe_excerpt(title, 200), "detail": safe_excerpt(detail, 800),
            "occurred_at": occurred_at or utcnow(), "received_at": utcnow(),
            "pr_id": pr["id"], "pr_number": pr["number"], "url": pr["url"], "head_sha": pr["head_sha"],
            "source": "GitHub", "mode": "observed", "baseline": baseline, **(extra or {}),
        }

    @staticmethod
    def _files(body: object, total: int) -> tuple[list[dict], bool]:
        if not isinstance(body, list):
            return [], False
        files = []
        for item in body[:30]:
            if not isinstance(item, dict):
                continue
            path = safe_relative_path(item.get("filename"))
            if not path:
                continue
            raw_patch = item.get("patch")
            patch = raw_patch if isinstance(raw_patch, str) else ""
            files.append({
                "path": path, "status": safe_excerpt(item.get("status"), 30),
                "additions": _integer(item.get("additions")), "deletions": _integer(item.get("deletions")),
                "changes": _integer(item.get("changes")), "patch": patch[:12_000],
                # GitHub omits patches for binary and large files; a text excerpt is
                # evidence for those exact lines, never a complete file at this head.
                "patch_complete": isinstance(raw_patch, str) and len(patch) <= 12_000,
            })
        # The pull-list endpoint omits changed_files; fewer than 30 results proves
        # that the bounded first page is complete even when that total is unavailable.
        complete = len(files) == len(body) and (len(body) < 30 or len(files) == total) and all(item["patch_complete"] for item in files)
        return files, complete

    @staticmethod
    def _reviews(body: object) -> tuple[list[dict], bool]:
        if not isinstance(body, list):
            return [], False
        reviews = []
        for item in body[:50]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                continue
            state = str(item.get("state") or "").upper()
            if state not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}:
                continue
            reviews.append({
                "id": str(item["id"]), "state": state,
                "reviewer": safe_excerpt((item.get("user") or {}).get("login"), 80) or "GitHub reviewer",
                "submitted_at": _timestamp(item.get("submitted_at")),
                "commit_sha": str(item.get("commit_id") or "") if _SHA.fullmatch(str(item.get("commit_id") or "")) else None,
                "url": _url(item.get("html_url")),
            })
        return reviews, len(body) < 50 and len(reviews) == len(body)

    @staticmethod
    def _checks(body: object) -> tuple[list[dict], bool]:
        if not isinstance(body, dict) or not isinstance(body.get("check_runs"), list):
            return [], False
        checks = []
        for item in body["check_runs"][:50]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                continue
            status = str(item.get("status") or "unknown")
            conclusion = str(item["conclusion"]) if item.get("conclusion") is not None else None
            checks.append({
                "id": str(item["id"]), "name": safe_excerpt(item.get("name"), 120) or "Unnamed check",
                "status": safe_excerpt(status, 30), "conclusion": safe_excerpt(conclusion, 30) if conclusion else None,
                "started_at": _timestamp(item.get("started_at")), "completed_at": _timestamp(item.get("completed_at")),
                "url": _url(item.get("html_url") or item.get("details_url")),
            })
        return checks, _integer(body.get("total_count")) == len(checks) and len(checks) == len(body["check_runs"])

    async def refresh(self, pr_number: int | None = None) -> dict:
        """Reconcile a small recent PR window, fetching details only when they change."""
        workspace = self.db.workspace()
        if workspace.get("source") != "github":
            return {"status": "example", "prs": 0, "detail_pending": 0, "errors": []}
        owner, repo = parse_github(f"https://github.com/{workspace['repository']}")
        root = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
        url = f"{root}/pulls/{pr_number}" if pr_number is not None else f"{root}/pulls?state=all&sort=updated&direction=desc&per_page=10"
        body, mode = await self._get(url)
        rows = [body] if isinstance(body, dict) else body
        errors: list[str] = []
        detailed = 0
        pending = 0
        live_requests = int(mode == "live")
        for row in rows:
            if not isinstance(row, dict):
                continue
            number = _integer(row.get("number"))
            head_sha = str(((row.get("head") or {}).get("sha")) or "")
            state = str(row.get("state") or "")
            if not number or not _SHA.fullmatch(head_sha) or state not in {"open", "closed"}:
                errors.append("Skipped a malformed pull-request record")
                continue
            old = self.db.get_pull_request(f"pr-{number}")
            changed = not old or old.get("updated_at") != _timestamp(row.get("updated_at")) or old.get("head_sha") != head_sha
            # Retry actual request failures. A known first-page or patch-size bound
            # is a stable coverage limit until the PR changes, not a reason to refetch
            # the same oversized diff every polling cycle.
            needs_detail = state == "open" and (
                changed or not (old or {}).get("detail_attempted") or bool((old or {}).get("detail_errors"))
                or ((old or {}).get("check_summary") or {}).get("state") == "pending"
            )
            pr: dict = {
                **(old or {}), "id": f"pr-{number}", "number": number, "state": state,
                "title": safe_excerpt(row.get("title"), 240) or f"Pull request #{number}",
                "url": _url(row.get("html_url")) or f"https://github.com/{owner}/{repo}/pull/{number}",
                "head_sha": head_sha, "head_ref": safe_excerpt((row.get("head") or {}).get("label"), 240),
                "base_ref": safe_excerpt((row.get("base") or {}).get("ref"), 120),
                "author": safe_excerpt((row.get("user") or {}).get("login"), 80) or "Unknown author",
                "draft": row.get("draft") is True,
                "changed_files": _integer(row.get("changed_files"), len(old.get("files", [])) if old else 0),
                "created_at": _timestamp(row.get("created_at")) or utcnow(),
                "updated_at": _timestamp(row.get("updated_at")) or utcnow(),
                "merged_at": _timestamp(row.get("merged_at")), "merged": bool(row.get("merged_at")),
                "repository": f"{owner}/{repo}",
            }
            events: list[dict] = []
            detail_complete = bool(old and not needs_detail and old.get("detail_complete"))
            if needs_detail and detailed < self.settings.release_detail_limit:
                detailed += 1
                detail = await asyncio.gather(
                    self._get(f"{root}/pulls/{number}/files?per_page=30"),
                    self._get(f"{root}/pulls/{number}/reviews?per_page=50"),
                    self._get(f"{root}/commits/{head_sha}/check-runs?per_page=50"),
                    return_exceptions=True,
                )
                live_requests += sum(isinstance(result, tuple) and result[1] == "live" for result in detail)
                names = ("files", "reviews", "checks")
                detail_errors = []
                for name, result in zip(names, detail):
                    if isinstance(result, asyncio.CancelledError):
                        raise result
                    if isinstance(result, BaseException):
                        detail_errors.append(name)
                        errors.append(f"PR #{number} {name}: {result}")
                if detail_errors:
                    pending += 1
                if not isinstance(detail[0], BaseException):
                    pr["files"], files_complete = self._files(detail[0][0], pr["changed_files"])
                    pr["files_complete"] = files_complete
                    pr["changed_files"] = max(pr["changed_files"], len(pr["files"]))
                if not isinstance(detail[1], BaseException):
                    pr["reviews"], pr["reviews_complete"] = self._reviews(detail[1][0])
                if not isinstance(detail[2], BaseException):
                    pr["checks"], pr["checks_complete"] = self._checks(detail[2][0])
                pr["detail_attempted"] = True
                pr["detail_errors"] = detail_errors
                detail_complete = all(pr.get(key) is True for key in ("files_complete", "reviews_complete", "checks_complete"))
            elif needs_detail:
                pending += 1
            pr["detail_complete"] = detail_complete
            pr["check_summary"] = check_summary(pr.get("checks", []))
            checks_hash = hashlib.sha256(json.dumps(pr.get("checks", []), sort_keys=True).encode()).hexdigest()[:16]
            pr["checks_hash"] = checks_hash
            if not old:
                events.append(self._event("pr_indexed", pr, f"PR #{number} added to the release baseline", pr["title"], f"indexed:{head_sha}", baseline=True, occurred_at=pr["updated_at"], extra={"transport_mode": mode}))
            elif old.get("head_sha") != head_sha:
                events.append(self._event("commit", pr, f"New head on PR #{number}", f"{old['head_sha'][:8]} → {head_sha[:8]} · {pr['title']}", f"head:{head_sha}", extra={"previous_sha": old["head_sha"], "transport_mode": mode}))
            elif old.get("updated_at") != pr["updated_at"]:
                events.append(self._event("pr_update", pr, f"Activity on PR #{number}", f"{pr['title']} · GitHub's update timestamp changed.", f"updated:{pr['updated_at']}", extra={"transport_mode": mode}))
            previous_reviews = {item["id"]: item for item in (old or {}).get("reviews", [])}
            for review in pr.get("reviews", []):
                before = previous_reviews.get(review["id"])
                if before == review:
                    continue
                if before is None and not self.db.list_release_events(pr_id=pr["id"], limit=1) and old:
                    continue
                state_label = review["state"].lower().replace("_", " ")
                events.append(self._event("review", pr, f"{review['reviewer']} · {state_label}", f"PR #{number} · {pr['title']}", f"review:{review['id']}:{review['state']}:{review.get('submitted_at')}", baseline=not old, occurred_at=review.get("submitted_at") or pr["updated_at"], extra={"review": review, "transport_mode": mode}))
            if old and old.get("checks_hash") != checks_hash and pr.get("checks"):
                summary = pr["check_summary"]
                state_label = {"passed": "Checks passed", "failed": "Checks need attention", "pending": "Checks running"}.get(summary["state"], "Checks updated")
                events.append(self._event("checks", pr, f"{state_label} on PR #{number}", f"{summary['passed']} passed · {summary['failed']} failed · {summary['pending']} pending · head {head_sha[:8]}", f"checks:{checks_hash}", extra={"check_summary": summary, "transport_mode": mode}))
            self.db.save_pull_request(pr, events)
        return {"status": "live" if live_requests else "cached", "prs": len(rows), "detail_pending": pending, "requests": live_requests, "errors": errors}
