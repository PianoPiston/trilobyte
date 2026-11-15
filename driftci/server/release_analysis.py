"""Join public PR state to external evidence without changing GitHub review state."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

from .db import Database

def _exact_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<![\w@/.-]){re.escape(term.lower())}(?![\w@/.-])", text))


def observed_at(signal: dict) -> str | None:
    """Observation time is separate from an advisory's historical publication date."""
    return signal.get("observed_at") or (signal.get("change") or {}).get("observed_at")


def review_diff(pr: dict) -> tuple[set[str], list[tuple[str, str]]]:
    """Return current file paths and added/context lines, never deleted code."""
    paths = {item["path"] for item in pr.get("files", []) if item.get("status") != "removed"}
    diffs = []
    for item in pr.get("files", []):
        if item.get("status") == "removed":
            continue
        lines = [line[1:] for line in (item.get("patch") or "").splitlines() if line.startswith(("+", " ")) and not line.startswith("+++")]
        diffs.append((item["path"], "\n".join(lines).lower()))
    return paths, diffs


def _matched_signals(pr: dict, signals: list[dict]) -> list[dict]:
    paths, diffs = review_diff(pr)
    patch_text = "\n".join(text for _, text in diffs)
    matches = []
    for signal in signals:
        terms = {signal.get(field) for field in ("affected_package", "model")}
        terms.update(signal.get("affected_assets") or [])
        terms = {str(term).lower() for term in terms if isinstance(term, str) and len(term) >= 3}
        evidence = signal.get("evidence") or signal.get("affected_files") or []
        touched = set(paths.intersection(item.get("file") for item in evidence if item.get("file")))
        touched.update(path for path, text in diffs if any(_exact_term(text, term) for term in terms))
        term_in_current_diff = any(_exact_term(patch_text, term) for term in terms)
        if not term_in_current_diff and (signal["kind"] == "deprecation" or not touched):
            continue
        matches.append({
            "id": signal["id"], "kind": signal["kind"], "severity": signal["severity"], "state": signal["state"],
            "title": signal["title"], "summary": signal["summary"], "provider": signal["provider"],
            "created_at": signal["created_at"], "observed_at": observed_at(signal),
            "matched_files": sorted(touched)[:12], "evidence": deepcopy(evidence[:8]),
            "source_receipts": deepcopy(signal.get("source_receipts", [])[:6]),
            "change": deepcopy(signal.get("change")),
        })
    return sorted(matches, key=lambda item: ((observed_at(item) or item["created_at"]), item["id"]), reverse=True)[:12]


def release_payload(db: Database, files: dict[str, str], signals: list[dict], health: dict) -> dict:
    """Attach locally persisted decisions to the exact PR head and evidence snapshot."""
    prs = []
    for stored in db.list_pull_requests():
        pr = deepcopy(stored)
        matches = _matched_signals(pr, signals)
        active_matches = [item for item in matches if item["state"] != "resolved"]
        observations = [item["observed_at"] for item in matches if item.get("observed_at")]
        latest_observed = max(observations, default=None)
        approvals = [
            item for item in pr.get("reviews", [])
            if item.get("state") == "APPROVED" and item.get("submitted_at")
        ]
        latest_approval = max((item["submitted_at"] for item in approvals), default=None)
        current_head_approval = max((item["submitted_at"] for item in approvals if item.get("commit_sha") == pr["head_sha"]), default=None)
        # Human workflow transitions are not new external evidence. Bind a
        # decision to the observed facts and relevant source fingerprints instead.
        evidence_hash = hashlib.sha256(json.dumps([
            {
                "id": item["id"], "observed_at": item.get("observed_at"),
                "change_hash": (item.get("change") or {}).get("content_hash"),
                "deadline": item.get("deadline"), "cvss": item.get("cvss"),
                "fixed_version": item.get("fixed_version"), "matched_files": item["matched_files"],
                "sources": [{"url": receipt.get("url"), "quote": receipt.get("quote")} for receipt in item["source_receipts"]],
                "checks": [{"id": check["id"], "status": check["status"], "conclusion": check.get("conclusion")} for check in pr.get("checks", [])],
            }
            for item in matches
        ], sort_keys=True).encode()).hexdigest()[:16]
        stored_decision = db.release_decision(pr["id"])
        decision = stored_decision if stored_decision and stored_decision.get("head_sha") == pr["head_sha"] and stored_decision.get("evidence_hash") == evidence_hash else None
        checks = pr.get("check_summary") or {"state": "none"}
        active_observations = [item["observed_at"] for item in active_matches if item.get("observed_at")]
        latest_active_observed = max(active_observations, default=None)
        outdated_remote_review = bool(latest_approval and latest_active_observed and latest_active_observed > latest_approval)
        if pr["state"] != "open":
            readiness = "merged" if pr.get("merged") else "closed"
        elif stored_decision and stored_decision.get("head_sha") != pr["head_sha"]:
            readiness = "head_changed"
        elif stored_decision and stored_decision.get("evidence_hash") != evidence_hash:
            readiness = "evidence_stale"
        elif decision and decision["decision"] == "hold":
            readiness = "paused"
        elif checks.get("state") == "failed":
            readiness = "checks_failed"
        elif checks.get("state") == "pending":
            readiness = "checks_running"
        elif outdated_remote_review:
            readiness = "review_stale"
        elif decision and decision["decision"] == "ready":
            readiness = "ready"
        elif active_matches:
            readiness = "needs_review"
        else:
            readiness = "observing"
        pr["files"] = [{key: value for key, value in item.items() if key != "patch"} for item in pr.get("files", [])]
        pr["external_evidence"] = matches
        pr["active_external_count"] = len(active_matches)
        pr["latest_external_observation"] = latest_observed
        pr["latest_remote_approval"] = latest_approval
        pr["current_head_approval"] = current_head_approval
        pr["outdated_remote_review"] = outdated_remote_review
        pr["evidence_hash"] = evidence_hash
        pr["release_decision"] = decision
        pr["expired_release_decision"] = stored_decision if stored_decision and not decision else None
        pr["readiness"] = readiness
        pr.pop("checks_hash", None)
        prs.append(pr)
    prs.sort(key=lambda item: item["updated_at"], reverse=True)
    prs.sort(key=lambda item: (item["state"] != "open", item["readiness"] != "review_stale"))
    events = db.list_release_events(limit=80)
    return {
        "pull_requests": prs,
        "events": events,
        "latest_seq": db.latest_release_event_seq(),
        "status": health,
        "counts": {
            "open": sum(pr["state"] == "open" for pr in prs),
            "needs_review": sum(pr["readiness"] in {"needs_review", "head_changed", "evidence_stale", "review_stale", "checks_failed"} for pr in prs),
            "ready": sum(pr["readiness"] == "ready" for pr in prs),
            "live_events": sum(not event.get("baseline") for event in events),
        },
    }
