from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path

import httpx
import pytest

from server.config import Settings
from server.contextdev import ContextDev
from server.db import Database
from server.intel import VulnerabilityIntel
from server.monitors import ContextMonitors
from server.remediation import RemediationError, generate
from server.repository import Reader, SourceLimits
from server.scanner import Dependency, inventory, production_models, usage_index
from server.service import DriftService
from server.web import CachedWebClient, WebResult


def test_bundled_dependency_patch_requires_owning_workflow():
    signal = {"id": "sig-cve", "kind": "vulnerability", "affected_package": "requests", "affected_version": "3.0.0", "ecosystem": "npm", "fixed_version": "3.0.1", "dependency_scope": "bundled"}
    with pytest.raises(RemediationError, match="Only application manifests"):
        generate({"package.json": '{"dependencies":{"requests":"3.0.0"}}'}, signal, False)


def advisory(identifier: str = "GHSA-test-0001") -> dict:
    return {
        "id": identifier,
        "summary": "Test advisory",
        "aliases": ["CVE-2026-10000"],
        "affected": [{"package": {"ecosystem": "PyPI", "name": "requests"}, "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "2.20.0"}]}]}],
    }


def dependency() -> Dependency:
    return Dependency("requests", "PyPI", "2.19.0", "2.19.0", "library", "requirements.txt", True, certainty="locked")


async def make_intel(tmp_path: Path, handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=.1)
    db = Database(tmp_path / "inventory.db", Path("does-not-exist"))
    return db, http, VulnerabilityIntel(db, CachedWebClient(db, http, 0))


@pytest.mark.asyncio
async def test_querybatch_descriptors_are_expanded_and_cached(tmp_path):
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/querybatch"):
            return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-test-0001", "modified": "2026-01-01T00:00:00Z"}]}]})
        assert request.url.path == "/v1/vulns/GHSA-test-0001"
        return httpx.Response(200, json=advisory())
    db, http, intel = await make_intel(tmp_path, handler)
    first = await intel.query_batch([dependency()], limit=100, deadline=time.monotonic() + 5)
    assert first["packages_checked"] == 1
    assert first["packages_pending"] == 0
    assert len(first["records"][0].advisories) == 1
    assert first["advisory_details_retrieved"] == 1
    assert not first["advisory_detail_errors"]
    assert first["records"][0].advisories[0]["affected"]
    assert first["complete"]
    call_count = len(calls)
    second = await intel.query_batch([dependency()], limit=100, deadline=time.monotonic() + 5)
    assert len(calls) == call_count
    assert second["records"][0].result.mode == "cached"
    assert second["records"][0].advisories[0]["affected"]
    db.close()
    await http.aclose()


@pytest.mark.asyncio
async def test_failed_advisory_detail_does_not_complete_package_check(tmp_path):
    def handler(request):
        if request.url.path.endswith("/querybatch"):
            return httpx.Response(200, json={"results": [{"vulns": [{"id": "GHSA-test-0001"}]}]})
        return httpx.Response(503, text="upstream temporarily unavailable")
    db, http, intel = await make_intel(tmp_path, handler)
    result = await intel.query_batch([dependency()], limit=100, deadline=time.monotonic() + 5)
    assert result["packages_checked"] == 0
    assert result["packages_pending"] == 1
    assert result["advisory_details_pending"] == 1
    assert not result["complete"]
    assert result["error"]
    db.close()
    await http.aclose()


@pytest.mark.asyncio
async def test_paginated_batch_is_explicitly_incomplete(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [{"next_page_token": "second-page", "vulns": []}]}))) as http:
        db = Database(tmp_path / "paged.db", Path("does-not-exist"))
        intel = VulnerabilityIntel(db, CachedWebClient(db, http, 0))
        result = await intel.query_batch([dependency()], limit=100, deadline=time.monotonic() + 5)
        assert result["packages_eligible"] == 1
        assert result["packages_checked"] == 0
        assert result["packages_pending"] == 1
        assert "next-page token" in result["error"]
        db.close()


