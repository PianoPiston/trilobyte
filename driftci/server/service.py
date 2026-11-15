"""Application orchestration: inventory, live sources, incidents, approvals and exports."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .changes import capture_change, change_kind, change_severity
from .config import Settings
from .contextdev import ContextDev, DocumentSpec, custom_dict, custom_spec, documents_for, parse_deprecations, research_query, status_snapshot, validate_watch_url
from .db import Database
from .github import GitHubError, GitHubPullRequests
from .intel import VulnerabilityIntel, advisory_receipts, cve_id, kev_entries, kev_receipt, score_and_severity
from .release_analysis import observed_at, release_payload
from .releases import ReleaseError, ReleaseWatcher
from .remediation import RemediationError, generate, patch_text
from .repository import RepositoryError, SourceLimits, read_public
from .scanner import Dependency, dependency_evidence, inventory, middleware_evidence, model_evidence, production_models
from .seed import actions, deprecation_receipt, deprecation_signal
from .util import parse_iso, safe_excerpt, stable_id, utcnow
from .versioning import fixed_version
from .web import CachedWebClient

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
ACTIVE_STATES = {"needs_action", "acknowledged", "fix_ready", "monitoring"}


def public_source(source: dict) -> dict:
    """Keep internal markdown snapshots out of API responses."""
    return {key: value for key, value in source.items() if not key.startswith("_")}


def _date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.replace(".", ""), fmt).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return None


def _latest_date(values: list[str] | tuple[str, ...]) -> str | None:
    parsed = [_date(value) for value in values]
    return max((value for value in parsed if value), key=parse_iso, default=None)


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()


def signal_sort(signal: dict) -> tuple:
    return (signal["state"] not in ACTIVE_STATES, SEVERITY_ORDER.get(signal.get("severity"), 5), not signal.get("kev", False), -(signal.get("cvss") or 0), signal.get("created_at", ""), signal["id"])


class DriftService:
    def __init__(self, db: Database, settings: Settings, http: httpx.AsyncClient):
        self.db = db
        self.settings = settings
        self.http = http
        self.context = ContextDev(db, CachedWebClient(db, http, settings.context_min_interval), settings.contextdev_api_key, settings.context_cache_ttl, settings.context_daily_credit_limit)
        self.intel = VulnerabilityIntel(db, CachedWebClient(db, http, .2), settings.osv_cache_ttl, settings.kev_cache_ttl)
        self.releases = ReleaseWatcher(db, settings, http)

    def health(self) -> dict:
        sources = self.db.list_sources()
        counts = {
            "live": sum(source.get("status") == "live" for source in sources),
            "cached": sum(source.get("status") not in {"live", "replay", "partial", "error", "unconfigured"} for source in sources),
            "partial": sum(source.get("status") == "partial" for source in sources),
            "errors": sum(source.get("status") in {"error", "unconfigured"} for source in sources),
            "replay": sum(source.get("status") == "replay" for source in sources),
        }
        return {
            "ok": True, "version": "2.0.0",
            "context_dev": {"configured": bool(self.settings.contextdev_api_key), "mode": "live" if self.settings.contextdev_api_key and not self.settings.offline else "offline" if self.settings.offline else "unconfigured", "usage": self.context.usage()},
            "github": {"configured": bool(self.settings.github_token), "mode": "pull requests available" if self.settings.github_token else "read-only"},
            "last_scan_at": self.db.get_meta("last_scan_at"), "source_counts": counts,
            "release_stream": self.releases.health(),
        }


    def bootstrap(self) -> dict:
        workspace = self.db.workspace()
        files = self.db.files()
        signals = [dict(row, observed_at=observed_at(row)) for row in sorted(self.db.list_signals(), key=signal_sort)]
        incidents = self.db.list_incidents()
        active_incidents = [incident for incident in incidents if incident["state"] != "resolved"]
        history = [incident for incident in incidents if incident["state"] == "resolved"]
        active_incidents.sort(key=lambda item: (SEVERITY_ORDER.get(item.get("severity"), 5), not item.get("kev"), -(item.get("cvss") or 0), item["id"]))
        history.sort(key=lambda item: item.get("resolved_at", ""), reverse=True)
        issues: dict[tuple[str, str], int] = {}
        affected = set()
        for signal in signals:
            if signal["state"] not in ACTIVE_STATES:
                continue
            if signal.get("affected_package"):
                key = (signal.get("ecosystem", "npm"), signal["affected_package"])
                issues[key] = issues.get(key, 0) + 1
                affected.add(key)
            elif signal["kind"] == "deprecation":
                names = {"OpenAI": ["openai", "@ai-sdk/openai"], "Anthropic": ["anthropic", "@anthropic-ai/sdk"]}.get(signal.get("provider"), [])
                for dep in inventory(files):
                    if dep["name"] in names:
                        key = (dep["ecosystem"], dep["name"])
                        issues[key] = issues.get(key, 0) + 1
                        affected.add(key)
        dependencies = inventory(files, issues)
        remediations = self.db.list_remediations()
        durations = []
        now = datetime.now(timezone.utc)
        resolved_this_month = 0
        for incident in history:
            if not incident.get("resolved_at"):
                continue
            try:
                first, resolved = parse_iso(incident["first_seen_at"]), parse_iso(incident["resolved_at"])
                durations.append(max(0, (resolved - first).total_seconds() / 3600))
                if resolved.year == now.year and resolved.month == now.month:
                    resolved_this_month += 1
            except (ValueError, TypeError):
                continue
        risk_score = 0
        weights = {"critical": 50, "high": 30, "medium": 15, "low": 5, "info": 0}
        for signal in signals:
            if signal["state"] in ACTIVE_STATES:
                risk_score += weights.get(signal["severity"], 0) - (18 if signal["kind"] == "deprecation" and signal["severity"] == "critical" else 0)
                risk_score += 10 if signal.get("kev") else 0
        receipts = {f"{r.get('publisher')}|{r.get('url')}|{r.get('retrieved_at')}|{r.get('mode')}" for signal in signals for r in signal.get("source_receipts", [])}
        sources = self.db.list_sources()
        changes = sorted((dict(change, publisher=source.get("publisher"), source_title=source.get("title"), signal_id=change.get("signal_id")) for source in sources for change in source.get("observations", [])), key=lambda item: item["observed_at"], reverse=True)
        search_source = self.db.get_source("src-context-search") or {}
        release = release_payload(self.db, files, signals, self.releases.health())
        return {
            "workspace": workspace,
            "summary": {
                "risk_score": min(100, risk_score),
                "active_changes": sum(signal["state"] in ACTIVE_STATES for signal in signals),
                "critical_vulnerabilities": sum(incident["severity"] == "critical" for incident in active_incidents),
                "affected_dependencies": len(affected), "remediations_ready": sum(item["status"] in {"ready_for_review", "approved"} for item in remediations),
                "production_models": len(production_models(files)), "resolved_this_month": resolved_this_month,
                "mean_response_hours": round(sum(durations) / len(durations), 1) if durations else 0.0,
                "watched_sources": sum(bool(source.get("category")) for source in sources),
                "observed_changes": len(changes),
                "open_prs": release["counts"]["open"], "release_reviews": release["counts"]["needs_review"],
                "live_release_events": release["counts"]["live_events"],
            },
            "signals": signals, "dependencies": dependencies,
            "activity": self.db.list_activity(30), "sources": [public_source(source) for source in sources],
            "incidents": active_incidents, "history": history,
            "remediations": remediations, "changes": changes, "discoveries": search_source.get("results", []),
            "research": {"query": search_source.get("query"), "retrieved_at": search_source.get("last_checked_at"), "mode": search_source.get("mode")} if search_source else None,
            "release": release,
            "metrics": {"source_receipts": len(receipts), "files_indexed": len(files), "dependencies_indexed": len(dependencies), "context_queries": self.db.get_meta("context_queries", 0), "context_credits": self.db.get_meta("context_credits", 0)},
        }

    def incident_payload(self) -> dict:
        bootstrap = self.bootstrap()
        return {"active": bootstrap["incidents"], "history": bootstrap["history"], "metrics": {
            "active": len(bootstrap["incidents"]), "critical": bootstrap["summary"]["critical_vulnerabilities"],
            "resolved": len(bootstrap["history"]), "mean_response_hours": bootstrap["summary"]["mean_response_hours"],
        }}

    def reset_demo(self) -> dict:
        self.db.reset_demo()
        return self.bootstrap()

    def replay(self) -> dict:
        old = self.db.get_signal("sig-model-gpt4-0314") or {}
        signal = deprecation_signal(self.db.files(), deprecation_receipt())
        signal["remediation_id"] = None
        self.db.delete_remediations_for_signal(signal["id"])
        self.db.save_signal(signal)
        source = self.db.get_source("src-openai-deprecations") or {}
        source.update({"id": "src-openai-deprecations", "publisher": "OpenAI", "title": "Model deprecations", "url": deprecation_receipt()["url"], "status": "replay", "last_checked_at": "2026-03-26T00:00:00Z", "event_count": 1, "mode": "historical_replay", "error": None})
        self.db.save_source(source)
        self.db.add_activity("replay", "Historical incident replayed", "OpenAI announced gpt-4-0314 retirement on 26 Sep 2025; shutdown was 26 Mar 2026. This is a replay, not a new announcement.")
        if old.get("state") == "resolved":
            signal["state"] = "needs_action"
            self.db.save_signal(signal)
        return self.bootstrap()

    def update_incident_action(self, ident: str, action_id: str, status: str) -> dict:
        incident = self.db.get_incident(ident)
        if not incident:
            raise LookupError("Incident not found")
        index = next((index for index, action in enumerate(incident["actions"]) if action["id"] == action_id), None)
        if index is None:
            raise LookupError("Incident action not found")
        actions_list = incident["actions"]
        if status == "done" and any(action["status"] != "done" for action in actions_list[:index]):
            raise RemediationError("Complete preceding checklist actions before this transition")
        if status == "pending" and any(action["status"] == "done" for action in actions_list[index + 1:]):
            raise RemediationError("Reopen later checklist actions before reopening this one")
        action = actions_list[index]
        action["status"] = status
        action["completed_at"] = utcnow() if status == "done" else None
        completed = sum(item["status"] == "done" for item in actions_list)
        incident["state"] = "resolved" if action_id == "resolve" and status == "done" else "responding" if completed else "triaging"
        incident["resolved_at"] = utcnow() if incident["state"] == "resolved" else None
        self.db.save_incident(incident)
        signal = self.db.get_signal(incident["signal_id"])
        if signal:
            signal["state"] = "resolved" if incident["state"] == "resolved" else "needs_action"
            self.db.save_signal(signal)
        self.db.add_activity("incident", f"{incident['cve']}: {action['label']}", f"Checklist action marked {status}")
        return incident

    def add_external_event(self, signal: dict) -> None:
        """Record a newly observed external fact and its currently mapped PRs."""
        related = release_payload(self.db, self.db.files(), self.db.list_signals(), self.releases.health())["pull_requests"]
        numbers = [pr["number"] for pr in related if any(item["id"] == signal["id"] for item in pr["external_evidence"]) and pr["state"] == "open"]
        receipt = (signal.get("source_receipts") or [{}])[0]
        self.db.add_release_event({
            "id": stable_id("event", "external", signal["id"], observed_at(signal) or signal["created_at"]),
            "kind": "web_change", "title": signal["title"],
            "detail": f"External evidence matched {len(numbers)} open PR{'s' if len(numbers) != 1 else ''}. Inspect the source diff before recording a decision.",
            "occurred_at": observed_at(signal) or signal["created_at"], "received_at": utcnow(),
            "pr_id": f"pr-{numbers[0]}" if len(numbers) == 1 else None,
            "pr_number": numbers[0] if len(numbers) == 1 else None,
            "affected_pr_numbers": numbers[:12], "signal_id": signal["id"],
            "url": receipt.get("url"), "source": signal.get("provider", "Context.dev"),
            "mode": receipt.get("mode", "live"), "baseline": False,
            "head_sha": None,
        })

    async def _scan_status(self, files: dict[str, str]) -> None:
        """Hot polling is activity-scoped; unrelated documentation keeps its long cache."""
        specs = [spec for spec in documents_for(files, self._custom_specs(), self.settings.context_max_sources) if spec.category == "status"]
        if not specs:
            return
        hot = False
        deadline = datetime.now(timezone.utc).timestamp() - self.settings.status_hot_window_seconds
        for pr in self.db.list_pull_requests():
            if pr.get("state") != "open":
                continue
            if (pr.get("check_summary") or {}).get("state") == "pending":
                hot = True
                break
            try:
                hot = parse_iso(pr["updated_at"]).timestamp() >= deadline
            except (ValueError, TypeError):
                continue
            if hot:
                break
        await self._scan_documents(files, specs, research=False, hot=hot)

    async def refresh_releases(self, pr_number: int | None = None, include_status: bool = True) -> dict:
        """Refresh PR events independently of expensive web and vulnerability scans."""
        if self.settings.offline:
            return self.bootstrap()
        source = self.db.get_source("src-github-releases") or {
            "id": "src-github-releases", "publisher": "GitHub", "title": "Release event stream",
            "url": f"https://github.com/{self.db.workspace().get('repository', '')}",
        }
        now = utcnow()
        try:
            result = await self.releases.refresh(pr_number)
        except (ReleaseError, RepositoryError) as exc:
            health = self.db.get_meta("github_release_health", {})
            health["last_polled_at"] = now
            health["last_error"] = safe_excerpt(exc, 320)
            if isinstance(exc, ReleaseError) and exc.retry_after:
                health["retry_after_seconds"] = exc.retry_after
            self.db.set_meta("github_release_health", health)
            source.update({"status": "error", "last_attempt_at": now, "error": health["last_error"], "watch": False})
            self.db.save_source(source)
        else:
            health = self.db.get_meta("github_release_health", {})
            health["last_polled_at"] = now
            health["last_success_at"] = now
            health["last_error"] = None
            health["last_transport_mode"] = result["status"]
            health["detail_pending"] = result["detail_pending"]
            health["release_requests"] = self.db.get_meta("github_release_requests", 0)
            self.db.set_meta("github_release_health", health)
            error = safe_excerpt("; ".join(result["errors"]), 360) if result["errors"] else None
            source.update({
                "status": result["status"], "last_checked_at": now, "event_count": sum(event.get("source") == "GitHub" for event in self.db.list_release_events(limit=500)),
                "mode": result["status"], "error": error, "category": "release_events", "watch": False,
                "poll_interval_seconds": self.settings.release_poll_interval_seconds,
            })
            self.db.save_source(source)
            if include_status:
                await self._scan_status(self.db.files())
        return self.bootstrap()

    def record_release_decision(self, pr_id: str, decision: str, reviewer: str, note: str) -> dict:
        if decision not in {"ready", "hold"} or not 1 <= len(reviewer.strip()) <= 80 or len(note) > 1000:
            raise RemediationError("Provide a reviewer name and a ready or hold decision")
        pr = self.db.get_pull_request(pr_id)
        if not pr:
            raise LookupError("Release pull request not found")
        current = next((row for row in release_payload(self.db, self.db.files(), self.db.list_signals(), self.releases.health())["pull_requests"] if row["id"] == pr_id), None)
        if not current or pr["state"] != "open":
            raise RemediationError("Only an open pull request can receive a release decision")
        release_health = self.releases.health()
        if decision == "ready" and (release_health.get("last_error") or not release_health.get("last_success_at")):
            raise RemediationError("GitHub release evidence is stale or has not been retrieved. Refresh it before recording ready, or record a hold with that limitation.")
        if decision == "ready" and not pr.get("detail_complete"):
            raise RemediationError("PR file, review and check coverage is incomplete. Refresh first, or record a hold with the known coverage limit.")
        if decision == "ready" and (pr.get("check_summary") or {}).get("state") in {"pending", "failed"}:
            raise RemediationError("Checks are still running or failing. Inspect them before recording a ready decision.")
        created = utcnow()
        record = {
            "id": stable_id("decision", pr_id, current["head_sha"], current["evidence_hash"], created, reviewer, decision),
            "pr_id": pr_id, "head_sha": current["head_sha"], "evidence_hash": current["evidence_hash"],
            "decision": decision, "reviewer": safe_excerpt(reviewer, 80), "note": safe_excerpt(note, 1000),
            "created_at": created, "scope": "local DriftCI release decision; no GitHub review or merge state was changed",
        }
        self.db.save_release_decision(record)
        self.db.add_release_event({
            "id": stable_id("event", "local-decision", record["id"]),
            "kind": "decision", "title": f"Release {'readiness confirmed' if decision == 'ready' else 'paused'}",
            "detail": f"{record['reviewer']} recorded a local {decision} decision for head {current['head_sha'][:8]} · evidence {current['evidence_hash'][:8]}. {record['note']}",
            "occurred_at": created, "received_at": created, "pr_id": pr_id, "pr_number": pr["number"],
            "url": pr["url"], "head_sha": pr["head_sha"], "source": "DriftCI reviewer", "mode": "local_record", "baseline": False,
            "decision": decision,
        })
        self.db.add_activity("release_decision", f"PR #{pr['number']}: release {'ready' if decision == 'ready' else 'paused'}", f"{record['reviewer']} · local decision · no GitHub state changed")
        return self.bootstrap()

    def release_report(self, pr_id: str) -> tuple[str, str]:
        current = next((row for row in release_payload(self.db, self.db.files(), self.db.list_signals(), self.releases.health())["pull_requests"] if row["id"] == pr_id), None)
        if not current:
            raise LookupError("Release pull request not found")
        decision = current["release_decision"]
        lines = [
            f"# DriftCI release decision · PR #{current['number']}", "",
            current["title"], "",
            f"Generated at {utcnow()}. Source repository: {current['repository']}.", "",
            "## Current state", "",
            f"- Head commit: `{current['head_sha']}`",
            f"- Readiness: **{current['readiness']}**",
            f"- Local decision: **{decision['decision'] if decision else 'not recorded'}**",
            f"- Reviewer: {decision['reviewer'] if decision else 'not recorded'}",
            f"- Decision recorded: {decision['created_at'] if decision else 'not recorded'}",
            f"- Evidence hash: `{current['evidence_hash']}`",
            f"- Latest observed external change: {current['latest_external_observation'] or 'no observed post-baseline change mapped'}",
            f"- Latest remote approval: {current['latest_remote_approval'] or 'no approval in the bounded review retrieval'}",
            f"- Changed-file coverage: {'complete within the declared bound' if current.get('files_complete') else 'partial; refresh before relying on absence'}",
            "",
        ]
        if decision:
            lines.extend(["## Reviewer note", "", decision["note"] or "No note supplied.", "", decision["scope"], ""])
        elif current.get("expired_release_decision"):
            expired = current["expired_release_decision"]
            lines.extend(["An earlier local decision no longer matches the current head or evidence set.", "", f"Previous decision: {expired['decision']} at {expired['created_at']}.", ""])
        lines.extend(["## Checks", "", "| Check | Status | Conclusion |", "| --- | --- | --- |"])
        for check in current.get("checks", []):
            lines.append(f"| {check['name']} | {check['status']} | {check.get('conclusion') or 'pending'} |")
        if not current.get("checks"):
            lines.append("| No checks reported in the bounded GitHub response | — | — |")
        lines.extend(["", "## Changed files", ""])
        for item in current.get("files", []):
            lines.append(f"- `{item['path']}` · +{item['additions']} / −{item['deletions']}")
        lines.extend(["", "## External evidence", ""])
        for match in current["external_evidence"]:
            lines.extend([f"### {match['title']}", "", f"Signal `{match['id']}` · state {match['state']} · observed {match.get('observed_at') or 'baseline only; no post-baseline observation timestamp'}.", ""])
            if match["matched_files"]:
                lines.append("Matched paths: " + ", ".join(f"`{path}`" for path in match["matched_files"]))
                lines.append("")
            for receipt in match["source_receipts"]:
                fingerprint = (match.get("change") or {}).get("content_hash") or hashlib.sha256(f"{receipt.get('url')}\0{receipt.get('retrieved_at')}\0{receipt.get('quote')}".encode()).hexdigest()
                lines.append(f"- [{receipt.get('publisher')}: {receipt.get('title')}]({receipt.get('url')}) · retrieved {receipt.get('retrieved_at')} · `{fingerprint}`")
        if not current["external_evidence"]:
            lines.append("No matching external evidence in the bounded PR/source mapping. This is scoped evidence, not a guarantee that no relevant external change exists.")
        lines.extend(["", "## Limitations", "", "DriftCI did not execute the repository, change GitHub review/merge state or prove runtime exploitability. PR matching uses added and context lines in the bounded retrieved diffs; removed lines and deleted files do not count as current configuration. Omitted or truncated patches remain incomplete. Validate application-owned tests and deployment checks before release.", ""])
        return f"pr-{current['number']}-release-decision.md", "\n".join(lines)

    def create_remediation(self, signal_id: str) -> dict:
        signal = self.db.get_signal(signal_id)
        if not signal:
            raise LookupError("Signal not found")
        if signal["state"] == "resolved":
            raise RemediationError("Resolved signals do not need a new remediation")
        remediation = generate(self.db.files(), signal, bool(self.settings.github_token))
        existing = self.db.get_remediation(remediation["id"])
        if existing:
            return existing
        self.db.save_remediation(remediation)
        signal["remediation_id"] = remediation["id"]
        signal["state"] = "fix_ready"
        self.db.save_signal(signal)
        self.db.add_activity("remediation", remediation["title"], remediation["summary"] + "; static checks only")
        return remediation

    def approve(self, ident: str) -> dict:
        remediation = self.db.get_remediation(ident)
        if not remediation:
            raise LookupError("Remediation not found")
        if remediation["status"] == "ready_for_review":
            remediation["status"] = "approved"
            remediation["approved_at"] = utcnow()
            self.db.save_remediation(remediation)
            self.db.add_activity("approval", "Remediation approved by a human", f"{ident} is approved for patch export or pull request creation")
        return remediation

    def export_patch(self, ident: str) -> tuple[str, str]:
        remediation = self.db.get_remediation(ident)
        if not remediation:
            raise LookupError("Remediation not found")
        if remediation["status"] != "approved" or not remediation.get("approved_at"):
            raise RemediationError("Human approval is required before patch export")
        return f"{ident}.patch", patch_text(remediation)

    def incident_report(self, ident: str) -> str:
        incident = self.db.get_incident(ident)
        if not incident:
            raise LookupError("Incident not found")
        lines = [
            f"# {incident['cve']}: {incident['title']}", "",
            f"Generated by DriftCI at {utcnow()}. This is a response record, not proof of exploitability.", "",
            "## Impact", "",
            f"- **State:** {incident['state']}",
            f"- **Severity / CVSS:** {incident['severity']} / {incident.get('cvss') if incident.get('cvss') is not None else 'not supplied'}",
            f"- **CISA KEV listed:** {'yes' if incident.get('kev') else 'no'}",
            f"- **Package:** `{incident['affected_package']}@{incident['affected_version']}`",
            f"- **Fixed version identified:** `{incident.get('fixed_version') or 'not supplied'}`",
            f"- **Reachability clue:** {incident.get('reachability', 'unknown')}",
            f"- **First seen:** {incident['first_seen_at']}",
            f"- **Resolved:** {incident.get('resolved_at') or 'not resolved'}", "",
            incident.get("summary", ""), "",
            "## Reachability assessment", "",
            incident.get("reachability_reason", "No reachability assessment was recorded."),
            "Deployment-specific verification is still required; installation alone does not prove exploitability.", "",
            "## Response timeline", "",
            "| Step | Status | Completed at |", "| --- | --- | --- |",
        ]
        for action in incident.get("actions", []):
            lines.append(f"| {action['label']} | {action['status']} | {action.get('completed_at') or '—'} |")
        lines.extend(["", "## Repository evidence", ""])
        evidence = incident.get("affected_files") or []
        if not evidence:
            lines.append("No source locations were returned.")
        for item in evidence:
            lines.extend([f"### `{item['file']}:{item['line']}`", "", "```text", item.get("snippet", "").replace("```", "''"), "```", "", item.get("reason", ""), ""])
        lines.extend(["## Advisory receipts", ""])
        for receipt in incident.get("source_receipts", []):
            lines.append(f"- [{receipt.get('publisher')}: {receipt.get('title')}]({receipt.get('url')}) — retrieved {receipt.get('retrieved_at')} · {receipt.get('mode')}")
            if receipt.get("quote"):
                lines.extend(["", "> " + str(receipt["quote"]).replace("\n", "\n> "), ""])
        lines.extend(["## Remaining validation", "", "Complete application-owned build, security and deployment checks before relying on a patch or closing residual risk. DriftCI did not execute repository code.", ""])
        return "\n".join(lines)

    async def open_pr(self, ident: str) -> dict:
        remediation = self.db.get_remediation(ident)
        if not remediation:
            raise LookupError("Remediation not found")
        if remediation["status"] != "approved":
            raise RemediationError("Human approval is required before opening a pull request")
        if not self.settings.github_token:
            raise PermissionError("GitHub is not configured. Export the approved unified patch instead; no pull request was created.")
        signal = self.db.get_signal(remediation["signal_id"])
        if not signal:
            raise LookupError("The originating signal no longer exists")
        result = await GitHubPullRequests(self.http, self.settings.github_token).open(self.db.workspace(), remediation, signal)
        remediation.update(result)
        remediation["can_open_pr"] = True
        self.db.save_remediation(remediation)
        self.db.add_activity("pull_request", "Pull request opened", str(result["pr_url"]))
        return remediation

    def update_signal_state(self, ident: str, state: str) -> dict:
        signal = self.db.get_signal(ident)
        if not signal:
            raise LookupError("Signal not found")
        if state not in {"acknowledged", "resolved", "monitoring", "needs_action"}:
            raise RemediationError("Unsupported signal state")
        if signal["kind"] == "vulnerability" and state == "resolved":
            raise RemediationError("Resolve vulnerabilities through the incident-response checklist")
        signal["state"] = state
        signal["reviewed_at"] = utcnow() if state in {"acknowledged", "resolved"} else None
        self.db.save_signal(signal)
        self.db.add_activity("review", f"Signal marked {state.replace('_', ' ')}", signal["title"])
        return signal

    def _custom_specs(self) -> list[DocumentSpec]:
        return [custom_spec(item) for item in self.db.get_meta("custom_watches", [])]

    async def add_watch(self, url: str, title: str) -> dict:
        spec = validate_watch_url(url, title)
        watches = self.db.get_meta("custom_watches", [])
        if not any(item["key"] == spec.key for item in watches):
            if len(watches) >= 12:
                raise RemediationError("The prototype supports up to 12 custom web watches")
            watches.append(custom_dict(spec))
            self.db.set_meta("custom_watches", watches)
        self.db.add_activity("watch", "Custom web watch added", f"{spec.title} · {spec.url}")
        await self._scan_documents(self.db.files())
        self.db.set_meta("last_scan_at", utcnow())
        return self.bootstrap()

    def remove_watch(self, key: str) -> dict:
        watches = self.db.get_meta("custom_watches", [])
        spec = next((custom_spec(item) for item in watches if item["key"] == key), None)
        if not spec:
            raise LookupError("Custom watch not found")
        self.db.set_meta("custom_watches", [item for item in watches if item["key"] != key])
        self.db.delete_source(f"src-{spec.key}")
        for signal in self.db.list_signals():
            if signal.get("watch_id") == f"src-{spec.key}":
                self.db.delete_signal(signal["id"])
        self.db.add_activity("watch", "Custom web watch removed", spec.title)
        return self.bootstrap()

    async def connect(self, url: str) -> dict:
        limits = SourceLimits(self.settings.github_file_limit, self.settings.github_byte_limit, self.settings.github_file_byte_limit)
        workspace, files = await read_public(self.http, url, self.settings.github_token, limits)
        self.db.replace_workspace(workspace, files)
        scope = "full eligible-file coverage" if workspace["coverage"]["complete"] else "bounded/partial coverage; inspect scan coverage before concluding absence"
        self.db.add_activity("repository", "Public repository selectively indexed", f"{workspace['repository']}@{(workspace['coverage']['commit_sha'])[:12]} · {len(files)} text files, {workspace['coverage']['bytes_read']} bytes · {scope}; no archive or repository code executed")
        await self.scan()
        return self.bootstrap()

    async def scan(self) -> dict:
        files = self.db.files()
        dependencies = [Dependency(**{key: item[key] for key in ("name", "ecosystem", "version", "declared", "kind", "manifest", "exact")}) for item in inventory(files) if item["exact"]]
        if self.settings.offline:
            self.db.add_activity("scan", "Offline inventory refreshed", f"{len(files)} files · {len(dependencies)} exact dependency versions; network sources were not queried")
        else:
            document_results, vulnerability_count, _release = await asyncio.gather(self._scan_documents(files), self._scan_vulnerabilities(files, dependencies), self.refresh_releases(include_status=False))
            warnings = sum(bool(source.get("error")) or source.get("status") in {"error", "unconfigured", "partial"} for source in self.db.list_sources())
            decisions = sum(signal["state"] in ACTIVE_STATES for signal in self.db.list_signals())
            self.db.add_activity("scan", "Source refresh completed", f"{document_results} model signals · {vulnerability_count} package-advisory matches · {decisions} decisions required · {warnings} source warnings")
        self.db.set_meta("last_scan_at", utcnow())
        return self.bootstrap()

    def _observation_signal(self, spec: DocumentSpec, observation: dict, files: dict[str, str], locations_by_model: dict[str, list[dict]]) -> dict | None:
        if spec.category == "deprecations":
            return None  # Structured lifecycle rows produce more precise signals below.
        changed_text = " ".join(observation["added"] + observation["removed"]).lower()
        evidence: list[dict] = []
        assets: list[str] = []
        terms: list[str] = []
        if spec.category == "status":
            package_names = {"OpenAI": {"openai", "@ai-sdk/openai"}, "Anthropic": {"anthropic", "@anthropic-ai/sdk"}}.get(spec.provider, set())
            for item in inventory(files):
                if item["name"] in package_names:
                    dependency = Dependency(**{key: item[key] for key in ("name", "ecosystem", "version", "declared", "kind", "manifest", "exact")})
                    evidence.extend(dependency_evidence(files, dependency))
                    assets.append(item["name"])
                    terms.append(item["name"])
            for model, locations in locations_by_model.items():
                evidence.extend(dict(item) for item in locations)
                assets.append(model)
                terms.append(model)
        elif spec.package:
            for item in inventory(files):
                if item["name"] != spec.package:
                    continue
                dependency = Dependency(**{key: item[key] for key in ("name", "ecosystem", "version", "declared", "kind", "manifest", "exact")})
                evidence.extend(dependency_evidence(files, dependency))
            assets.append(spec.package)
            terms.append(spec.package)
        else:
            for model, locations in locations_by_model.items():
                if model in changed_text:
                    evidence.extend(dict(item) for item in locations)
                    assets.append(model)
                    terms.append(model)
        if not evidence and not spec.custom:
            return None
        evidence = evidence[:12]
        ident = stable_id("sig-web", observation["id"])
        old = self.db.get_signal(ident) or {}
        observation["signal_id"] = ident
        observation["matched_terms"] = terms
        receipt = {
            "publisher": spec.provider, "title": spec.title, "url": spec.url,
            "retrieved_at": observation["observed_at"], "mode": observation["mode"],
            "quote": observation["added"][0] if observation["added"] else observation["removed"][0],
        }
        signal = {
            "id": ident, "kind": change_kind(observation, spec), "severity": change_severity(observation, spec),
            "state": old.get("state", "needs_action"), "title": observation["title"],
            "summary": f"Context.dev observed {observation['added_lines']} added and {observation['removed_lines']} removed lines against the previous snapshot. {len(evidence)} repository locations are attached for review.",
            "provider": spec.provider, "affected_assets": assets or [spec.title],
            "deadline": None, "announced_at": None, "cve": None, "cvss": None, "kev": False,
            "fixed_version": None, "replacement": None, "model": None,
            "reachability": "confirmed" if evidence else "unknown",
            "reachability_reason": "The watch was derived from this repository; the diff still requires human review.",
            "recommendation": "Compare the added and removed lines, open the primary source, and validate any repository impact before changing production.",
            "evidence": evidence, "source_receipts": [receipt], "remediation_id": None,
            "created_at": old.get("created_at") or observation["observed_at"],
            "watch_id": observation["source_id"], "change": observation,
        }
        self.db.save_signal(signal)
        return signal

    async def _scan_research(self, files: dict[str, str], specs: list[DocumentSpec]) -> None:
        query = research_query(files, specs)
        if not query:
            return
        result = await self.context.search(query)
        old = self.db.get_source("src-context-search") or {}
        source = {
            **old, "id": "src-context-search", "publisher": "Context.dev", "title": "Scoped official-web research",
            "url": "https://context.dev/", "query": query, "watch": False,
        }
        if result.error:
            source.update({"status": "unconfigured" if not self.settings.contextdev_api_key else "error", "error": safe_excerpt(result.error, 240)})
            self.db.save_source(source)
            return
        rows = []
        terms = [model.lower() for model in production_models(files)] + [item["name"].lower() for item in inventory(files) if item["kind"] in {"framework", "ai_sdk"}]
        for item in result.data["results"]:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                continue
            highlights = item.get("highlights") or []
            if not isinstance(highlights, list):
                highlights = []
            summary = safe_excerpt(" ".join(str(value) for value in highlights) or item.get("text") or item.get("summary"), 900)
            title = safe_excerpt(item.get("title") or url, 180)
            official_host = query.split("site:", 1)[1].split()[0].split("/", 1)[0]
            if urlparse(url).hostname != official_host:
                continue
            haystack = f"{title} {summary}".lower()
            rows.append({
                "id": stable_id("discovery", url), "title": title, "url": url, "summary": summary,
                "published_at": item.get("publishedDate") if isinstance(item.get("publishedDate"), str) else None,
                "retrieved_at": result.retrieved_at, "mode": result.mode,
                "matched_terms": [term for term in terms if term and term in haystack][:6],
            })
        source.update({
            "status": result.mode, "last_checked_at": result.retrieved_at, "event_count": len(rows),
            "mode": result.mode, "error": None, "results": rows,
        })
        self.db.save_source(source)

    async def _scan_documents(self, files: dict[str, str], specs: list[DocumentSpec] | None = None, research: bool = True, hot: bool = False) -> int:
        matched = 0
        specs = specs if specs is not None else documents_for(files, self._custom_specs(), self.settings.context_max_sources)
        locations_by_model: dict[str, list[dict]] = {}
        for item in model_evidence(files):  # Parse the selected source tree once, not once per lifecycle event.
            locations_by_model.setdefault(item["model"].lower(), []).append({key: value for key, value in item.items() if key != "model"})
        for spec in specs:
            ttl = self.settings.status_hot_ttl_seconds if hot else self.settings.status_cache_ttl_seconds if spec.category == "status" else None
            result = await self.context.scrape(spec, ttl=ttl)
            if result.error:
                source = self.context.error_source(spec, result.error)
                if not self.settings.contextdev_api_key:
                    source["status"] = "unconfigured"
                source["watch"] = True
                self.db.save_source(source)
                continue

            old = self.db.get_source(f"src-{spec.key}") or {}
            had_document_baseline = bool(old.get("content_hash"))
            comparable = status_snapshot(result.data) if spec.category == "status" else result.data
            observation, snapshot = capture_change(spec, comparable, old, result.retrieved_at or utcnow(), result.mode)
            observations = list(old.get("observations") or [])[:12]
            lifecycle_matches = 0
            if observation:
                signal = self._observation_signal(spec, observation, files, locations_by_model)
                observations.insert(0, observation)
                if signal:
                    matched += 1
                self.db.add_activity("web_change", observation["title"], f"{observation['added_lines']} additions · {observation['removed_lines']} removals · matched {len(observation.get('matched_terms', []))} repository terms")
                if signal:
                    self.add_external_event(signal)

            observations = observations[:12]
            if spec.category == "deprecations":
                for event in parse_deprecations(result.data, spec.provider):
                    evidence = [dict(item) for item in locations_by_model.get(event["model"].lower(), [])]
                    if not evidence:
                        continue
                    lifecycle_matches += 1
                    model = event["model"]
                    special = spec.provider == "OpenAI" and model.lower() == "gpt-4-0314"
                    ident = "sig-model-gpt4-0314" if special else stable_id("sig-model", spec.provider, model.lower())
                    existing = self.db.get_signal(ident) or {}
                    replacement = "gpt-4.1" if special else event.get("replacement")
                    deadline = _latest_date(event.get("shutdown_dates") or [])
                    announced = _latest_date(event.get("announcement_dates") or [])
                    receipt = {"publisher": spec.provider, "title": spec.title, "url": spec.url, "retrieved_at": result.retrieved_at, "mode": result.mode, "quote": event["quote"]}
                    past = bool(deadline and parse_iso(deadline) <= datetime.now(timezone.utc))
                    signal = {
                        "id": ident, "kind": "deprecation", "severity": "critical" if past else "high", "state": existing.get("state", "needs_action"),
                        "title": "Retired model identifiers remain in source" if past else "Model identifiers are approaching retirement",
                        "summary": f"{model} {'was shut down' if past else 'is listed for retirement'}{' on ' + deadline[:10] if deadline else ''}. {len(evidence)} selected code/config locations reference it.",
                        "provider": spec.provider, "affected_assets": ["Support summaries", "Escalation drafts"] if special else sorted({item["file"] for item in evidence}),
                        "deadline": deadline, "announced_at": announced, "cve": None, "cvss": None, "kev": False, "fixed_version": None,
                        "replacement": replacement, "model": model, "reachability": "confirmed",
                        "reachability_reason": "Exact identifiers confirm presence in selected code/config, not runtime invocation or deployment. SDK catalog definitions also require compatibility review.",
                        "recommendation": f"Where application-owned code uses it, review migration to {replacement} and run existing evaluations. For SDK catalogs, review compatibility and removal policy first." if replacement else "Review official lifecycle replacements for application call sites and compatibility catalogs, then run existing evaluations before deployment.",
                        "evidence": evidence, "source_receipts": [receipt], "remediation_id": existing.get("remediation_id"),
                        "created_at": existing.get("created_at") or announced or utcnow(), "watch_id": f"src-{spec.key}",
                    }
                    new_signal = not existing
                    signal["observed_at"] = existing.get("observed_at") or (result.retrieved_at if new_signal and had_document_baseline else None)
                    self.db.save_signal(signal)
                    if new_signal and had_document_baseline:
                        self.add_external_event(signal)
            self.db.save_source({
                **old, **snapshot, "id": f"src-{spec.key}", "publisher": spec.provider, "title": spec.title, "url": spec.url,
                "status": result.mode, "last_checked_at": result.retrieved_at, "event_count": lifecycle_matches + len(observations),
                "matched_events": lifecycle_matches, "observations": observations, "mode": result.mode, "error": None,
                "category": spec.category, "package": spec.package, "custom": spec.custom, "watch": True,
            })
            matched += lifecycle_matches
        if research:
            await self._scan_research(files, specs)
        return matched

    async def _scan_vulnerabilities(self, files: dict[str, str], dependencies: list[Dependency]) -> int:
        if not dependencies:
            return 0
        had_baseline = bool(self.db.get_meta("vulnerability_baseline_at"))
        dependency_priority = {"framework": 0, "ai_sdk": 1, "ui": 2}
        ordered = sorted(dependencies, key=lambda item: (item.manifest.count("/") > 0, dependency_priority.get(item.kind, 3), item.manifest, item.name))
        limit = self.settings.vulnerability_package_limit
        packages = ordered[:limit] if limit > 0 else ordered
        packages_pending = max(0, len(ordered) - len(packages))
        semaphore = asyncio.Semaphore(4)

        async def query_package(dependency: Dependency):
            async with semaphore:
                return await self.intel.query_package(dependency)

        tasks = [asyncio.create_task(query_package(dependency)) for dependency in packages]
        try:
            done, pending = await asyncio.wait(tasks, timeout=self.settings.osv_batch_timeout_seconds)
        finally:
            unfinished = [task for task in tasks if not task.done()]
            for task in unfinished:
                task.cancel()
            if unfinished:
                await asyncio.gather(*unfinished, return_exceptions=True)
        package_timeouts = len(pending)
        results = [task.result() for task in sorted(done, key=tasks.index)]
        kev_result = await self.intel.kev()
        known_exploited = kev_entries(kev_result)
        matches = 0
        errors = []
        live_retrievals = []
        for package_result in results:
            if package_result.result.error:
                errors.append(f"{package_result.dependency.name}: {package_result.result.error}")
                continue
            dependency = package_result.dependency
            live_retrievals.append(package_result.result.retrieved_at)
            for advisory in package_result.advisories:
                cve = cve_id(advisory) or advisory["id"]
                base_id = f"sig-{cve}"
                existing = self.db.get_signal(base_id) or {}
                same_scope = (
                    existing.get("affected_package") == dependency.name
                    and existing.get("ecosystem") == dependency.ecosystem
                    and existing.get("affected_version") == dependency.version
                    and existing.get("manifest") in {None, dependency.manifest}
                )
                ident = base_id if not existing or same_scope else f"{base_id}-{_slug(dependency.ecosystem)}-{_slug(dependency.name)}-{_slug(dependency.manifest)}"
                existing = self.db.get_signal(ident) or {}
                score, severity = score_and_severity(advisory)
                is_kev = cve in known_exploited
                fixed = fixed_version(advisory, dependency.name, dependency.ecosystem, dependency.version)
                evidence = dependency_evidence(files, dependency)
                middleware = middleware_evidence(files) if dependency.name == "next" and cve == "CVE-2025-29927" else []
                receipts = advisory_receipts(advisory, package_result.result)
                if is_kev and not kev_result.error:
                    receipts.append(kev_receipt(cve, kev_result))
                title = safe_excerpt(advisory.get("summary") or cve, 180)
                summary = safe_excerpt(advisory.get("summary") or advisory.get("details") or "OSV reports the installed version in an affected range.", 800)
                state = existing.get("state") if existing.get("state") != "resolved" else "needs_action"
                signal = {
                    "id": ident, "kind": "vulnerability", "severity": severity, "state": state or "needs_action", "title": title, "summary": summary,
                    "provider": "OSV", "affected_assets": [dependency.name], "deadline": _date(known_exploited.get(cve, {}).get("dueDate")),
                    "cve": cve if cve.startswith("CVE-") else None, "advisory_id": advisory["id"], "cvss": score, "kev": is_kev,
                    "fixed_version": fixed, "replacement": None,
                    "reachability": "likely" if middleware else "unknown",
                    "reachability_reason": "Authorization middleware is present; deployment verification is required" if middleware else "The installed version matches an affected range; code reachability and exploitability are not proven",
                    "recommendation": f"Upgrade {dependency.name} to {fixed} or later and run targeted application tests." if fixed else f"Follow the linked official advisory for {dependency.name}; no fixed version was identified in this affected range.",
                    "evidence": evidence, "source_receipts": receipts, "remediation_id": existing.get("remediation_id"),
                    "created_at": existing.get("created_at") or advisory.get("published") or utcnow(),
                    "affected_package": dependency.name, "ecosystem": dependency.ecosystem, "affected_version": dependency.version,
                    "manifest": dependency.manifest, "aliases": advisory.get("aliases") or [],
                }
                if known_exploited.get(cve):
                    signal["kev_due_date"] = known_exploited[cve].get("dueDate")
                    signal["kev_ransomware"] = known_exploited[cve].get("knownRansomwareCampaignUse")
                signal["observed_at"] = existing.get("observed_at") or (utcnow() if had_baseline else None)
                new_signal = not existing
                self.db.save_signal(signal)
                if new_signal and had_baseline:
                    self.add_external_event(signal)
                incident_id = "inc-" + ident[4:]
                previous = self.db.get_incident(incident_id) or {}
                old_actions = previous.get("actions") or actions(fixed or "an unaffected release")
                signal_reachability = signal["reachability"]
                incident = {
                    "id": incident_id, "cve": cve, "title": title, "severity": severity, "cvss": score, "kev": is_kev,
                    "state": previous.get("state", "triaging") if previous.get("state") != "resolved" else "triaging",
                    "first_seen_at": previous.get("first_seen_at") or signal["created_at"], "resolved_at": None,
                    "affected_package": dependency.name, "affected_version": dependency.version, "fixed_version": fixed,
                    "reachability": signal_reachability, "reachability_reason": signal["reachability_reason"], "summary": summary,
                    "affected_files": middleware or evidence, "source_receipts": receipts, "actions": old_actions, "signal_id": ident,
                }
                self.db.save_incident(incident)
                matches += 1
        source = self.db.get_source("src-osv") or {"id": "src-osv", "publisher": "OSV", "title": "Open vulnerability intelligence", "url": "https://osv.dev"}
        any_live = any(result.result.mode == "live" and not result.result.error for result in results)
        scope_warnings = []
        if packages_pending:
            scope_warnings.append(f"{packages_pending} additional inventoried packages were not queried within the package limit")
        if package_timeouts:
            scope_warnings.append(f"{package_timeouts} package queries timed out; absent advisories are not evidence of safety")
        status = "error" if errors else "partial" if packages_pending or package_timeouts else "live" if any_live else "cached"
        source.update({"status": status, "last_checked_at": max((item for item in live_retrievals if item), default=source.get("last_checked_at")), "event_count": matches, "mode": "live" if any_live else source.get("mode", "cached"), "error": safe_excerpt("; ".join(errors + scope_warnings), 360) if errors or scope_warnings else None, "packages_total": len(ordered), "packages_checked": len(results), "packages_pending": packages_pending + package_timeouts})
        self.db.save_source(source)
        cisa = self.db.get_source("src-cisa") or {"id": "src-cisa", "publisher": "CISA", "title": "Known Exploited Vulnerabilities", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"}
        cisa.update({"status": "error" if kev_result.error else kev_result.mode, "last_checked_at": kev_result.retrieved_at or cisa.get("last_checked_at"), "event_count": sum(cve_id(advisory) in known_exploited for result in results for advisory in result.advisories), "mode": kev_result.mode if not kev_result.error else cisa.get("mode", "cached"), "error": safe_excerpt(kev_result.error, 240) if kev_result.error else None})
        self.db.save_source(cisa)
        self.db.set_meta("vulnerability_baseline_at", self.db.get_meta("vulnerability_baseline_at") or utcnow())
        return matches
