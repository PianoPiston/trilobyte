"""Context.dev-hosted monitors. Runs and changes come from the remote service, not local polling."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import httpx

from .db import Database
from .util import safe_excerpt, utcnow

MONITOR_REPO = re.compile(r"^driftci-repo:([a-z0-9_.-]+)$", re.I)
MONITOR_ID = re.compile(r"^mon_[a-zA-Z0-9_-]+$")


def repository_tag(owner: str, repository: str) -> str:
    """Tags are fixed, validated repository identifiers, never user-provided query fragments."""
    if owner == "example":
        return "driftci-repo:junction-orders-ai"
    return f"driftci-repo:{owner.lower()}-{repository.lower()}"


def monitor_definition(repository: str, owner: str) -> dict:
    """Dependency-sensitive official-source searches, executed and scheduled by Context.dev."""
    slug = repository.lower()
    if owner.lower() == "nodejs" and slug == "node":
        query = 'site:nodejs.org/en/blog/vulnerability "Node.js"'
        name = "DriftCI · Node.js security advisories"
        instructions = "Detect newly published Node.js security releases, vulnerability announcements, CVEs and GHSA advisories. Include affected versions and fixes; exclude routine releases and duplicates."
    elif owner.lower() == "vercel" and slug == "ai":
        query = 'site:ai-sdk.dev/advisories OR site:vercel.com/changelog "AI SDK" security OR vulnerability'
        name = "DriftCI · Vercel AI SDK advisories"
        instructions = "Detect new security advisories, vulnerabilities, affected AI SDK packages, breaking dependency changes and required upgrades. Exclude ordinary marketing announcements."
    else:
        query = f'"{owner.lower()}/{slug}" security advisory OR vulnerability OR SDK deprecation'
        name = f"DriftCI · {owner}/{repository} security & dependency changes"
        instructions = "Detect official security advisories, dependency vulnerabilities, supported-version changes and SDK or model deprecations relevant to this repository. Exclude marketing, duplicate results and unsupported vulnerability claims."
    return {
        "name": name[:200],
        "tags": ["driftci", repository_tag(owner, repository)],
        "target": {"type": "search", "query": query[:1000]},
        "change_detection": {"type": "semantic", "instructions": instructions[:2000], "confidence_threshold": 0.8},
        "schedule": {"kind": "interval", "interval": 1, "unit": "hours"},
    }


def public_change(change: dict) -> dict:
    """Retain cited results and measured change diffs; such text remains untrusted data downstream."""
    allowed = (
        "id", "monitor_id", "run_id", "target_type", "change_detection_type", "title", "summary",
        "importance", "confidence", "url", "diff", "before_text_excerpt", "after_text_excerpt",
        "detected_at", "tags", "evidence", "matched_urls", "matched_url_count", "removed_urls",
    )
    return {key: value for key, value in change.items() if key in allowed}


class ContextMonitors:
    """Small REST client; account metadata reads do not consume Context.dev credits."""

    def __init__(self, db: Database, http: httpx.AsyncClient, api_key: str | None, daily_budget: int, ordinary_usage=None):
        self.db = db
        self.http = http
        self.api_key = api_key
        self.daily_budget = max(0, daily_budget)
        self.ordinary_usage = ordinary_usage or self._ordinary_usage

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.api_key:
            return {"configured": False, "error": "CONTEXTDEV_API_KEY is required for Context.dev-hosted monitoring."}
        response = await self.http.request(
            method, f"https://api.context.dev/v1{path}", json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"}, timeout=12, follow_redirects=False,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Context.dev returned an invalid monitor response")
        return data

    def budget(self) -> dict:
        state = self.db.get_meta("context_monitor_accounting", {})
        today = datetime.now(timezone.utc).date().isoformat()
        if state.get("date") != today:
            return {"reserved": 0, "spent": 0}
        return {"reserved": int(state.get("reserved", 0)), "spent": int(state.get("spent", 0))}

    def _accounting(self, resources: list[dict], actual: int | None = None) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()
        active = [resource for resource in resources if resource.get("status") == "active"]
        reserved = len(active) * 48
        old = self.db.get_meta("context_monitor_accounting", {})
        spent = actual if actual is not None else int(old.get("spent", 0)) if old.get("date") == today else 0
        state = {
            "date": today, "reserved": max(0, reserved - spent), "spent": spent,
            "active": len(active), "updated_at": utcnow(),
        }
        self.db.set_meta("context_monitor_accounting", state)
        return state

    def _ordinary_usage(self) -> dict:
        current = self.db.get_meta("context_daily", {})
        today = datetime.now(timezone.utc).date().isoformat()
        ordinary = int(current.get("credits", 0)) if current.get("date") == today else 0
        accounting = self.budget()
        return {"daily_available": max(0, self.daily_budget - ordinary - accounting["spent"] - accounting["reserved"])}

    def _reserve_creation(self, resources: list[dict]) -> bool:
        self._accounting(resources)
        return int(self.ordinary_usage()["daily_available"]) >= 48

    async def _list(self, tag: str) -> list[dict]:
        result = await self._request("GET", f"/monitors?tag={tag}&limit=100")
        if result.get("configured") is False:
            return []
        values = result.get("data", [])
        if not isinstance(values, list):
            raise ValueError("Invalid monitor list")
        return [value for value in values if isinstance(value, dict) and MONITOR_ID.match(str(value.get("id", "")))]

    async def sync(self, repository: str, owner: str, enable: bool) -> tuple[dict | None, list[dict]]:
        """Reconcile the remote latest runs. Baselines never become new-change alerts."""
        if not self.enabled:
            return None, []
        tag = repository_tag(owner, repository)
        resources = await self._list(tag)
        monitor = next((row for row in resources if tag in row.get("tags", [])), None)
        if enable and monitor is None and self._reserve_creation(resources):
            definition = monitor_definition(repository, owner)
            monitor = await self._request("POST", "/monitors", definition)
            if monitor.get("configured") is False:
                monitor = None
            if monitor and MONITOR_ID.match(str(monitor.get("id", ""))):
                resources.append(monitor)
            else:
                monitor = None
        if monitor is None:
            self._accounting(resources)
            return None, []
        if enable and monitor.get("status") == "paused":
            await self._request("PATCH", f"/monitors/{monitor['id']}", {"status": "active"})
            monitor["status"] = "active"
        identifier = monitor["id"]
        usage = await self._request("GET", f"/monitors/credit-usage?since={datetime.now(timezone.utc).date().isoformat()}T00%3A00%3A00Z")
        if usage.get("configured") is not False:
            owned = {row.get("id") for row in resources}
            entries = [row for row in usage.get("data", []) if row.get("monitor_id") in owned]
            self._accounting(resources, sum(int(row.get("credits", 0)) for row in entries))
        runs_response = await self._request("GET", f"/monitors/{identifier}/runs?limit=100")
        runs = [run for run in runs_response.get("data", []) if isinstance(run, dict)]
        latest = max(runs, key=lambda run: str(run.get("started_at") or run.get("completed_at") or ""), default=None)
        baseline = max((run for run in runs if run.get("baseline_created")), key=lambda run: str(run.get("started_at") or run.get("completed_at") or ""), default=None)
        known = self.db.get_meta("context_monitor_runs", {})
        previous = set(known.get(identifier, []))
        if baseline and not previous:
            previous.add(str(baseline["id"]))
        changes: list[dict] = []
        if baseline and latest and baseline.get("id") != latest.get("id"):
            since = baseline.get("started_at")
            if since:
                response = await self._request("GET", f"/monitors/{identifier}/changes?limit=100&since={since}")
                for change in response.get("data", []):
                    if not isinstance(change, dict) or not change.get("id") or change.get("monitor_id") != identifier:
                        continue
                    seen = self.db.get_meta("context_monitor_changes", [])
                    if change["id"] not in seen:
                        changes.append(public_change(change))
                if changes:
                    seen = self.db.get_meta("context_monitor_changes", [])
                    seen.extend(change["id"] for change in changes)
                    self.db.set_meta("context_monitor_changes", list(dict.fromkeys(seen))[-2000:])
        if latest and latest.get("id"):
            known[identifier] = list(previous | {str(latest["id"])})[-100:]
            self.db.set_meta("context_monitor_runs", known)
        state = {
            "configured": True, "provider": "Context.dev", "mode": "remote_scheduled",
            "id": identifier, "name": monitor.get("name"), "status": monitor.get("status"),
            "schedule": "Every hour, executed by Context.dev", "target": monitor.get("target"),
            "next_run_at": monitor.get("next_run_at"), "last_polled_at": utcnow(),
            "last_run": {key: latest.get(key) for key in ("id", "status", "run_type", "started_at", "completed_at", "change_detected", "change_id", "baseline_created", "credits_charged", "skip_reason", "error")} if latest else None,
            "baseline_at": baseline.get("completed_at") if baseline else None,
            "new_changes": len(changes), "budget": self.budget(),
            "api_receipt": {"request_type": "Context.dev monitor read", "credits_consumed": 0},
            "note": "Remote schedules continue while this application is offline. The UI reconciles API runs; a completed baseline is not an alert. Failed or skipped runs are not proof that nothing changed.",
        }
        return state, changes

    async def pause_unrelated(self, repository: str, owner: str) -> None:
        """Stop scheduled credit use for repositories no longer shown; retain their server history."""
        if not self.enabled:
            return
        resources = await self._list("driftci")
        keep = repository_tag(owner, repository) if owner != "example" else None
        for resource in resources:
            if resource.get("status") != "active" or keep in resource.get("tags", []):
                continue
            if any(MONITOR_REPO.match(tag) for tag in resource.get("tags", [])):
                await self._request("PATCH", f"/monitors/{resource['id']}", {"status": "paused"})
                resource["status"] = "paused"
        self._accounting(resources)


def monitor_signal(change: dict) -> dict:
    """One remote observation, with source attribution and explicit semantic-detection uncertainty."""
    urls = [str(url) for url in change.get("matched_urls", [])[:20] if str(url).startswith("https://")]
    if change.get("url", "").startswith("https://") and change["url"] not in urls:
        urls.insert(0, change["url"])
    evidence = change.get("evidence", []) if isinstance(change.get("evidence"), list) else []
    sources = []
    for index, url in enumerate(urls):
        item = next((entry for entry in evidence if isinstance(entry, dict) and entry.get("url") == url), {})
        sources.append({"url": url, "title": safe_excerpt(str(item.get("title") or change.get("title") or "Official-source result"), 220), "mode": "live"})
    detected_at = change.get("detected_at") or utcnow()
    importance = change.get("importance") if change.get("importance") in {"low", "medium", "high"} else "medium"
    snippet_parts = [str(change.get("summary", "")), str(change.get("diff", ""))]
    snippet_parts.extend(str(entry.get("content") or entry.get("snippet") or entry.get("markdown") or "")[:2500] for entry in evidence[:10] if isinstance(entry, dict))
    return {
        "id": f"sig-context-{change['id']}",
        "source": f"Context.dev monitor {change.get('monitor_id', '')}",
        "kind": "security_or_dependency_change",
        "title": safe_excerpt(str(change.get("title") or change.get("summary") or "Official-source monitor change"), 180),
        "severity": importance,
        "summary": safe_excerpt(str(change.get("summary") or change.get("title") or "New official-web result detected by a Context.dev monitor."), 2400),
        "state": "needs_action", "resolved_at": None, "created_at": detected_at,
        "published_at": detected_at, "fixed_version": None,
        "evidence": safe_excerpt("\n".join(snippet_parts), 4000),
        "urls": urls[:20], "sources": sources[:20],
        "monitor_id": change.get("monitor_id"), "run_id": change.get("run_id"),
        "monitor_confidence": change.get("confidence"),
        "difference": public_change(change),
    }
