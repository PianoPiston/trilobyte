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
    """Parse lifecycle tables and explicit prose without promoting replacement models.

    Canonical machine-readable table rows take precedence over historical commentary.
    Only the affected-model column is searched for deprecated identifiers; replacement
    columns are deliberately parsed separately.
    """
    events: dict[str, dict] = {}
    model_re = re.compile(r"(?<![\w-])((?:gpt-[a-z0-9.-]+|o[1-9](?:-mini|-preview)?|claude-[a-z0-9.-]+))(?![\w-])", re.I)
    date_re = re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b", re.I)
    lifecycle_re = re.compile(r"deprecat|retir|shut\s*down|shutdown|end.of.life", re.I)
    table_headers: list[str] | None = None
    table_model_column: int | None = None
    historical_notes = False

    def add(model: str, line: str, replacement: str | None, dates: list[str], retired: bool,
            shutdown_dates: list[str], announcement_dates: list[str], table: bool = False) -> None:
        key = f"{provider}:{model.lower()}"
        existing = events.get(key)
        # Historical commentary must never dilute a precise lifecycle-table row.
        if existing and existing.get("_table") and not table:
            return
        if table and (not existing or not existing.get("_table")):
            existing = None
        event = existing or {
            "provider": provider, "model": model, "replacement": replacement, "dates": [],
            "shutdown_dates": [], "announcement_dates": [], "retired": retired,
            "quote": safe_excerpt(line, 700), "_table": table,
        }
        event["dates"] = sorted(set(event["dates"] + dates))
        event["shutdown_dates"] = sorted(set(event["shutdown_dates"] + shutdown_dates))
        event["announcement_dates"] = sorted(set(event["announcement_dates"] + announcement_dates))
        event["retired"] = event["retired"] or retired
        if replacement or table:
            event["replacement"] = replacement
        if table or not existing:
            event["quote"] = safe_excerpt(line, 700)
            event["_table"] = table
        events[key] = event

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().lower()
            historical_notes = heading in {"historical notes", "historical note"}
            table_headers = None
            table_model_column = None
            continue
        if historical_notes:
            continue
        if stripped.startswith("|"):
            cells = [cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")]
            lowered = [re.sub(r"[*_]", "", cell).lower().strip() for cell in cells]
            model_columns = [index for index, cell in enumerate(lowered) if re.fullmatch(
                r"(?:affected\s+|deprecated\s+)?models?(?:\s+id)?(?:\s+or\s+(?:feature|endpoint|features?\s+or\s+endpoints?))?", cell
            )]
            if model_columns and any(lifecycle_re.search(cell) for cell in lowered):
                table_headers = lowered
                table_model_column = model_columns[0]
                continue
            if table_headers is not None and table_model_column is not None:
                if all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in cells):
                    continue
                # A new non-tabular block ends this table extraction context.
                if len(cells) != len(table_headers):
                    table_headers = None
                    table_model_column = None
                    continue
                shutdown_dates = [date for index, cell in enumerate(cells)
                                  if re.search(r"shutdown|retirement", table_headers[index]) for date in date_re.findall(cell)]
                announcement_dates = [date for index, cell in enumerate(cells)
                                      if re.search(r"notice|announce|deprecation", table_headers[index]) for date in date_re.findall(cell)]
                replacement_text = " ".join(cell for index, cell in enumerate(cells)
                                            if "replacement" in table_headers[index] and index != table_model_column)
                replacements = [item.rstrip(".-") for item in model_re.findall(replacement_text)]
                status = " ".join(cell for index, cell in enumerate(cells) if table_headers[index] == "status")
                models = [item.rstrip(".-") for item in model_re.findall(cells[table_model_column])]
                dates = sorted(set(shutdown_dates + announcement_dates))
                retired = bool(shutdown_dates or lifecycle_re.search(status))
                for model in models:
                    replacement = next((item for item in replacements if item.lower() != model.lower()), None)
                    add(model, line, replacement, dates, retired, shutdown_dates, announcement_dates, table=True)
                continue
            table_headers = None
            table_model_column = None
        else:
            table_headers = None
            table_model_column = None
        if not lifecycle_re.search(stripped):
            continue
        target_text = re.split(r"recommended\s+replacement|replacement\s+(?:is|with)|replace\s+(?:is|with)", stripped, maxsplit=1, flags=re.I)[0]
        models = [item.rstrip(".-") for item in model_re.findall(target_text)]
        if not models:
            continue
        replacement_text = stripped[len(target_text):]
        replacements = [item.rstrip(".-") for item in model_re.findall(replacement_text)]
        dates = date_re.findall(stripped)
        retired = bool(re.search(r"shut\s*down|shutdown|retired|retirement", stripped, re.I))
        for model in models:
            add(model, line, replacements[0] if replacements else None, dates, retired,
                dates if retired else [], dates if not retired else [], table=False)
    for event in events.values():
        event.pop("_table", None)
    return list(events.values())
