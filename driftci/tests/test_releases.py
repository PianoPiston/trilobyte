from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import EXAMPLE, make_settings
from server.app import create_app
from server.config import Settings
from server.contextdev import OPENAI_STATUS, status_snapshot
from server.db import Database
from server.scanner import read_text_tree
from server.seed import demo_records
from server.remediation import RemediationError
from server.release_analysis import release_payload
from server.service import DriftService

HEAD = "a" * 40
NEXT = "b" * 40


def pull_request(state: dict) -> dict:
    return {
        "number": 42, "state": "open", "title": "Update support model integration",
        "html_url": "https://github.com/acme/orders/pull/42", "draft": False,
        "created_at": "2026-11-14T08:00:00Z", "updated_at": state["updated_at"],
        "merged_at": None, "changed_files": 1,
        "head": {"sha": state["head"], "label": "acme:model-update"},
        "base": {"ref": "main"}, "user": {"login": "alice"},
    }


def github_handler(state: dict, calls: list[str]):
    def handler(request: httpx.Request):
        calls.append(str(request.url))
        if request.url.host != "api.github.com":
            raise AssertionError(str(request.url))
        if request.url.path.endswith("/pulls") or request.url.path.endswith("/pulls/42"):
            etag = f'"{state["head"]}"'
            if request.headers.get("if-none-match") == etag:
                return httpx.Response(304)
            return httpx.Response(200, json=pull_request(state) if request.url.path.endswith("/42") else [pull_request(state)], headers={"etag": etag})
        if request.url.path.endswith("/pulls/42/files"):
            return httpx.Response(200, json=[{
                "filename": "src/lib/ai.ts", "status": "modified", "additions": 3, "deletions": 1, "changes": 4,
                "patch": '- model: selectModel()\n+ model: selectModel("gpt-4-0314")',
            }])
        if request.url.path.endswith("/pulls/42/reviews"):
            return httpx.Response(200, json=[{
                "id": 901, "state": "APPROVED", "user": {"login": "alice"},
                "submitted_at": "2026-11-14T10:00:00Z", "commit_id": HEAD,
                "html_url": "https://github.com/acme/orders/pull/42#pullrequestreview-901",
            }])
        if request.url.path.endswith(f"/commits/{state['head']}/check-runs"):
            return httpx.Response(200, json={"total_count": 1, "check_runs": [{
                "id": 3001, "name": "model-evaluation", "status": state.get("check_status", "completed"), "conclusion": state.get("check_conclusion", "success"),
                "started_at": "2026-11-14T10:01:00Z", "completed_at": "2026-11-14T10:04:00Z",
                "html_url": "https://github.com/acme/orders/runs/3001",
            }]})
        raise AssertionError(str(request.url))
    return handler


@pytest.fixture
def github_db(tmp_path):
    db = Database(str(tmp_path / "release.db"), EXAMPLE)
    db.replace_workspace({
        "id": "github-acme-orders", "name": "orders", "repository": "acme/orders",
        "branch": "main", "environment": "Production", "source": "github",
    }, read_text_tree(EXAMPLE))
    for signal in demo_records(read_text_tree(EXAMPLE))["signals"]:
        if signal["kind"] == "deprecation":
            db.save_signal(signal)
    try:
        yield db
    finally:
        db.close()


def run_with_service(db: Database, settings: Settings, handler, operation):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await operation(DriftService(db, settings, http))
    return asyncio.run(run())


