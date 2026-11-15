from __future__ import annotations

import asyncio

import httpx

from server.contextdev import DOCUMENTS, ContextDev, parse_deprecations
from server.db import Database
from server.web import CachedWebClient


OPENAI_TABLE = """
# Model deprecations
| Model | Announced | Shutdown date | Recommended replacement |
| --- | --- | --- | --- |
| gpt-4-0314 | September 26, 2025 | March 26, 2026 | gpt-5, or gpt-4.1 for latency-sensitive tasks |
"""


def test_replacement_models_do_not_become_deprecation_events():
    events = parse_deprecations(OPENAI_TABLE, "OpenAI")
    assert len(events) == 1
    event = events[0]
    assert event["model"] == "gpt-4-0314"
    assert event["replacement"] == "gpt-5"
    assert event["shutdown_dates"] == ["March 26, 2026"]
    assert event["announcement_dates"] == ["September 26, 2025"]
    assert "gpt-4.1" in event["quote"]


def test_unrelated_model_table_is_ignored():
    text = "| Model | Context | Input |\n| --- | --- | --- |\n| gpt-4.1 | 1M | Text |\n"
    assert parse_deprecations(text, "OpenAI") == []


def test_context_scrape_is_sanitized_cached_and_counted_once():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        assert request.headers["authorization"] == "Bearer test-secret"
        assert request.content.find(b'"markdown":true') >= 0
        return httpx.Response(200, json={
            "markdown": {"success": True, "data": "line one\n<script>alert(1)</script>line two"},
            "key_metadata": {"credits_consumed": 1},
        })

    async def run():
        db = Database(":memory:")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = ContextDev(db, CachedWebClient(db, http, 0, 1), "test-secret")
            first = await client.scrape(DOCUMENTS[0])
            second = await client.scrape(DOCUMENTS[0])
            assert first.mode == "live"
            assert second.mode == "cached"
            assert first.data == "line one\nline two"
            assert calls == 1
            assert db.get_meta("context_queries") == 1
            assert db.get_meta("context_credits") == 1
        db.close()

    asyncio.run(run())
