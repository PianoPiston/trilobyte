"""Deterministic text patches and targeted static validation; never runs repository tooling."""
from __future__ import annotations

import difflib
import json
import re

from .scanner import model_evidence
from .util import stable_id, utcnow
from .versioning import Version


class RemediationError(ValueError):
    pass


def unified(path: str, before: str, after: str) -> tuple[str, int, int]:
    lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))
    additions = sum(line.startswith("+") and not line.startswith("+++") for line in lines)
    deletions = sum(line.startswith("-") and not line.startswith("---") for line in lines)
    return ("\n".join(lines) + "\n") if lines else "", additions, deletions


def _model_changes(files: dict[str, str], signal: dict) -> tuple[dict[str, str], list[dict]]:
    evidence = model_evidence(files)
    models = {item["model"] for item in evidence}
    old_model = signal.get("model")
    if not old_model:
        # Seeded IDs and evidence quotes both carry the exact identifier; derive only from evidence for live records.
        cves = signal.get("evidence") or []
        snippets = " ".join(item.get("snippet", "") for item in cves)
        old_model = next((model for model in models if model in snippets), "gpt-4-0314" if signal["id"] == "sig-model-gpt4-0314" else None)
    replacement = signal.get("replacement")
    if not old_model or not replacement:
        raise RemediationError("This signal has no deterministic model replacement; follow its cited official guidance")
    paths = sorted({item["file"] for item in model_evidence(files, old_model)})
    if not paths:
        raise RemediationError("The configured model is no longer present; no patch was generated")
    changed = {}
    pattern = re.compile(rf"(?<![\w.-]){re.escape(old_model)}(?![\w.-])")
    for path in paths:
        after, count = pattern.subn(replacement, files[path])
        if count:
            changed[path] = after
    checks = [
        {"name": "Retired identifier removed", "status": "passed" if all(old_model not in content for content in changed.values()) else "failed", "detail": f"No references to {old_model} remain in changed files"},
        {"name": "Targeted configuration check", "status": "passed" if all(replacement in content for content in changed.values()) else "failed", "detail": f"Replacement {replacement} is explicit and reviewable"},
    ]
    return changed, checks


def _package_json_change(content: str, package: str, fixed: str) -> str:
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RemediationError("package.json is not valid JSON") from exc
    declared = any(package in (manifest.get(section) or {}) for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"))
    if not declared:
        raise RemediationError(f"{package} is not declared in package.json")
    pattern = re.compile(rf'(?m)^(\s*"{re.escape(package)}"\s*:\s*")[^"]*(")')
    after, count = pattern.subn(rf"\g<1>{fixed}\g<2>", content)
    if not count:
        raise RemediationError(f"Could not locate a reviewable declaration for {package}")
    return after


def _python_change(content: str, package: str, fixed: str) -> str:
    normalized = re.escape(package).replace(r"\-", "[-_]")
    exact = re.compile(rf"(?mi)^(\s*{normalized}\s*(?:\[[^]]+\]\s*)?(?:==)?\s*)([0-9][A-Za-z0-9.*+!_-]*)(.*)$")
    def replace(match: re.Match) -> str:
        prefix = match.group(1)
        if "==" in prefix:
            return prefix + fixed + match.group(3)
        return prefix
    after, count = exact.subn(replace, content)
    if fixed not in after:
        # Exact poetry entries have no == operator.
        poetry = re.compile(rf'(?mi)^(\s*{normalized}\s*=\s*")[^"]*(".*)$')
        after, count = poetry.subn(rf"\g<1>{fixed}\g<2>", after)
    if fixed not in after:
        raise RemediationError(f"Could not locate an exact {package} dependency declaration")
    return after


def _vulnerability_changes(files: dict[str, str], signal: dict) -> tuple[dict[str, str], list[dict]]:
    package = signal.get("affected_package")
    fixed = signal.get("fixed_version")
    if not package or not fixed:
        raise RemediationError("The advisory does not provide a deterministic fixed version; follow its linked guidance")
    try:
        current = Version.parse(signal["affected_version"])
        target = Version.parse(fixed)
    except (KeyError, ValueError) as exc:
        raise RemediationError("The dependency versions are not concrete supported releases") from exc
    if target <= current:
        raise RemediationError("The fixed version must be newer than the installed version")
    ecosystem = signal.get("ecosystem")
    changed = {}
    if ecosystem == "npm":
        if "package.json" not in files:
            raise RemediationError("package.json is absent")
        changed["package.json"] = _package_json_change(files["package.json"], package, fixed)
    elif ecosystem == "PyPI":
        for path in (signal.get("manifest"), "requirements.txt", "requirements.lock", "pyproject.toml"):
            if path and path in files and package.lower() in files[path].lower():
                try:
                    changed[path] = _python_change(files[path], package, fixed)
                    break
                except RemediationError:
                    continue
        if not changed:
            raise RemediationError("No exact Python dependency declaration could be patched")
    else:
        raise RemediationError(f"Patches for ecosystem {ecosystem or 'unknown'} are not supported")
    checks = [{"name": "Targeted fixed-version declaration", "status": "passed" if all(fixed in content for content in changed.values()) else "failed", "detail": f"{package} is pinned to {fixed} in the changed declaration"}]
    if ecosystem == "npm" and "package-lock.json" in files:
        checks.append({"name": "Lockfile refresh", "status": "pending", "detail": "Regenerate and verify package-lock.json in CI; DriftCI did not guess registry integrity hashes or execute package tooling"})
    return changed, checks


def generate(files: dict[str, str], signal: dict, github_configured: bool) -> dict:
    before_all = {path: files[path] for path in files}
    if signal["kind"] == "deprecation":
        changed, checks = _model_changes(files, signal)
        title = "Replace retired OpenAI snapshot" if signal.get("provider") == "OpenAI" else f"Replace retired {signal.get('provider', 'provider')} snapshot"
    elif signal["kind"] == "vulnerability":
        changed, checks = _vulnerability_changes(files, signal)
        title = f"Upgrade {signal.get('affected_package')} to a fixed release"
    else:
        raise RemediationError(f"No deterministic patch generator exists for {signal['kind']} signals")
    patched = dict(files)
    patched.update(changed)
    rows = []
    for path, after in sorted(changed.items()):
        before = before_all[path]
        if before == after:
            continue
        diff, additions, deletions = unified(path, before, after)
        rows.append({"path": path, "before": before, "after": after, "diff": diff, "additions": additions, "deletions": deletions})
    if not rows or any(check["status"] == "failed" for check in checks):
        raise RemediationError("Static validation rejected the generated patch")
    checks.append({"name": "Repository tests", "status": "pending", "detail": "Run application tests in its own CI. DriftCI performs static checks only and never executes repository code."})
    identity = "|".join(f"{row['path']}:{stable_id('content', row['after'], length=64)}" for row in rows)
    ident = stable_id("rem", signal["id"], identity, length=12)
    return {
        "id": ident,
        "signal_id": signal["id"],
        "title": title,
        "status": "ready_for_review",
        "summary": f"{len(rows)} file{'s' if len(rows) != 1 else ''} changed · {len(checks)} targeted checks",
        "files": rows,
        "checks": checks,
        "source_receipts": signal.get("source_receipts") or [],
        "can_open_pr": github_configured,
        "created_at": utcnow(),
        "approved_at": None,
        "pr_url": None,
        "pr_number": None,
    }


def patch_text(remediation: dict) -> str:
    return "".join(row["diff"] for row in remediation["files"])