@pytest.mark.asyncio
async def test_one_exact_version_query_retains_all_manifest_occurrences(tmp_path):
    second = Dependency("requests", "PyPI", "2.19.0", "2.19.0", "library", "test/fixtures/requirements.txt", True, certainty="locked")
    db, http, intel = await make_intel(tmp_path, lambda request: httpx.Response(200, json={"results": [{"vulns": []}] if request.url.path.endswith("/querybatch") else advisory()}))
    result = await intel.query_batch([dependency(), second], limit=100, deadline=time.monotonic() + 5)
    assert [record.dependency.manifest for record in result["records"]] == ["requirements.txt", "test/fixtures/requirements.txt"]
    assert result["packages_checked"] == 2
    db.close()
    await http.aclose()


@pytest.mark.asyncio
async def test_parallel_scrapes_respect_the_credit_budget(tmp_path):
    active = 0
    calls = []

    class SlowMetadata:
        async def request_json(self, method, url, cache_key, ttl, **kwargs):
            nonlocal active
            error = kwargs["allow_request"]()
            if error:
                return WebResult(error=error)
            active += 1
            assert active <= 2
            calls.append(cache_key)
            await asyncio.sleep(.01)
            active -= 1
            return WebResult({"key_metadata": {"credits_consumed": 1}}, "live", "2026-11-15T07:00:00Z")

    db = Database(tmp_path / "budget-reservation.db", Path("does-not-exist"))
    client = ContextDev(db, SlowMetadata(), "test-only", daily_credit_limit=2)
    async def exercise():
        await asyncio.gather(*(client.metadata_json(f"https://api.github.com/repos/example/{number}") for number in range(3)))

    await exercise()
    assert len(calls) == 2
    assert client.usage()["ordinary_reserved_credits"] == 0
    assert client.usage()["daily_available"] == 0
    assert client._reserved_credits == 0
    db.close()


@pytest.mark.asyncio
async def test_github_array_metadata_preserves_the_document(tmp_path):
    document = [{"number": 42, "state": "open"}]
    class BytesClient:
        async def request_json(self, method, url, cache_key, ttl, **kwargs):
            assert kwargs["allow_request"]() is None
            assert ttl == 300
            assert kwargs["payload"]["maxAgeMs"] == 300_000
            return WebResult({
                "key_metadata": {"credits_consumed": 1},
                "bytes": {"success": True, "data": {
                    "base64": base64.b64encode(json.dumps(document).encode()).decode(),
                    "contentType": "application/json; charset=utf-8",
                }},
            }, "live", "2026-11-15T07:40:00Z")
    client = ContextDev(Database(tmp_path / "array.db", Path("does-not-exist")), BytesClient(), "test-only")
    result = await client.metadata_json("https://api.github.com/repos/acme/orders/pulls", ttl=300)
    assert result.data == document
    assert result.error is None
    assert client.usage()["daily_credits"] == 1
    client.db.close()


def test_bare_o_number_variables_are_not_production_models():
    files = {
        "lib/internal/ffi-shared-buffer.js": {"kind": "code", "scope": "application", "content": 'const o1 = argOffsets[1];\nwriteNumericArg(view, i5, o5, a5, 5);\n'},
        "config/ai.ts": {"kind": "code", "scope": "application", "content": 'configure({ model: "o3-mini" });\n'},
        "test/fixtures/models.ts": {"kind": "code", "scope": "examples_tests_docs", "content": 'export const model = "o1";\n'},
    }
    assert production_models(files) == ["o3-mini"]
    native = {"test/fixtures/native/version.h": {"kind": "native", "scope": "examples_tests_docs", "content": '#define ZLIB_VERSION "1.3.0"'}}
    items = [item for item in inventory(native) if item["ecosystem"] == "Native"]
    assert items[0]["version"] == "1.3.0"
    assert items[0]["scope"] == "examples_tests_docs"
    assert not items[0]["advisory_supported"]


def test_usage_index_uses_import_roots_and_counts_files_once():
    irrelevant = {("npm", f"irrelevant-{number}") for number in range(3000)}
    packages = irrelevant | {("npm", "left-pad"), ("npm", "@scope/pkg"), ("npm", "o1"), ("PyPI", "my-package"), ("crates.io", "serde")}
    files = {
        "src/a.js": 'import deep from "@scope/pkg/deep";\nconst o1 = argOffsets[1];\nconst leftPad = require("left-pad");\n',
        "src/b.js": 'import pad from "left-pad";\n// const serde = "serde";\nconst other = "serde";',
        "src/c.py": 'import my_package.core\n',
    }
    usages = usage_index(files, packages)
    assert usages[("npm", "@scope/pkg")] == usages[("PyPI", "my-package")] == 1
    assert usages[("npm", "left-pad")] == 2
    assert ("npm", "o1") not in usages
    assert usages[("crates.io", "serde")] == 1


