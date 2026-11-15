from __future__ import annotations

import asyncio
import base64
import json
import time
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.contextdev import ContextDev
from server.db import Database
from server.web import CachedWebClient
from server.repository import RepositoryError, SourceLimits, candidate_priority, parse_github, read_public, supported_source
from server.scanner import inventory, middleware_evidence, production_models
from test_live_scan import NEXT_ADVISORY, osv_batch_response

from conftest import make_settings

SHA = "a" * 40


def source_files() -> dict[str, str]:
    return {
        "package.json": '{"dependencies":{"next":"14.2.3","openai":"^4.28.0"}}',
        "package-lock.json": '{"packages":{"node_modules/next":{"version":"14.2.3"}}}',
        "src/lib/ai.ts": 'const model = "gpt-4-0314";',
    }


def fake_github(contents: dict[str, str] | None = None, *, truncated: bool = False, calls: list[str] | None = None, slow_paths: set[str] | None = None, extra_handler=None):
    contents = source_files() if contents is None else contents
    calls = [] if calls is None else calls
    slow_paths = slow_paths or set()
    tree_contents = {
        **contents,
        "README.md": "Documentation is not downloaded for source analysis.",
        "test/fixtures/package.json": '{"dependencies":{"not-production":"1.0.0"}}',
        "assets/logo.png": "binary",
        "node_modules/next/package.json": '{"version":"99.0.0"}',
    }

    def blob(path: str, size: int | None = None) -> dict:
        value = tree_contents.get(path, "not fetched")
        return {"path": path, "type": "blob", "size": len(value.encode()) if size is None else size, "sha": "b" * 40}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.url.host != "codeload.github.com", "selective reads must never use repository archives"
        if request.url.host == "api.github.com":
            path = request.url.path
            if path == "/repos/acme/large-repo/dependency-graph/sbom":
                return httpx.Response(403, json={"message": "Dependency graph unavailable; use manifests"})
            if path == "/repos/acme/large-repo":
                return httpx.Response(200, json={"name": "large-repo", "private": False, "default_branch": "main", "size": 90_000})
            if path == "/repos/acme/large-repo/git/ref/heads/main":
                return httpx.Response(200, json={"object": {"type": "commit", "sha": SHA}})
            if path == f"/repos/acme/large-repo/git/trees/{SHA}" and request.url.params.get("recursive") == "1":
                entries = [blob(path) for path in tree_contents]
                return httpx.Response(200, json={"sha": SHA, "truncated": truncated, "tree": entries})
            return httpx.Response(404, json={"message": "unexpected API endpoint"})
        if request.url.host == "raw.githubusercontent.com":
            # Reading public source never forwards API/PR credentials to raw.github.
            assert "authorization" not in request.headers
            prefix = f"/acme/large-repo/{SHA}/"
            assert request.url.path.startswith(prefix)
            path = unquote(request.url.path[len(prefix):])
            if path not in tree_contents:
                return httpx.Response(404, text="unknown")
            response_text = tree_contents[path]
            if path in slow_paths:
                await asyncio.sleep(10)
            return httpx.Response(200, content=response_text.encode())
        if extra_handler:
            extra = extra_handler(request)
            if extra is not None:
                return extra
        return httpx.Response(400, text="unexpected host")

    transport = httpx.MockTransport(handler)
    assert calls is not None
    return transport, calls


@pytest.mark.asyncio
async def test_large_repository_uses_tree_and_targeted_raw_files_with_manifest_coverage_not_archive():
    transport, calls = fake_github()
    async with httpx.AsyncClient(transport=transport) as http:
        workspace, files = await read_public(http, "https://github.com/acme/large-repo", token="not-forwarded-to-raw-host")
    assert set(files) == {*source_files(), "test/fixtures/package.json", "node_modules/next/package.json"}
    coverage = workspace["coverage"]
    assert coverage["repository_size_kb"] == 90_000
    assert coverage["complete"] is True  # This flag covers eligible dependency manifests.
    assert coverage["source_complete"] is True  # This tiny fixture's wider source is also fully indexed.
    assert coverage["dependency_graph_status"].startswith("HTTP 403")
    assert coverage["archive_downloaded"] is False
    assert coverage["commit_sha"] == SHA
    assert coverage["files_read"] == 5
    assert coverage["manifest_files_read"] == 4
    assert any(f"/git/trees/{SHA}?recursive=1" in call for call in calls), "tree must be pinned to the resolved commit"
    raw_calls = [call for call in calls if "raw.githubusercontent.com" in call]
    assert len(raw_calls) == 5
    assert all(f"/{SHA}/" in call for call in raw_calls)
    assert any("node_modules/next/package.json" in call for call in raw_calls)
    assert any("test/fixtures/package.json" in call for call in raw_calls)
    assert all("README" not in call and "logo" not in call for call in raw_calls)
    assert not any("codeload" in call for call in calls)


