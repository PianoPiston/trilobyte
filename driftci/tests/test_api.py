from __future__ import annotations

from fastapi.testclient import TestClient

from server.app import create_app
from server.seed import NEXT_CVE_URL

from conftest import make_settings


def test_bootstrap_health_and_seed_source_mapping(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["last_scan_at"] is None
    payload = client.get("/api/bootstrap").json()
    assert payload["metrics"]["files_indexed"] == 15
    assert payload["summary"]["production_models"] == 2
    assert payload["summary"]["active_changes"] == 2
    assert payload["summary"]["affected_dependencies"] == 2
    signal = client.get("/api/signals/sig-model-gpt4-0314").json()
    assert signal["replacement"] == "gpt-4.1"
    assert len(signal["evidence"]) == 2
    assert signal["deadline"] == "2026-03-26T00:00:00Z"
    assert signal["announced_at"] == "2025-09-26T00:00:00Z"
    cve = client.get("/api/signals/sig-CVE-2025-29927").json()
    assert cve["source_receipts"][0]["url"] == NEXT_CVE_URL == "https://osv.dev/vulnerability/GHSA-f82v-jwr5-mffw"
    assert cve["source_receipts"][0]["mode"] == "historical_snapshot"
    assert len(payload["history"]) == 1
    assert payload["history"][0]["state"] == "resolved"


def test_signal_filters(client):
    response = client.get("/api/signals?kind=vulnerability&severity=critical")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == ["sig-CVE-2025-29927"]
    assert client.get("/api/signals/does-not-exist").status_code == 404
    assert client.get("/api/signals?kind=unknown").status_code == 422


def test_model_remediation_approval_real_patch_and_no_token_behavior(client):
    request = {"signal_id": "sig-model-gpt4-0314"}
    response = client.post("/api/remediations", json=request)
    assert response.status_code == 200, response.text
    remediation = response.json()
    assert {row["path"] for row in remediation["files"]} == {"src/lib/ai.ts", "src/jobs/escalation.ts"}
    assert all("gpt-4.1" in row["after"] for row in remediation["files"])
    assert all("gpt-4-0314" not in row["after"] for row in remediation["files"])
    assert all(row["diff"].startswith(f"--- a/{row['path']}") for row in remediation["files"])
    assert remediation["can_open_pr"] is False
    assert client.post("/api/remediations", json=request).json()["id"] == remediation["id"]
    ident = remediation["id"]
    assert client.get(f"/api/remediations/{ident}/patch").status_code == 409
    approved = client.post(f"/api/remediations/{ident}/approve").json()
    assert approved["status"] == "approved" and approved["approved_at"]
    patch = client.get(f"/api/remediations/{ident}/patch")
    assert patch.status_code == 200
    assert patch.headers["content-type"].startswith("text/x-patch")
    assert "--- a/src/lib/ai.ts" in patch.text and "+++ b/src/jobs/escalation.ts" in patch.text
    denied = client.post(f"/api/remediations/{ident}/open-pr")
    assert denied.status_code == 409
    assert "Export the approved unified patch" in denied.json()["detail"]
    reset = client.post("/api/demo/reset").json()
    assert reset["summary"]["remediations_ready"] == 0


def test_incident_actions_validate_order_and_resolution(client):
    base = "/api/incidents/inc-CVE-2025-29927/actions"
    assert client.post(f"{base}/verify", json={"status": "done"}).status_code == 409
    for action in ("contain", "patch", "verify", "resolve"):
        response = client.post(f"{base}/{action}", json={"status": "done"})
        assert response.status_code == 200, response.text
    assert response.json()["state"] == "resolved"
    incidents = client.get("/api/incidents").json()
    assert incidents["metrics"]["active"] == 0
    assert {item["id"] for item in incidents["history"]} == {"inc-CVE-2025-29927", "inc-CVE-2024-34351"}
    assert client.post(f"{base}/contain", json={"status": "pending"}).status_code == 409
    assert client.post(f"{base}/resolve", json={"status": "invalid"}).status_code == 422
    report = client.get("/api/incidents/inc-CVE-2025-29927/report")
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    assert "| Resolve & document | done |" in report.text
    assert "GHSA-f82v-jwr5-mffw" in report.text
    assert client.get("/api/incidents/not-an-incident/report").status_code == 404


def test_replay_is_explicit_historical_replay(client):
    payload = client.post("/api/demo/replay").json()
    signal = next(row for row in payload["signals"] if row["id"] == "sig-model-gpt4-0314")
    assert signal["source_receipts"][0]["mode"] == "historical_replay"
    assert payload["activity"][0]["type"] == "replay"
    assert "not a new announcement" in payload["activity"][0]["detail"]


def test_safe_spa_mount(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<main>DriftCI</main>")
    (dist / "app.js").write_text("console.log('ok')")
    with TestClient(create_app(make_settings(tmp_path, web_dist=dist))) as client:
        assert client.get("/mission-control").text == "<main>DriftCI</main>"
        assert client.get("/app.js").text == "console.log('ok')"
        assert client.get("/missing.js").status_code == 404
        assert client.get("/api/not-a-route").status_code == 404