def test_removed_or_deleted_model_configuration_does_not_trigger_branch_warning(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    settings = make_settings(tmp_path, offline=False)
    run_with_service(github_db, settings, github_handler(state, []), lambda service: service.refresh_releases(include_status=False))
    pr = github_db.get_pull_request("pr-42")
    pr["files"][0]["patch"] = '- const model = "gpt-4-0314"\n+ const model = "gpt-4.1"'
    github_db.save_pull_request(pr)
    current = release_payload(github_db, read_text_tree(EXAMPLE), github_db.list_signals(), {})["pull_requests"][0]
    assert not [item for item in current["external_evidence"] if item["kind"] == "deprecation"]
    pr["files"][0]["status"] = "removed"
    pr["files"][0]["patch"] = '- const model = "gpt-4-0314"'
    github_db.save_pull_request(pr)
    current = release_payload(github_db, read_text_tree(EXAMPLE), github_db.list_signals(), {})["pull_requests"][0]
    assert not [item for item in current["external_evidence"] if item["kind"] == "deprecation"]


def test_ready_decision_expires_on_new_external_evidence(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    calls = []
    settings = make_settings(tmp_path, offline=False, release_poll_interval_seconds=0)
    result = run_with_service(github_db, settings, github_handler(state, calls), lambda service: service.refresh_releases(include_status=False))
    pr = result["release"]["pull_requests"][0]
    assert pr["detail_complete"] is True
    assert pr["external_evidence"]
    assert pr["readiness"] == "needs_review"
    assert all(event["baseline"] for event in result["release"]["events"])
    assert result["release"]["counts"]["live_events"] == 0
    ready = run_with_service(github_db, settings, github_handler(state, calls), lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "ready", "Release owner", "Evaluations pass and current model evidence is understood."))
    assert ready["release"]["pull_requests"][0]["readiness"] == "ready"

    signal = github_db.get_signal("sig-model-gpt4-0314")
    signal["observed_at"] = "2026-11-15T04:00:00Z"
    github_db.save_signal(signal)
    stale = service_payload(github_db, settings)
    pr = stale["release"]["pull_requests"][0]
    assert pr["readiness"] == "evidence_stale"
    assert pr["outdated_remote_review"] is True
    assert pr["release_decision"] is None
    assert pr["expired_release_decision"]["decision"] == "ready"


def service_payload(db, settings):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as http:
            return DriftService(db, settings, http).bootstrap()
    return asyncio.run(run())


def test_human_review_transitions_do_not_expire_a_decision(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    settings = make_settings(tmp_path, offline=False)
    result = run_with_service(github_db, settings, github_handler(state, []), lambda service: service.refresh_releases(include_status=False))
    evidence_hash = result["release"]["pull_requests"][0]["evidence_hash"]
    run_with_service(github_db, settings, lambda request: httpx.Response(500), lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "ready", "Release owner", "The cited lifecycle fact has been validated."))
    reviewed = run_with_service(github_db, settings, lambda request: httpx.Response(500), lambda service: asyncio.to_thread(service.update_signal_state, "sig-model-gpt4-0314", "acknowledged"))
    assert reviewed["state"] == "acknowledged"
    current = service_payload(github_db, settings)["release"]["pull_requests"][0]
    assert current["evidence_hash"] == evidence_hash
    assert current["readiness"] == "ready"
    run_with_service(github_db, settings, lambda request: httpx.Response(500), lambda service: asyncio.to_thread(service.update_signal_state, "sig-model-gpt4-0314", "resolved"))
    current = service_payload(github_db, settings)["release"]["pull_requests"][0]
    assert current["evidence_hash"] == evidence_hash
    assert current["active_external_count"] == 0
    assert current["readiness"] == "ready"


def test_stale_github_evidence_cannot_be_recorded_ready(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    settings = make_settings(tmp_path, offline=False)
    run_with_service(github_db, settings, github_handler(state, []), lambda service: service.refresh_releases(include_status=False))
    health = github_db.get_meta("github_release_health", {})
    health["last_error"] = "GitHub API is rate limited"
    github_db.set_meta("github_release_health", health)
    with pytest.raises(RemediationError, match="stale"):
        run_with_service(github_db, settings, github_handler(state, []), lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "ready", "Owner", "Retained source is stale."))


def test_oversized_diff_is_incomplete_without_repeated_refetch(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    calls = []
    base_handler = github_handler(state, calls)

    def handler(request):
        response = base_handler(request)
        if response.status_code == 200 and request.url.path.endswith("/files"):
            rows = response.json()
            rows[0]["patch"] = "+" + "a" * 13_000
            return httpx.Response(200, json=rows)
        return response

    settings = make_settings(tmp_path, offline=False)
    first = run_with_service(github_db, settings, handler, lambda service: service.refresh_releases(include_status=False))
    pr = first["release"]["pull_requests"][0]
    assert pr["detail_complete"] is False
    assert pr["files"][0]["patch_complete"] is False
    assert first["release"]["status"]["detail_pending"] == 0
    with pytest.raises(RemediationError, match="coverage is incomplete"):
        run_with_service(github_db, settings, handler, lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "ready", "Owner", "Bounded patch is not complete."))
    second = run_with_service(github_db, settings, handler, lambda service: service.refresh_releases(include_status=False))
    assert sum(url.split("?", 1)[0].endswith("/files") for url in calls) == 1
    assert second["release"]["status"]["last_transport_mode"] == "cached"
    assert second["release"]["pull_requests"][0]["detail_complete"] is False


def test_pending_checks_reconcile_and_expire_the_prior_hold(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD, "check_status": "in_progress", "check_conclusion": None}
    calls = []
    settings = make_settings(tmp_path, offline=False)
    refresh = lambda service: service.refresh_releases(include_status=False)
    first = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    assert first["release"]["pull_requests"][0]["readiness"] == "checks_running"
    with pytest.raises(RemediationError, match="running or failing"):
        run_with_service(github_db, settings, github_handler(state, calls), lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "ready", "Owner", "CI has not finished."))
    paused = run_with_service(github_db, settings, github_handler(state, calls), lambda service: asyncio.to_thread(service.record_release_decision, "pr-42", "hold", "Owner", "Wait for CI."))
    assert paused["release"]["pull_requests"][0]["readiness"] == "paused"
    second = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    assert second["release"]["pull_requests"][0]["check_summary"]["state"] == "pending"
    assert sum("/check-runs" in url for url in calls) == 2

    state.update(check_status="completed", check_conclusion="success")
    completed = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    pr = completed["release"]["pull_requests"][0]
    assert pr["check_summary"]["state"] == "passed"
    assert pr["readiness"] == "evidence_stale"
    assert pr["expired_release_decision"]["decision"] == "hold"
    assert sum("/check-runs" in url for url in calls) == 3
    assert any(event["kind"] == "checks" and not event["baseline"] for event in completed["release"]["events"])