@pytest.mark.asyncio
async def test_source_budget_reports_partial_coverage_instead_of_claiming_full_scan():
    transport, _calls = fake_github(truncated=True)
    limits = SourceLimits(max_files=2, max_bytes=100_000, max_file_bytes=20_000)
    async with httpx.AsyncClient(transport=transport) as http:
        workspace, files = await read_public(http, "https://github.com/acme/large-repo", limits=limits)
    assert len(files) == 2
    assert workspace["coverage"]["complete"] is False
    assert workspace["coverage"]["skipped_budget_files"] >= 1
    assert workspace["coverage"]["dependency_manifest_complete"] is False
    assert workspace["coverage"]["tree_truncated"] is True


@pytest.mark.asyncio
async def test_remote_fetch_uses_budgets_and_validates_inputs():
    for url in ("/tmp/repo", "file:///tmp/repo", "https://evil.example/owner/repo", "https://github.com/owner/repo/issues"):
        with pytest.raises(RepositoryError):
            parse_github(url)
    assert parse_github("https://github.com/owner/repo.git") == ("owner", "repo")

    def failed_api(request: httpx.Request):
        return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(failed_api)) as http:
        with pytest.raises(RepositoryError, match="rate limit"):
            await read_public(http, "https://github.com/acme/large-repo")


@pytest.mark.asyncio
async def test_source_deadline_retains_completed_files_and_reports_pending():
    files = {**source_files(), "src/slow.ts": "export const slowlyRead = true;"}
    transport, _calls = fake_github(files, slow_paths={"src/slow.ts"})
    limits = SourceLimits(max_files=64, max_bytes=100_000, max_file_bytes=20_000, max_seconds=5, per_file_timeout=30)
    started = asyncio.get_running_loop().time()
    async with httpx.AsyncClient(transport=transport) as http:
        workspace, read = await read_public(http, "https://github.com/acme/large-repo", limits=limits)
    elapsed = asyncio.get_running_loop().time() - started
    assert len(read) == 5 and "src/slow.ts" not in read
    assert workspace["coverage"]["timed_out_files"] == 1
    assert workspace["coverage"]["failed_files"] == 1
    assert workspace["coverage"]["source_complete"] is False
    assert 4.5 <= elapsed < 8


@pytest.mark.asyncio
async def test_contextdev_byte_transport_preserves_metadata_and_keeps_code_reads_pinned(tmp_path):
    metadata = {
        "": {"full_name": "acme/large-repo", "private": False, "default_branch": "main", "size": 1},
        "/git/ref/heads/main": {"object": {"sha": SHA}},
        f"/git/trees/{SHA}?recursive=1": {"tree": [{"path": "package.json", "type": "blob", "size": 39, "sha": "b" * 40}], "truncated": False},
        "/dependency-graph/sbom": {"sbom": {"packages": []}},
    }
    calls = []

    class ByteWeb:
        async def request_json(self, _method, _url, _key, _ttl, *, payload, headers, allow_request):
            assert payload["formats"] == {"bytes": True}
            assert allow_request() is None
            assert headers["Authorization"] == "Bearer context-key"
            target = payload["url"].removeprefix("https://api.github.com/repos/acme/large-repo")
            calls.append(target)
            content = json.dumps(metadata[target]).encode()
            return type("Result", (), {"error": None, "mode": "live", "retrieved_at": None, "data": {"key_metadata": {"credits_consumed": 1}, "bytes": {"success": True, "data": {"contentType": "application/json", "base64": base64.b64encode(content).decode()}}}})()

    async def handler(request):
        assert request.url.host != "codeload.github.com"
        assert request.url.host != "api.github.com", "Configured metadata reads must use Context.dev"
        assert request.url.host == "raw.githubusercontent.com"
        assert "authorization" not in request.headers
        assert request.url.path == f"/acme/large-repo/{SHA}/package.json"
        return httpx.Response(200, text='{"dependencies":{"aiohttp":"3.12.15"}}')

    db = Database(tmp_path / "metadata.db", tmp_path / "missing")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        context = ContextDev(db, CachedWebClient(db, http, 0), "context-key")
        context.web = ByteWeb()
        workspace, files = await read_public(http, "https://github.com/acme/large-repo", token="github-secret", metadata_context=context)
        disallowed = await context.metadata_json("https://raw.githubusercontent.com/acme/large-repo/secret")
    assert len(calls) == 4, "Repository, ref, tree and graph metadata must use byte-preserving Context.dev requests"
    assert workspace["coverage"]["metadata_transport"] == "context.dev_bytes"
    assert workspace["coverage"]["context_metadata_reads"] == 4
    assert workspace["coverage"]["archive_downloaded"] is False
    assert context.usage()["daily_credits"] == 4
    assert disallowed.error
    assert json.loads(files["package.json"])["dependencies"] == {"aiohttp": "3.12.15"}
    db.close()


