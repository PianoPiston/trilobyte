"""Context.dev ingestion from explicit official documentation allowlists.

Scraped markdown is untrusted input. It is size-capped, sanitized, cached and parsed only as text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .db import Database
from .seed import DEPRECATION_URL
from .util import safe_excerpt, sanitize_markdown
from .web import CachedWebClient, WebResult

API_URL = "https://api.context.dev/v1/web/scrape"


@dataclass(frozen=True)
class DocumentSpec:
    key: str
    provider: str
    title: str
    url: str
    scrape_url: str


DOCUMENTS = (
    DocumentSpec("openai-deprecations", "OpenAI", "Model deprecations", DEPRECATION_URL, DEPRECATION_URL + ".md"),
    DocumentSpec("anthropic-deprecations", "Anthropic", "Model deprecations", "https://platform.claude.com/docs/en/about-claude/model-deprecations", "https://platform.claude.com/docs/en/about-claude/model-deprecations.md"),
)


class ContextDev:
    def __init__(self, db: Database, web: CachedWebClient, api_key: str | None, ttl: int = 21600):
        self.db = db
        self.web = web
        self.api_key = api_key
        self.ttl = ttl

    async def scrape(self, spec: DocumentSpec) -> WebResult:
        if not self.api_key:
            return WebResult(error="CONTEXTDEV_API_KEY is not configured; retained last-known evidence")
        result = await self.web.request_json("POST", API_URL, f"context:{spec.scrape_url}", self.ttl, payload={
            "url": spec.scrape_url,
            "formats": {"markdown": True, "html": False},
            "timeoutOpts": {"milliseconds": 30000, "behavior": "return-partial"},
        }, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        if result.error:
            return result
        markdown = (result.data or {}).get("markdown") or {}
        if not markdown.get("success") or not isinstance(markdown.get("data"), str):
            return WebResult(error="Context.dev returned no markdown document")
        if result.mode == "live":
            self.db.increment_meta("context_queries")
            credits = ((result.data or {}).get("key_metadata") or {}).get("credits_consumed", 0)
            if isinstance(credits, (int, float)):
                current = self.db.get_meta("context_credits", 0)
                self.db.set_meta("context_credits", current + credits)
        result.data = sanitize_markdown(markdown["data"])
        return result

    def error_source(self, spec: DocumentSpec, error: str) -> dict:
        old = self.db.get_source(f"src-{spec.key}") or {}
        return {
            **old,
            "id": f"src-{spec.key}", "publisher": spec.provider, "title": spec.title, "url": spec.url,
            "status": "error", "last_attempt_at": old.get("last_checked_at"), "error": safe_excerpt(error, 240),
            "mode": old.get("mode", "unconfigured"), "event_count": old.get("event_count", 0),
        }


def parse_deprecations(text: str, provider: str) -> list[dict]:
    """Parse explicit lifecycle prose and markdown lifecycle tables, ignoring unrelated model text."""
    events: dict[str, dict] = {}
    model_re = re.compile(r"(?<![\w-])((?:gpt-[a-z0-9.-]+|o[1-9](?:-mini|-preview)?|claude-[a-z0-9.-]+))(?![\w-])", re.I)
    date_re = re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b", re.I)
    lifecycle_re = re.compile(r"deprecat|retir|shut\s*down|shutdown|end.of.life", re.I)
    table_headers: list[str] | None = None

    def add(model: str, line: str, replacement: str | None, dates: list[str], retired: bool, shutdown_dates: list[str], announcement_dates: list[str]) -> None:
        key = f"{provider}:{model.lower()}"
        event = events.setdefault(key, {
            "provider": provider, "model": model, "replacement": replacement, "dates": [],
            "shutdown_dates": [], "announcement_dates": [], "retired": retired, "quote": safe_excerpt(line, 700),
        })
        event["dates"] = sorted(set(event["dates"] + dates))
        event["shutdown_dates"] = sorted(set(event["shutdown_dates"] + shutdown_dates))
        event["announcement_dates"] = sorted(set(event["announcement_dates"] + announcement_dates))
        event["retired"] = event["retired"] or retired
        if replacement:
            event["replacement"] = replacement
        if len(event["quote"]) < len(line):
            event["quote"] = safe_excerpt(line, 700)

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")]
            lowered = [re.sub(r"[*_]", "", cell).lower() for cell in cells]
            if any(re.fullmatch(r"model(?:\s+id)?", cell) for cell in lowered) and any(lifecycle_re.search(cell) for cell in lowered):
                table_headers = lowered
                continue
            if table_headers is not None:
                if all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
                    continue
                dates = date_re.findall(stripped)
                shutdown_dates = [date for index, cell in enumerate(cells) if index < len(table_headers) and re.search(r"shutdown|retirement", table_headers[index]) for date in date_re.findall(cell)]
                announcement_dates = [date for index, cell in enumerate(cells) if index < len(table_headers) and re.search(r"announce|deprecation", table_headers[index]) for date in date_re.findall(cell)]
                replacement_text = " ".join(cell for index, cell in enumerate(cells) if index < len(table_headers) and "replacement" in table_headers[index])
                model_text = " ".join(cell for index, cell in enumerate(cells) if index < len(table_headers) and re.fullmatch(r"model(?:\s+id)?", table_headers[index]))
                replacements = [item.rstrip(".-") for item in model_re.findall(replacement_text)]
                retired = any(re.search(r"shutdown|retir", header) for header in table_headers)
                for model in [item.rstrip(".-") for item in model_re.findall(model_text)]:
                    replacement = next((item for item in replacements if item.lower() != model.lower()), None)
                    add(model, line, replacement, dates, retired, shutdown_dates, announcement_dates)
                continue
        table_headers = None
        if not lifecycle_re.search(stripped):
            continue
        models = [item.rstrip(".-") for item in model_re.findall(stripped)]
        if not models:
            continue
        match = re.search(r"(?:recommended\s+replacement|replace(?:ment)?\s+(?:is|with))\s*[:` ]+((?:gpt|claude)-[a-z0-9.-]+)", stripped, re.I)
        replacement = match.group(1).rstrip(".-") if match else None
        dates = date_re.findall(stripped)
        retired = bool(re.search(r"shut\s*down|shutdown|retired|retirement", stripped, re.I))
        for model in models:
            add(model, line, replacement, dates, retired, dates if retired else [], dates if not retired else [])
    return list(events.values())
