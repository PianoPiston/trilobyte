"""Deterministic snapshots and compact diffs for Context.dev documents."""
from __future__ import annotations

import difflib
import hashlib
import re

from .contextdev import DocumentSpec
from .util import safe_excerpt, stable_id


def _lines(text: str) -> list[str]:
    return [re.sub(r"[ \t]+", " ", line.strip()) for line in text.splitlines() if line.strip()]


def capture_change(spec: DocumentSpec, text: str, previous: dict, retrieved_at: str, mode: str) -> tuple[dict | None, dict]:
    """Compare a normalized document with its last snapshot and return one bounded observation."""
    normalized = _lines(text)
    fingerprint = hashlib.sha256("\n".join(normalized).encode()).hexdigest()
    state = {
        "content_hash": fingerprint,
        "baseline_at": previous.get("baseline_at") or retrieved_at,
        "_snapshot": "\n".join(normalized)[:120_000],
    }
    if previous.get("content_hash") == fingerprint:
        return None, state
    if not previous.get("content_hash") or not isinstance(previous.get("_snapshot"), str):
        return None, state

    before = _lines(previous["_snapshot"])
    added: list[str] = []
    removed: list[str] = []
    added_count = 0
    removed_count = 0
    for line in difflib.unified_diff(before, normalized, n=0, lineterm=""):
        if line.startswith("+") and not line.startswith("+++"):
            added_count += 1
            if len(added) < 14 and line[1:].strip():
                added.append(safe_excerpt(line[1:], 500))
        elif line.startswith("-") and not line.startswith("---"):
            removed_count += 1
            if len(removed) < 14 and line[1:].strip():
                removed.append(safe_excerpt(line[1:], 500))
    if not added_count and not removed_count:
        return None, state

    title = spec.title if spec.provider.lower() in spec.title.lower() else f"{spec.provider} {spec.title}"
    observation = {
        "id": stable_id("obs", spec.key, fingerprint),
        "source_id": f"src-{spec.key}",
        "title": f"{title} changed",
        "url": spec.url,
        "observed_at": retrieved_at,
        "mode": mode,
        "content_hash": fingerprint,
        "previous_hash": previous["content_hash"],
        "added_lines": added_count,
        "removed_lines": removed_count,
        "added": added,
        "removed": removed,
    }
    state["last_changed_at"] = retrieved_at
    return observation, state


def change_kind(observation: dict, spec: DocumentSpec) -> str:
    if spec.category == "status":
        return "status"
    if spec.category == "pricing":
        return "pricing"
    text = " ".join(observation.get("added", []) + observation.get("removed", [])).lower()
    if re.search(r"outage|incident|degraded|service status", text):
        return "status"
    return "api"


def change_severity(observation: dict, spec: DocumentSpec) -> str:
    added = " ".join(observation.get("added", [])).lower()
    if spec.category == "status" and re.search(r"outage|degraded|investigating|under maintenance", added):
        return "high"
    text = " ".join(observation.get("added", []) + observation.get("removed", [])).lower()
    if re.search(r"security|vulnerab|deprecat|retir|shutdown|shut down|breaking", text):
        return "high"
    if spec.category == "pricing" or re.search(r"\bprice|pricing|\bcost\b", text):
        return "medium"
    return "info"