def test_connect_endpoint_persists_selective_workspace_and_inventory(tmp_path):
    transport, calls = fake_github()
    with TestClient(create_app(make_settings(tmp_path, offline=True), transport=transport)) as client:
        response = client.post("/api/repositories/connect", json={"url": "https://github.com/acme/large-repo"})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["workspace"]["repository"] == "acme/large-repo"
        assert payload["workspace"]["coverage"]["metadata_transport"] == "direct"
        assert payload["workspace"]["coverage"]["files_read"] == 5
        versions = {row["name"]: row["version"] for row in payload["dependencies"] if row["scope"] == "application" and row["manifest"] == "package.json"}
        assert versions == {"next": "14.2.3", "openai": "^4.28.0"}
        assert any(row["manifest"] == "test/fixtures/package.json" and row["scope"] == "examples_tests_docs" for row in payload["dependencies"])
        assert any(row["manifest"] == "node_modules/next/package.json" and row["scope"] == "bundled" for row in payload["dependencies"])
        assert payload["metrics"]["files_indexed"] == 5
        assert payload["summary"]["production_models"] == 1
        assert any("no archive" in row["detail"] for row in payload["activity"] if row["type"] == "repository")
    assert not any("codeload" in call for call in calls)
    assert not any("api.context.dev" in call for call in calls), "Unconfigured Context.dev must not receive metadata requests"


def test_fresh_repository_first_advisory_does_not_dereference_missing_record(tmp_path):
    def live_sources(request: httpx.Request):
        if request.url.host == "api.osv.dev":
            return osv_batch_response(request)
        if request.url.host == "www.cisa.gov":
            return httpx.Response(200, json={"vulnerabilities": []})
        return None

    transport, _calls = fake_github(extra_handler=live_sources)
    with TestClient(create_app(make_settings(tmp_path, offline=False), transport=transport)) as client:
        response = client.post("/api/repositories/connect", json={"url": "https://github.com/acme/large-repo"})
        assert response.status_code == 200, response.text
        assert any(row["id"] == "sig-CVE-2025-29927" for row in response.json()["signals"])


def test_inventory_uses_shared_usage_index(monkeypatch):
    import server.scanner as scanner_module

    def unexpected_rescan(*_args):
        raise AssertionError("inventory must not rescan all files once per package")

    monkeypatch.setattr(scanner_module, "package_usage", unexpected_rescan)
    rows = inventory({
        "package.json": '{"dependencies":{"react":"18.3.1","lodash":"4.17.21"}}',
        "src/app.ts": 'import "react"; const merge = require("lodash/merge");',
    })
    assert {row["name"]: row["usage_count"] for row in rows} == {"lodash": 1, "react": 1}


def test_outer_connect_timeout_returns_actionable_504(tmp_path):
    async def stalled(_request: httpx.Request):
        await asyncio.sleep(10)
        return httpx.Response(200, json={})

    settings = make_settings(tmp_path, repository_connect_timeout_seconds=1, request_timeout=30)
    with TestClient(create_app(settings, transport=httpx.MockTransport(stalled))) as client:
        started = time.monotonic()
        response = client.post("/api/repositories/connect", json={"url": "https://github.com/acme/large-repo"})
        elapsed = time.monotonic() - started
        assert response.status_code == 504
        assert "time budget" in response.json()["detail"]
        assert elapsed < 5
        assert client.get("/api/bootstrap").json()["workspace"]["source"] == "demo"


def test_nested_manifests_keep_distribution_and_lock_scope():
    files = {
        "package.json": '{"dependencies":{"next":"14.2.3"}}',
        "services/web/package.json": '{"dependencies":{"next":"14.2.4"}}',
        "services/web/package-lock.json": '{"packages":{"node_modules/next":{"version":"14.2.4"}}}',
        "services/api/pyproject.toml": '[project]\ndependencies = ["fastapi==0.115.0"]',
        "services/api/requirements.txt": "django==5.0.0",
        "services/web/src/middleware.ts": "// authorization comment\nconst session = cookies.get('session');",
    }
    rows = inventory(files)
    next_rows = [row for row in rows if row["name"] == "next"]
    assert {(row["manifest"], row["version"]) for row in next_rows} == {
        ("package.json", "14.2.3"), ("services/web/package.json", "14.2.4"),
    }
    by_package = {row["name"]: row for row in rows}
    assert by_package["fastapi"]["manifest"] == "services/api/pyproject.toml"
    assert by_package["django"]["manifest"] == "services/api/requirements.txt"
    assert middleware_evidence(files)[0]["file"] == "services/web/src/middleware.ts"
    assert middleware_evidence(files)[0]["line"] == 2


def test_large_tree_budget_skips_fixtures_and_examples_before_application_source():
    files = {
        "src/config/models.ts": 'export const configured = "gpt-4-0314";',
        "src/config/models.test.ts": 'export const fixture = "gpt-fake-test-model";',
        "packages/anthropic/__fixtures__/response.json": '{"model":"claude-synthetic-fixture"}',
        "examples/demo/model.ts": 'export const example = "gpt-example-only";',
    }
    assert production_models(files) == ["gpt-4-0314", "gpt-example-only"]
    assert not supported_source("src/config/models.test.ts")
    assert not supported_source("packages/anthropic/__fixtures__/response.json")
    assert candidate_priority("src/config/models.ts") < candidate_priority("examples/demo/package.json")
