#!/usr/bin/env python3
"""End-to-end DriftCI smoke test against a running API.

Usage: .venv/bin/python scripts/smoke.py [http://127.0.0.1:8100]
Set DRIFTCI_SMOKE_LIVE=1 to include the real Context.dev/OSV/CISA scan.
The script resets the demo before and after its assertions.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("DRIFTCI_URL", "http://127.0.0.1:8100")).rstrip("/")


def request(method: str, path: str, body=None, expected=(200,)):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
        content_type = error.headers.get("content-type", "")
    assert status in expected, f"{method} {path}: expected {expected}, got {status}: {raw[:800]!r}"
    if "json" in content_type:
        return json.loads(raw)
    return raw


def main():
    request("POST", "/api/demo/reset", {})
    health = request("GET", "/api/health")
    assert health["ok"] is True
    data = request("GET", "/api/bootstrap")
    assert data["workspace"]["repository"]
    assert data["signals"], "seed must contain actionable signals"
    assert data["dependencies"], "repository inventory must not be empty"
    assert any(s["kind"] == "deprecation" for s in data["signals"]), "missing model deprecation"
    assert any(s["kind"] == "vulnerability" for s in data["signals"]), "missing vulnerability signal"

    deprecation = next(s for s in data["signals"] if s["kind"] == "deprecation" and s.get("replacement"))
    remediation = request("POST", "/api/remediations", {"signal_id": deprecation["id"]})
    assert remediation["files"], "remediation has no changed files"
    assert any(f["diff"] for f in remediation["files"]), "remediation did not produce a unified diff"
    assert remediation["checks"], "targeted checks missing"
    assert any(c["status"] == "passed" for c in remediation["checks"]), "no static validation was performed"
    assert not any(c["status"] == "failed" for c in remediation["checks"]), "generated remediation failed its own checks"

    approved = request("POST", f"/api/remediations/{remediation['id']}/approve", {})
    assert approved.get("approved_at"), "approval was not persisted"
    patch = request("GET", f"/api/remediations/{remediation['id']}/patch")
    assert b"diff --git" in patch or b"---" in patch, "patch export is empty"

    if not health.get("github", {}).get("configured"):
        error = request("POST", f"/api/remediations/{remediation['id']}/open-pr", {}, expected=(400, 409, 422))
        assert "patch" in json.dumps(error).lower(), "credential-free PR failure must explain patch export"

    vulnerability = next(s for s in data["signals"] if s["kind"] == "vulnerability" and s.get("fixed_version"))
    security_fix = request("POST", "/api/remediations", {"signal_id": vulnerability["id"]})
    assert any(f["path"].endswith(("package.json", "requirements.txt", "pyproject.toml")) for f in security_fix["files"]), "CVE patch did not change a dependency manifest"
    assert all(vulnerability["fixed_version"] in f["after"] for f in security_fix["files"]), "CVE patch lacks its fixed version"

    incident_response = request("GET", "/api/incidents")
    active = incident_response["active"]
    assert active, "seed must contain an active incident"
    incident = active[0]
    action = next((a for a in incident["actions"] if a["status"] != "done"), incident["actions"][0])
    updated = request("POST", f"/api/incidents/{incident['id']}/actions/{action['id']}", {"status": "done"})
    saved = next(a for a in updated["actions"] if a["id"] == action["id"])
    assert saved["status"] == "done" and saved.get("completed_at"), "incident action timestamp missing"
    report = request("GET", f"/api/incidents/{incident['id']}/report")
    assert incident["cve"].encode() in report and b"Response timeline" in report, "incident report export is incomplete"
    # Restore that checklist item before final reset to exercise both transitions.
    restored = request("POST", f"/api/incidents/{incident['id']}/actions/{action['id']}", {"status": "pending"})
    assert next(a for a in restored["actions"] if a["id"] == action["id"])["status"] == "pending"

    live_result = None
    if os.getenv("DRIFTCI_SMOKE_LIVE") == "1":
        live = request("POST", "/api/scan", expected=(200, 429))
        if "signals" not in live:
            match = re.search(r"Retry in (\d+) seconds", str(live.get("detail", "")), re.I)
            if not match:
                raise AssertionError(f"scan guard returned no actionable retry interval: {live}")
            time.sleep(min(60, int(match.group(1))) + 1)
            live = request("POST", "/api/scan")
        if len(live.get("signals", [])) < 3:
            raise AssertionError("live scan did not produce any changes")
        models = {row["model"] for row in live.get("signals", []) if row["kind"] == "deprecation" and row.get("model")}
        if not {"gpt-4-0314", "o1-mini"}.issubset(models):
            raise AssertionError(f"live model detection incomplete: {sorted(models)}")
        vulnerabilities = [row for row in live["signals"] if row["kind"] == "vulnerability"]
        if not vulnerabilities:
            raise AssertionError("live OSV scan did not produce advisory matches")
        sources = {row["publisher"]: row for row in live.get("sources", [])}
        for name in ("OpenAI", "OSV", "CISA"):
            if sources.get(name, {}).get("status") not in {"live", "cached", "degraded"}:
                raise AssertionError(f"{name} did not return a usable live/cached/degraded result")
        live_result = {
            "signals": len(live["signals"]),
            "production_models": sorted(models),
            "advisory_matches": len(vulnerabilities),
            "source_health": {name: row["status"] for name, row in sources.items()},
            "context_queries": live["metrics"]["context_queries"],
        }

    request("POST", "/api/demo/reset", {})
    print(json.dumps({
        "ok": True,
        "url": BASE,
        "signals": len(data["signals"]),
        "dependencies": len(data["dependencies"]),
        "incidents": len(active),
        "remediation_files": [f["path"] for f in remediation["files"]],
        "security_remediation_files": [f["path"] for f in security_fix["files"]],
        "live_scan": live_result,
    }, indent=2))


if __name__ == "__main__":
    main()