def test_changed_head_emits_once_and_etags_keep_quiet_polling_event_free(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    calls = []
    settings = make_settings(tmp_path, offline=False, release_poll_interval_seconds=0)
    refresh = lambda service: service.refresh_releases(include_status=False)
    first = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    baseline_count = len(first["release"]["events"])
    state.update(updated_at="2026-11-15T03:20:00Z", head=NEXT)
    changed = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    pr = changed["release"]["pull_requests"][0]
    assert pr["head_sha"] == NEXT
    assert any(event["kind"] == "commit" and not event["baseline"] for event in changed["release"]["events"])
    assert pr["current_head_approval"] is None
    event_count = len(changed["release"]["events"])
    assert event_count > baseline_count
    quiet = run_with_service(github_db, settings, github_handler(state, calls), refresh)
    assert len(quiet["release"]["events"]) == event_count
    assert sum(url.endswith("/pulls?state=all&sort=updated&direction=desc&per_page=10") for url in calls) == 3


@pytest.mark.parametrize("headers_supplied", [True, False])
def test_rate_limit_backoff_suppresses_scheduled_requests(tmp_path, github_db, headers_supplied):
    calls = []
    reset = int(time.time()) + 180

    def handler(request):
        calls.append(str(request.url))
        if request.url.path.endswith("/rate_limit"):
            return httpx.Response(200, json={"resources": {"core": {"remaining": 0, "reset": reset}}})
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)} if headers_supplied else {}
        return httpx.Response(403, json={"message": "API rate limit exceeded"}, headers=headers)

    settings = make_settings(tmp_path, offline=False)
    first = run_with_service(github_db, settings, handler, lambda service: service.refresh_releases(include_status=False))
    assert "rate limit reached" in first["release"]["status"]["last_error"]
    assert first["release"]["status"]["retry_after_seconds"] > 0
    assert abs(first["release"]["status"]["retry_not_before_epoch"] - reset) <= 2
    second = run_with_service(github_db, settings, handler, lambda service: service.refresh_releases(include_status=False))
    assert sum("/pulls" in url for url in calls) == 1
    assert "retry window" in second["release"]["status"]["last_error"]
    assert second["release"]["status"]["rate_limit_reset_epoch"] == reset


def test_partial_pr_evidence_cannot_be_called_ready(tmp_path, github_db):
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    settings = make_settings(tmp_path, offline=False, release_poll_interval_seconds=0, release_detail_limit=0)
    refreshed = run_with_service(github_db, settings, github_handler(state, []), lambda service: service.refresh_releases(include_status=False))
    assert refreshed["release"]["pull_requests"][0]["detail_complete"] is False
    with pytest.raises(RemediationError, match="coverage is incomplete"):
        async def decide():
            async with httpx.AsyncClient() as http:
                return DriftService(github_db, settings, http).record_release_decision("pr-42", "ready", "Reviewer", "")
        asyncio.run(decide())


