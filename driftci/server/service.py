"""Application orchestration: inventory, live sources, incidents, approvals and exports."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from .config import Settings
from .contextdev import DOCUMENTS, ContextDev, DocumentSpec, parse_deprecations
from .db import Database
from .github import GitHubError, GitHubPullRequests
from .intel import VulnerabilityIntel, advisory_receipts, cve_id, kev_entries, kev_receipt, score_and_severity
from .remediation import RemediationError, generate, patch_text
from .repository import download_public
from .scanner import Dependency, dependency_evidence, inventory, middleware_evidence, model_evidence, production_models
from .seed import actions, deprecation_receipt, deprecation_signal
from .util import parse_iso, safe_excerpt, stable_id, utcnow
from .versioning import fixed_version
from .web import CachedWebClient

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
ACTIVE_STATES = {"needs_action", "acknowledged", "fix_ready"}


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
        self.context = ContextDev(db, CachedWebClient(db, http, settings.context_min_interval), settings.contextdev_api_key, settings.context_cache_ttl)
        self.intel = VulnerabilityIntel(db, CachedWebClient(db, http, .2), settings.osv_cache_ttl, settings.kev_cache_ttl)

    def health(self) -> dict:
        sources = self.db.list_sources()
        counts = {
            "live": sum(source.get("status") == "live" for source in sources),
            "cached": sum(source.get("status") not in {"live", "replay"} for source in sources),
            "replay": sum(source.get("status") == "replay" for source in sources),
        }
        return {
            "ok": True, "version": "1.0.0",
            "context_dev": {"configured": bool(self.settings.contextdev_api_key), "mode": "live" if self.settings.contextdev_api_key and not self.settings.offline else "offline" if self.settings.offline else "unconfigured"},
            "github": {"configured": bool(self.settings.github_token), "mode": "pull requests" if self.settings.github_token else "patch export"},
            "last_scan_at": self.db.get_meta("last_scan_at"), "source_counts": counts,
        }

    def bootstrap(self) -> dict:
        workspace = self.db.workspace()
        files = self.db.files()
        signals = sorted(self.db.list_signals(), key=signal_sort)
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
        return {
            "workspace": workspace,
            "summary": {
                "risk_score": min(100, risk_score),
                "active_changes": sum(signal["state"] in ACTIVE_STATES for signal in signals),
                "critical_vulnerabilities": sum(incident["severity"] == "critical" for incident in active_incidents),
                "affected_dependencies": len(affected), "remediations_ready": sum(item["status"] in {"ready_for_review", "approved"} for item in remediations),
                "production_models": len(production_models(files)), "resolved_this_month": resolved_this_month,
                "mean_response_hours": round(sum(durations) / len(durations), 1) if durations else 0.0,
            },
            "signals": signals, "dependencies": dependencies,
            "activity": self.db.list_activity(30), "sources": self.db.list_sources(),
            "incidents": active_incidents, "history": history,
            "remediations": remediations,
            "metrics": {"source_receipts": len(receipts), "files_indexed": len(files), "dependencies_indexed": len(dependencies), "context_queries": self.db.get_meta("context_queries", 0)},
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

    async def connect(self, url: str) -> dict:
        workspace, files = await download_public(self.http, url, self.settings.github_token)
        self.db.replace_workspace(workspace, files)
        self.db.add_activity("repository", "Public repository connected", f"{workspace['repository']} · {len(files)} UTF-8 source files indexed; no repository code executed")
        await self.scan()
        return self.bootstrap()

    async def scan(self) -> dict:
        files = self.db.files()
        dependencies = [Dependency(**{key: item[key] for key in ("name", "ecosystem", "version", "declared", "kind", "manifest", "exact")}) for item in inventory(files) if item["exact"]]
        if self.settings.offline:
            self.db.add_activity("scan", "Offline inventory refreshed", f"{len(files)} files · {len(dependencies)} exact dependency versions; network sources were not queried")
        else:
            document_results, vulnerability_count = await asyncio.gather(self._scan_documents(files), self._scan_vulnerabilities(files, dependencies))
            errors = sum(source.get("status") in {"error", "unconfigured"} for source in self.db.list_sources())
            decisions = sum(signal["state"] in ACTIVE_STATES for signal in self.db.list_signals())
            self.db.add_activity("scan", "Source refresh completed", f"{document_results} model signals · {vulnerability_count} package-advisory matches · {decisions} decisions required · {errors} source warnings")
        self.db.set_meta("last_scan_at", utcnow())
        return self.bootstrap()

    async def _scan_documents(self, files: dict[str, str]) -> int:
        matched = 0
        for spec in DOCUMENTS:
            result = await self.context.scrape(spec)
            if result.error:
                source = self.context.error_source(spec, result.error)
                if not self.settings.contextdev_api_key:
                    source["status"] = "unconfigured"
                self.db.save_source(source)
                continue
            events = parse_deprecations(result.data, spec.provider)
            event_count = 0
            for event in events:
                evidence = [{key: value for key, value in item.items() if key != "model"} for item in model_evidence(files, event["model"])]
                if not evidence:
                    continue
                event_count += 1
                model = event["model"]
                special = spec.provider == "OpenAI" and model.lower() == "gpt-4-0314"
                ident = "sig-model-gpt4-0314" if special else stable_id("sig-model", spec.provider, model.lower())
                existing = self.db.get_signal(ident) or {}
                replacement = "gpt-4.1" if special else event.get("replacement")
                # A provider may publish an initial estimate followed by a final shutdown.
                # Use the latest explicit dates, not lexicographic month-name ordering.
                deadline = _latest_date(event.get("shutdown_dates") or [])
                announced = _latest_date(event.get("announcement_dates") or [])
                receipt = {"publisher": spec.provider, "title": spec.title, "url": spec.url, "retrieved_at": result.retrieved_at, "mode": result.mode, "quote": event["quote"]}
                past = bool(deadline and parse_iso(deadline) <= datetime.now(timezone.utc))
                state = existing.get("state") if existing.get("state") in {"acknowledged", "fix_ready"} else "needs_action"
                signal = {
                    "id": ident, "kind": "deprecation", "severity": "critical" if past else "high", "state": state,
                    "title": "A retired model is still configured" if past else "A configured model is approaching retirement",
                    "summary": f"{model} {'was shut down' if past else 'is listed for retirement'}{' on ' + deadline[:10] if deadline else ''}. {len(evidence)} code/config locations select it.",
                    "provider": spec.provider, "affected_assets": ["Support summaries", "Escalation drafts"] if special else sorted({item["file"] for item in evidence}),
                    "deadline": deadline, "announced_at": announced, "cve": None, "cvss": None, "kev": False, "fixed_version": None,
                    "replacement": replacement, "model": model, "reachability": "confirmed",
                    "reachability_reason": "Exact source identifiers confirm configuration, not runtime invocation.",
                    "recommendation": f"Replace it with {replacement} and run existing evaluations before deployment." if replacement else "Select an official replacement from the cited lifecycle table and run existing evaluations before deployment.",
                    "evidence": evidence, "source_receipts": [receipt], "remediation_id": existing.get("remediation_id"),
                    "created_at": existing.get("created_at") or announced or utcnow(),
                }
                self.db.save_signal(signal)
            self.db.save_source({"id": f"src-{spec.key}", "publisher": spec.provider, "title": spec.title, "url": spec.url, "status": result.mode, "last_checked_at": result.retrieved_at, "event_count": event_count, "mode": result.mode, "error": None})
            matched += event_count
        return matched

    async def _scan_vulnerabilities(self, files: dict[str, str], dependencies: list[Dependency]) -> int:
        if not dependencies:
            return 0
        results = [await self.intel.query_package(dependency) for dependency in dependencies]
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
                existing = self.db.get_signal(base_id)
                ident = base_id if not existing or existing.get("affected_package") == dependency.name else f"{base_id}-{_slug(dependency.ecosystem)}-{_slug(dependency.name)}"
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
                self.db.save_signal(signal)
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
        source.update({"status": "error" if errors else "live" if any_live else "cached", "last_checked_at": max((item for item in live_retrievals if item), default=source.get("last_checked_at")), "event_count": matches, "mode": "live" if any_live else source.get("mode", "cached"), "error": safe_excerpt("; ".join(errors), 300) if errors else None})
        self.db.save_source(source)
        cisa = self.db.get_source("src-cisa") or {"id": "src-cisa", "publisher": "CISA", "title": "Known Exploited Vulnerabilities", "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"}
        cisa.update({"status": "error" if kev_result.error else kev_result.mode, "last_checked_at": kev_result.retrieved_at or cisa.get("last_checked_at"), "event_count": sum(cve_id(advisory) in known_exploited for result in results for advisory in result.advisories), "mode": kev_result.mode if not kev_result.error else cisa.get("mode", "cached"), "error": safe_excerpt(kev_result.error, 240) if kev_result.error else None})
        self.db.save_source(cisa)
        return matches