def test_inventory_cache_tracks_version_scope_and_issue_state():
    files = {"package.json": {"kind": "manifest", "scope": "application", "content": '{"dependencies":{"next":"14.2.3"}}'}}
    first = inventory(files)
    second_files = {"node_modules/next/package.json": {"kind": "manifest", "scope": "bundled", "content": '{"name":"next","version":"14.2.4"}'}}
    second = inventory(second_files)
    assert second[0]["version"] == "14.2.4"
    assert second[0]["scope"] == "bundled"
    affected = inventory(second_files, {("npm", "next"): 2})
    assert affected[0]["issues"] == 2
    assert affected[0]["health"] == "critical"
    second[0]["version"] = "caller mutation"
    assert inventory(second_files)[0]["version"] == "14.2.4"
    assert inventory(second_files)[0]["issues"] == 0
    assert inventory(files)[0]["version"] == "14.2.3"


def test_manifest_reservations_use_actual_capacity():
    limits = SourceLimits(max_files=6, max_bytes=100_000, max_file_bytes=10_000)
    reader = Reader(httpx.AsyncClient(), "acme", "example", None, limits)
    entries = [
        {"path": "package.json", "size": 100, "sha": "a"},
        {"path": "deps/zlib/zlib.h", "size": 100, "sha": "b"},
        *[{"path": f"src/module-{number}.js", "size": 100, "sha": str(number)} for number in range(8)],
    ]
    selected, metadata = reader.select(entries)
    assert len(selected) == 6
    assert sum(item["kind"] == "code" for item in selected) == 4
    assert metadata["dependency_manifest_complete"]


def test_structured_file_records_round_trip_through_sqlite(tmp_path):
    db = Database(tmp_path / "records.db", Path("does-not-exist"))
    record = {"kind": "manifest", "scope": "application", "content": '{"name": "__driftci_file_v1__"}', "blob_sha": "abc"}
    db.replace_workspace({"id": "acme/example", "source": "github", "name": "acme/example"}, {"package.json": record, "src/example.ts": "const model = 'o3-mini';"})
    actual = db.files()
    assert actual["package.json"] == {"path": "package.json", **record}
    assert actual["src/example.ts"] == "const model = 'o3-mini';"
    db.close()