def test_webhook_signature_deduplication_and_sse_cursor(tmp_path):
    settings = make_settings(tmp_path, offline=False, release_webhook_secret="hook-secret", release_poll_interval_seconds=0, release_manual_cooldown_seconds=0, release_detail_limit=0)
    state = {"updated_at": "2026-11-15T03:00:00Z", "head": HEAD}
    payload = {"repository": {"full_name": "acme/orders"}, "number": 42, "pull_request": pull_request(state)}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"hook-secret", raw, hashlib.sha256).hexdigest()
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "13ad6b20-d3b5-49d8-aa7c-111111111111", "X-Hub-Signature-256": signature, "Content-Type": "application/json"}
    with TestClient(create_app(settings, httpx.MockTransport(github_handler(state, [])))) as client:
        db = client.app.state.service.db
        db.replace_workspace({"id": "github-acme-orders", "name": "orders", "repository": "acme/orders", "branch": "main", "environment": "Production", "source": "github"}, read_text_tree(EXAMPLE))
        assert client.post("/api/github/webhook", content=raw, headers={**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}).status_code == 401
        response = client.post("/api/github/webhook", content=raw, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] is True
        duplicate = client.post("/api/github/webhook", content=raw, headers=headers)
        assert duplicate.json()["duplicate"] is True
        assert len([event for event in db.list_release_events() if event["kind"] == "webhook"]) == 1
        last = db.latest_release_event_seq()
        with client.stream("GET", "/api/events/stream?after=0") as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            lines = stream.iter_lines()
            assert next(lines).startswith(": release stream connected")
            events = []
            for line in lines:
                if line.startswith("event: update"):
                    events.append(line)
                if len(events) == 2:
                    break
            assert len(events) == 2
            assert db.latest_release_event_seq() == last
        assert client.get("/api/events/stream", headers={"Last-Event-ID": "invalid"}).status_code == 400


def test_context_status_change_invalidates_a_matching_release(tmp_path, github_db):
    phase = {"text": "API\nOperational"}
    github_db.save_pull_request({
        "id": "pr-42", "number": 42, "state": "open", "title": "Update support model integration",
        "repository": "acme/orders", "url": "https://github.com/acme/orders/pull/42", "head_sha": HEAD,
        "author": "alice", "created_at": "2026-11-14T08:00:00Z", "updated_at": "2026-11-15T03:00:00Z",
        "files": [{"path": "src/lib/ai.ts", "status": "modified", "additions": 2, "deletions": 1, "changes": 3, "patch": "gpt-4-0314"}],
        "changed_files": 1, "files_complete": True, "reviews_complete": True, "checks_complete": True, "detail_complete": True,
        "reviews": [{"id": "901", "state": "APPROVED", "reviewer": "alice", "submitted_at": "2026-11-14T10:00:00Z", "commit_sha": HEAD, "url": None}],
        "checks": [{"id": "3001", "name": "model-evaluation", "status": "completed", "conclusion": "success", "started_at": None, "completed_at": None, "url": None}],
        "check_summary": {"state": "passed", "total": 1, "pending": 0, "failed": 0, "passed": 1},
    })
    github_db.set_meta("github_release_health", {"last_success_at": "2026-11-15T03:01:00Z", "last_transport_mode": "live", "last_error": None})
    settings = make_settings(tmp_path, offline=False, contextdev_api_key="test-secret", release_poll_interval_seconds=0)

    def handler(request: httpx.Request):
        assert request.url.path.endswith("/web/scrape")
        return httpx.Response(200, json={"markdown": {"success": True, "data": phase["text"]}, "key_metadata": {"credits_consumed": 1}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = DriftService(github_db, settings, http)
            service.record_release_decision("pr-42", "ready", "Release owner", "Baseline checked")
            await service._scan_documents(github_db.files(), [OPENAI_STATUS], research=False, hot=True)
            assert service.bootstrap()["release"]["pull_requests"][0]["readiness"] == "ready"
            # Expire the hot-watch cache without sleeping through its real cadence.
            key = f"context:v2:{OPENAI_STATUS.scrape_url}"
            github_db.cache_set(key, time.time() - 60, github_db.cache_get(key))
            phase["text"] = "API\nDegraded performance\nInvestigating elevated errors"
            await service._scan_documents(github_db.files(), [OPENAI_STATUS], research=False, hot=True)
            return service.bootstrap()

    result = asyncio.run(run())
    pr = result["release"]["pull_requests"][0]
    assert pr["readiness"] == "evidence_stale"
    assert pr["outdated_remote_review"] is True
    status = next(signal for signal in result["signals"] if signal["kind"] == "status")
    assert status["severity"] == "high"
    assert status["evidence"]
    assert result["changes"][-1]["added"]
    assert any(event["kind"] == "web_change" and event["affected_pr_numbers"] == [42] for event in result["release"]["events"])
    assert status_snapshot("Navigation\nAPI\nOperational").splitlines() == ["API", "Operational"]
