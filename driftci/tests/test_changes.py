from __future__ import annotations

import json

import httpx

from server.changes import capture_change
from server.contextdev import DOCUMENTS, ContextDev, documents_for, validate_watch_url
from server.scanner import read_text_tree
from server.web import CachedWebClient

from conftest import EXAMPLE, make_settings
from test_contextdev import OPENAI_TABLE


def test_snapshot_establishes_baseline_then_records_compact_diff():
    previous = {}
    first, snapshot = capture_change(DOCUMENTS[0], "price $1\nstable", previous, "2026-11-15T00:00:00Z", "live")
    assert first is None
    same, snapshot = capture_change(DOCUMENTS[0], "price $1\nstable", snapshot, "2026-11-15T01:00:00Z", "cached")
    assert same is None
    changed, snapshot = capture_change(DOCUMENTS[0], "price $2\nstable\nnew migration note", snapshot, "2026-11-15T02:00:00Z", "live")
    assert changed is not None
    assert changed["added_lines"] == 2
    assert changed["removed_lines"] == 1
    assert changed["added"] == ["price $2", "new migration note"]
    assert changed["removed"] == ["price $1"]
    assert changed["previous_hash"] != changed["content_hash"]


def test_watchlist_is_relevant_capped_and_custom_first():
    files = read_text_tree(EXAMPLE)
    specs = documents_for(files, limit=4)
    assert [spec.key for spec in specs] == ["openai-deprecations", "openai-pricing", "openai-status", "openai-python-releases"]
    assert all(spec.category == "deprecations" for spec in documents_for(files, limit=1))
    custom = validate_watch_url("https://status.example.com/openai", "Provider status")
    specs = documents_for(files, [custom], limit=1)
    assert specs == [custom]
    for url in ("http://example.com", "https://127.0.0.1/status", "https://localhost/status", "https://user:pass@example.com"):
        try:
            validate_watch_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe watch URL accepted: {url}")


def test_signal_review_and_custom_watch_lifecycle(client):
    rejected = client.post("/api/watches", json={"url": "https://127.0.0.1/status", "title": "Local"})
    assert rejected.status_code == 400
    assert "Private and local" in rejected.json()["detail"]
    reviewed = client.post("/api/signals/sig-model-gpt4-0314/state", json={"state": "acknowledged"})
    assert reviewed.status_code == 200
    assert reviewed.json()["state"] == "acknowledged"
    assert reviewed.json()["reviewed_at"]
    invalid = client.post("/api/signals/sig-CVE-2025-29927/state", json={"state": "resolved"})
    assert invalid.status_code == 409
    added = client.post("/api/watches", json={"url": "https://status.example.com/openai", "title": "Provider status"})
    assert added.status_code == 200, added.text
    source = next(row for row in added.json()["sources"] if row.get("custom"))
    assert source["title"] == "Provider status"
    key = source["id"].removeprefix("src-")
    removed = client.delete(f"/api/watches/{key}")
    assert removed.status_code == 200
    assert not any(row["id"] == source["id"] for row in removed.json()["sources"])


def test_live_watch_refresh_creates_observations_search_receipts_and_usage(tmp_path):
    phase = {"value": 0}

    def handler(request: httpx.Request):
        if request.url.host == "api.context.dev":
            payload = json.loads(request.content)
            if request.url.path.endswith("/web/search"):
                return httpx.Response(200, json={
                    "results": [{"title": "gpt-4-0314 migration", "url": "https://developers.openai.com/api/docs/migrating", "highlights": ["Official migration guidance <script>alert(1)</script>"]}],
                    "key_metadata": {"credits_consumed": 2},
                })
            url = payload["url"]
            if "deprecations" in url:
                text = OPENAI_TABLE
            elif "pricing" in url:
                text = f"gpt-4-0314 input price ${1 + phase['value']} per million tokens"
            else:
                text = f"## Release v{phase['value'] + 1}\nSecurity and migration notes"
            return httpx.Response(200, json={"markdown": {"success": True, "data": text}, "key_metadata": {"credits_consumed": 1}})
        if request.url.host == "api.osv.dev":
            return httpx.Response(200, json={"vulns": []})
        if request.url.host == "www.cisa.gov":
            return httpx.Response(200, json={"vulnerabilities": []})
        raise AssertionError(str(request.url))

    settings = make_settings(tmp_path, offline=False, contextdev_api_key="test-secret", context_cache_ttl=0)
    from fastapi.testclient import TestClient
    from server.app import create_app

    with TestClient(create_app(settings, httpx.MockTransport(handler))) as client:
        baseline = client.post("/api/scan")
        assert baseline.status_code == 200, baseline.text
        assert baseline.json()["changes"] == []
        assert baseline.json()["release"]["counts"]["live_events"] == 0
        assert baseline.json()["metrics"]["context_queries"] == 7
        assert baseline.json()["metrics"]["context_credits"] == 8
        phase["value"] = 1
        refreshed = client.post("/api/scan")
        assert refreshed.status_code == 200, refreshed.text
        payload = refreshed.json()
        # The five-minute status cache intentionally avoids a second scrape here.
        assert next(row for row in payload["sources"] if row["id"] == "src-openai-status")["status"] == "cached"
        assert len(payload["changes"]) == 4
        assert len([row for row in payload["signals"] if row["kind"] in {"pricing", "api"}]) == 4
        assert payload["metrics"]["context_queries"] == 13
        assert payload["metrics"]["context_credits"] == 15
        assert "gpt-4-0314" in payload["discoveries"][0]["matched_terms"]
        assert "script" not in payload["discoveries"][0]["summary"]
        assert all("_snapshot" not in source for source in payload["sources"])
        pricing = next(signal for signal in payload["signals"] if signal["kind"] == "pricing")
        assert pricing["change"]["added"] == ["gpt-4-0314 input price $2 per million tokens"]
        assert pricing["evidence"]
        assert client.post(f"/api/signals/{pricing['id']}/state", json={"state": "resolved"}).json()["state"] == "resolved"
        health = client.get("/api/health").json()["context_dev"]["usage"]
        assert health["daily_credits"] == 15
        assert health["daily_credit_limit"] == 80


def test_daily_credit_ceiling_blocks_new_calls_but_serves_fresh_cache(tmp_path):
    import asyncio
    from server.db import Database

    calls = 0

    def handler(_request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"markdown": {"success": True, "data": "official docs"}, "key_metadata": {"credits_consumed": 1}})

    async def run():
        db = Database(":memory:")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            context = ContextDev(db, CachedWebClient(db, http, 0, 1), "test-secret", daily_credit_limit=1)
            first = await context.scrape(DOCUMENTS[0])
            cached = await context.scrape(DOCUMENTS[0])
            blocked = await context.scrape(DOCUMENTS[1])
            assert first.mode == "live"
            assert cached.mode == "cached"
            assert blocked.error and "budget" in blocked.error
            assert calls == 1
        db.close()

    asyncio.run(run())