@pytest.mark.asyncio
async def test_remote_baseline_then_genuine_change_is_deduplicated_and_not_auto_patched(tmp_path):
    baseline = {"id": "run-baseline", "status": "completed", "run_type": "baseline", "baseline_created": True, "started_at": "2026-11-15T05:36:39Z", "completed_at": "2026-11-15T05:36:44Z", "credits_charged": 2}
    current = {"id": "run-current", "status": "completed", "run_type": "scheduled", "baseline_created": False, "started_at": "2026-11-15T06:36:39Z", "completed_at": "2026-11-15T06:36:44Z", "change_detected": True, "change_id": "chg-one", "credits_charged": 2}
    monitor = {"id": "mon_test", "name": "DriftCI · Node.js security advisories", "status": "active", "tags": ["driftci", "driftci-repo:nodejs-node"], "target": {"type": "search", "query": "site:nodejs.org security"}}
    runs = [baseline]
    posted = 0
    def handler(request):
        nonlocal posted
        path = request.url.path
        if request.method == "POST" and path.endswith("/monitors"):
            posted += 1
            return httpx.Response(201, json=monitor)
        if path == "/v1/monitors":
            assert request.url.params["tag"] == "driftci-repo:nodejs-node"
            return httpx.Response(200, json={"data": [monitor]})
        if path == "/v1/monitors/credit-usage":
            return httpx.Response(200, json={"data": [{"monitor_id": "mon_test", "credits": len(runs) * 2}]})
        if path.endswith("/runs"):
            return httpx.Response(200, json={"data": list(reversed(runs))})
        if path.endswith("/changes"):
            return httpx.Response(200, json={"data": [{"id": "chg-one", "monitor_id": "mon_test", "run_id": "run-current", "title": "Node.js security release", "summary": "A new security release mentions zlib.", "confidence": .95, "importance": "high", "detected_at": "2026-11-15T06:36:44Z", "matched_urls": ["https://nodejs.org/en/blog/security", "https://untrusted.invalid/example"]}]})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")
    db = Database(tmp_path / "monitors.db", Path("does-not-exist"))
    db.replace_workspace({"id": "nodejs/node", "name": "nodejs/node", "source": "github", "repository": "https://github.com/nodejs/node", "branch": "main", "commit_sha": "a" * 40, "coverage": {}}, {"deps/zlib/zlib.h": {"kind": "native", "scope": "bundled", "content": '#define ZLIB_VERSION "1.3.0"'}})
    settings = Settings(db_path=str(tmp_path / "monitors.db"), contextdev_api_key="test-only", github_token=None, offline=False, context_cache_ttl=21600, osv_cache_ttl=3600, kev_cache_ttl=21600, context_min_interval=0, context_daily_credit_limit=80, context_max_sources=6, request_timeout=2, web_dist=tmp_path, example_dir=Path("does-not-exist"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = DriftService(db, settings, http)
        await service._scan_monitor()
        assert not db.list_signals()
        remote = await service.monitors.sync("node", "nodejs", enable=True)
        assert remote[0]["baseline_at"]
        runs.append(current)
        await service._scan_monitor()
        signals = db.list_signals()
        assert len(signals) == 1
        signal = signals[0]
        assert signal["monitor_id"] == "mon_test"
        assert [receipt["url"] for receipt in signal["source_receipts"]] == ["https://nodejs.org/en/blog/security"]
        assert signal["affected_assets"] == ["zlib"]
        assert signal["observed_at"]
        with pytest.raises(RemediationError):
            service.create_remediation(signal["id"])
        await service._scan_monitor()
        assert len(db.list_signals()) == 1
        assert db.get_meta("context_monitor_state")["new_changes"] == 0
        assert posted == 0
        assert service.monitors.budget()["spent"] == 4
    db.close()


@pytest.mark.asyncio
async def test_monitor_creation_reserves_hourly_cost_before_post(tmp_path):
    created = []
    def handler(request):
        path = request.url.path
        if request.method == "POST" and path.endswith("/monitors"):
            created.append(request.content)
            return httpx.Response(201, json={"id": "mon-new", "status": "active", "tags": ["driftci", "driftci-repo:acme-root"], "target": {"type": "search", "query": "acme/root"}})
        if path == "/v1/monitors":
            return httpx.Response(200, json={"data": []})
        raise AssertionError("Budget-exhausted monitor creation must not run")
    db = Database(tmp_path / "budget.db", Path("does-not-exist"))
    db.set_meta("context_daily", {"date": time.strftime("%Y-%m-%d", time.gmtime()), "credits": 33, "queries": 12})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        monitor = ContextMonitors(db, http, "test-only", 80)
        state, changes = await monitor.sync("root", "acme", enable=True)
        assert state is None
        assert not created
        assert not changes
    db.close()


@pytest.mark.asyncio
async def test_monitor_creation_includes_ordinary_inflight_reservations(tmp_path):
    posts = []
    db = Database(tmp_path / "inflight-budget.db", Path("does-not-exist"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: posts.append(request) or httpx.Response(200, json={"data": []}))) as http:
        monitor = ContextMonitors(db, http, "test-only", 80, ordinary_usage=lambda: {"daily_available": 47})
        state, _changes = await monitor.sync("root", "acme", enable=True)
    assert state is None
    assert [request.method for request in posts] == ["GET"]
    db.close()


@pytest.mark.asyncio
async def test_only_owned_unrelated_remote_schedules_pause(tmp_path):
    patched = []
    resources = [
        {"id": "mon_node", "status": "active", "tags": ["driftci", "driftci-repo:nodejs-node"]},
        {"id": "mon_other", "status": "active", "tags": ["driftci", "driftci-repo:acme-other"]},
    ]
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": resources})
        payload = json.loads(request.content)
        patched.append((request.url.path, payload))
        assert payload == {"status": "paused"}
        return httpx.Response(200, json={"id": "mon-other", "status": "paused"})
    db = Database(tmp_path / "pause.db", Path("does-not-exist"))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        monitor = ContextMonitors(db, http, "test-only", 80)
        await monitor.pause_unrelated("node", "nodejs")
        assert patched == [("/v1/monitors/mon_other", {"status": "paused"})]
        assert monitor.budget()["reserved"] == 48
    db.close()
