"""Context.dev ingestion from explicit official documentation allowlists.

Scraped markdown is untrusted input. It is size-capped, sanitized, cached and parsed only as text.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from .db import Database
from .scanner import inventory, production_models
from .seed import DEPRECATION_URL
from .util import safe_excerpt, sanitize_markdown, stable_id
from .web import CachedWebClient, WebResult

API_ROOT = "https://api.context.dev/v1"
API_URL = API_ROOT + "/web/scrape"


@dataclass(frozen=True)
class DocumentSpec:
    key: str
    provider: str
    title: str
    url: str
    scrape_url: str
    category: str = "documentation"
    package: str | None = None
    custom: bool = False


DOCUMENTS = (
    DocumentSpec("openai-deprecations", "OpenAI", "Model deprecations", DEPRECATION_URL, DEPRECATION_URL + ".md", "deprecations"),
    DocumentSpec("anthropic-deprecations", "Anthropic", "Model deprecations", "https://platform.claude.com/docs/en/about-claude/model-deprecations", "https://platform.claude.com/docs/en/about-claude/model-deprecations.md", "deprecations"),
)


class ContextDev:
    def __init__(self, db: Database, web: CachedWebClient, api_key: str | None, ttl: int = 21600, daily_credit_limit: int = 80):
        self.db = db
        self.web = web
        self.api_key = api_key
        self.ttl = ttl
        self.daily_credit_limit = daily_credit_limit

    def usage(self) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()
        daily = self.db.get_meta("context_daily", {})
        if daily.get("date") != today:
            daily = {"date": today, "credits": 0, "queries": 0}
        return {
            "queries": self.db.get_meta("context_queries", 0),
            "credits": self.db.get_meta("context_credits", 0),
            "daily_queries": daily["queries"],
            "daily_credits": daily["credits"],
            "daily_credit_limit": self.daily_credit_limit,
            "cache_ttl_seconds": self.ttl,
        }

    def _budget_error(self, estimated_credits: int = 1) -> str | None:
        usage = self.usage()
        if usage["daily_credits"] + estimated_credits > self.daily_credit_limit:
            return f"Daily Context.dev budget reached ({self.daily_credit_limit} locally recorded credits); cached evidence retained"
        return None

    def _record_usage(self, result: WebResult, kind: str, fallback_credits: int) -> None:
        if result.mode != "live":
            return
        metadata = (result.data or {}).get("key_metadata") or {}
        credits = metadata.get("credits_consumed", fallback_credits)
        if not isinstance(credits, (int, float)) or isinstance(credits, bool) or credits < 0:
            credits = fallback_credits
        self.db.increment_meta("context_queries")
        self.db.increment_meta(f"context_{kind}_queries")
        self.db.set_meta("context_credits", self.db.get_meta("context_credits", 0) + credits)
        usage = self.usage()
        self.db.set_meta("context_daily", {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "credits": usage["daily_credits"] + credits,
            "queries": usage["daily_queries"] + 1,
        })

    async def scrape(self, spec: DocumentSpec, ttl: int | None = None) -> WebResult:
        if not self.api_key:
            return WebResult(error="CONTEXTDEV_API_KEY is not configured; retained last-known evidence")
        result = await self.web.request_json("POST", API_URL, f"context:v2:{spec.scrape_url}", self.ttl if ttl is None else ttl, payload={
            "url": spec.scrape_url,
            "formats": {"markdown": True, "html": False},
            "timeoutOpts": {"milliseconds": 30000, "behavior": "return-partial"},
        }, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, allow_request=lambda: self._budget_error(1))
        if result.error:
            return result
        markdown = (result.data or {}).get("markdown") or {}
        if not markdown.get("success") or not isinstance(markdown.get("data"), str):
            return WebResult(error="Context.dev returned no markdown document")
        self._record_usage(result, "scrape", 1)
        result.data = sanitize_markdown(markdown["data"])
        return result

    async def search(self, query: str) -> WebResult:
        """Run one scoped discovery query; highlights cost at most two credits."""
        if not self.api_key:
            return WebResult(error="CONTEXTDEV_API_KEY is not configured; scoped web research is unavailable")
        result = await self.web.request_json("POST", API_ROOT + "/web/search", f"context-search:v1:{query}", self.ttl, payload={
            "query": query[:500], "numResults": 5,
            "highlightsOptions": {"enabled": True, "maxCharacters": 1400},
            "timeoutOpts": {"milliseconds": 30000, "behavior": "return-partial"},
        }, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, allow_request=lambda: self._budget_error(2))
        if result.error:
            return result
        rows = (result.data or {}).get("results")
        if not isinstance(rows, list):
            return WebResult(error="Context.dev returned no search result list")
        self._record_usage(result, "search", 2)
        result.data = {"query": query, "results": rows[:5]}
        return result

    def error_source(self, spec: DocumentSpec, error: str) -> dict:
        old = self.db.get_source(f"src-{spec.key}") or {}
        return {
            **old,
            "id": f"src-{spec.key}", "publisher": spec.provider, "title": spec.title, "url": spec.url,
            "status": "error", "last_attempt_at": old.get("last_checked_at"), "error": safe_excerpt(error, 240),
            "mode": old.get("mode", "unconfigured"), "event_count": old.get("event_count", 0),
            "category": spec.category, "package": spec.package, "custom": spec.custom,
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


OPENAI_PRICING = DocumentSpec(
    "openai-pricing", "OpenAI", "API pricing", "https://developers.openai.com/api/docs/pricing",
    "https://developers.openai.com/api/docs/pricing.md", "pricing",
)
OPENAI_STATUS = DocumentSpec(
    "openai-status", "OpenAI", "Service status", "https://status.openai.com/",
    "https://status.openai.com/", "status",
)
ANTHROPIC_RELEASES = DocumentSpec(
    "anthropic-release-notes", "Anthropic", "API release notes", "https://platform.claude.com/docs/en/release-notes/overview",
    "https://platform.claude.com/docs/en/release-notes/overview.md", "releases",
)

# Watches are inferred only for packages present in the repository. Each scan caps this list.
RELEASE_WATCHES = {
    "next": DocumentSpec("next-releases", "Vercel", "Next.js releases", "https://github.com/vercel/next.js/releases", "https://github.com/vercel/next.js/releases", "releases", "next"),
    "openai": DocumentSpec("openai-python-releases", "OpenAI", "Python SDK releases", "https://github.com/openai/openai-python/releases", "https://github.com/openai/openai-python/releases", "releases", "openai"),
    "@ai-sdk/openai": DocumentSpec("ai-sdk-releases", "Vercel", "AI SDK releases", "https://github.com/vercel/ai/releases", "https://github.com/vercel/ai/releases", "releases", "@ai-sdk/openai"),
    "anthropic": DocumentSpec("anthropic-python-releases", "Anthropic", "Python SDK releases", "https://github.com/anthropics/anthropic-sdk-python/releases", "https://github.com/anthropics/anthropic-sdk-python/releases", "releases", "anthropic"),
    "react": DocumentSpec("react-releases", "React", "React releases", "https://github.com/facebook/react/releases", "https://github.com/facebook/react/releases", "releases", "react"),
    "fastapi": DocumentSpec("fastapi-releases", "FastAPI", "FastAPI releases", "https://github.com/fastapi/fastapi/releases", "https://github.com/fastapi/fastapi/releases", "releases", "fastapi"),
    "django": DocumentSpec("django-releases", "Django", "Django releases", "https://github.com/django/django/releases", "https://github.com/django/django/releases", "releases", "django"),
    "flask": DocumentSpec("flask-releases", "Pallets", "Flask releases", "https://github.com/pallets/flask/releases", "https://github.com/pallets/flask/releases", "releases", "flask"),
    "express": DocumentSpec("express-releases", "Express", "Express releases", "https://github.com/expressjs/express/releases", "https://github.com/expressjs/express/releases", "releases", "express"),
    "undici": DocumentSpec("undici-releases", "Node.js", "Undici releases", "https://github.com/nodejs/undici/releases", "https://github.com/nodejs/undici/releases", "releases", "undici"),
    "vue": DocumentSpec("vue-releases", "Vue", "Vue releases", "https://github.com/vuejs/core/releases", "https://github.com/vuejs/core/releases", "releases", "vue"),
    "svelte": DocumentSpec("svelte-releases", "Svelte", "Svelte releases", "https://github.com/sveltejs/svelte/releases", "https://github.com/sveltejs/svelte/releases", "releases", "svelte"),
}


def documents_for(files: dict[str, str], custom: list[DocumentSpec] | None = None, limit: int = 6) -> list[DocumentSpec]:
    """Build a small, relevant watchlist from model identifiers and installed packages."""
    models = [model.lower() for model in production_models(files)]
    dependencies = inventory(files)
    names = {item["name"] for item in dependencies}
    specs: list[DocumentSpec] = list(custom or [])
    if any(model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")) for model in models) or names & {"openai", "@ai-sdk/openai"}:
        specs.extend([DOCUMENTS[0], OPENAI_PRICING, OPENAI_STATUS])
    if any(model.startswith("claude-") for model in models) or names & {"anthropic", "@anthropic-ai/sdk"}:
        specs.extend([DOCUMENTS[1], ANTHROPIC_RELEASES])
    priority = ["@ai-sdk/openai", "openai", "next", "fastapi", "django", "express", "react", "undici", "vue", "svelte", "flask"]
    specs.extend(RELEASE_WATCHES[name] for name in priority if name in names)
    unique: dict[str, DocumentSpec] = {}
    for spec in specs:
        unique.setdefault(spec.key, spec)
    return list(unique.values())[:limit]


def research_query(files: dict[str, str], specs: list[DocumentSpec]) -> str | None:
    """One repository-scoped search request per refresh, restricted to an official domain."""
    models = production_models(files)
    if models:
        provider = "OpenAI" if any(model.lower().startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")) for model in models) else "Anthropic"
        host = "developers.openai.com" if provider == "OpenAI" else "platform.claude.com"
        docs_path = "/api/docs" if provider == "OpenAI" else "/docs/en"
        terms = " ".join(models[:3])
        return f"site:{host}{docs_path} {terms} model deprecations retirement migration"
    package_spec = next((spec for spec in specs if spec.package), None)
    if package_spec:
        host = urlparse(package_spec.url).hostname
        return f"site:{host} {package_spec.package} (release notes OR security fix OR deprecation)"
    return None


def validate_watch_url(url: str, title: str = "") -> DocumentSpec:
    """Validate a public HTTPS page before sending its URL to Context.dev."""
    parsed = urlparse(url.strip())
    host = parsed.hostname
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or len(url) > 1000:
        raise ValueError("Use a public HTTPS URL without embedded credentials")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private and local network addresses cannot be watched")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")) or "." not in host:
        raise ValueError("Private and local network addresses cannot be watched")
    key = stable_id("custom", url.strip(), length=12)
    clean_title = safe_excerpt(title, 80) or "Custom web watch"
    return DocumentSpec(key, host.replace("www.", ""), clean_title, url.strip(), url.strip(), "custom", custom=True)


_STATUS_WORDS = re.compile(r"\b(?:operational|degraded(?:\s+performance)?|partial\s+outage|major\s+outage|under\s+maintenance|investigating|identified|monitoring|resolved|incident)\b", re.I)


def status_snapshot(text: str) -> str:
    """Keep component state and incident context, excluding navigation and page chrome."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected: list[str] = []
    for index, line in enumerate(lines):
        if not _STATUS_WORDS.search(line):
            continue
        for candidate in (lines[index - 1] if index else "", line, lines[index + 1] if index + 1 < len(lines) else ""):
            if len(candidate) <= 500 and candidate not in selected:
                selected.append(candidate)
        if len(selected) >= 81:
            break
    if selected:
        return "\n".join(selected[:81])
    # An unrecognized page stays reviewable and unchanged parsing is explicitly not a health claim.
    return "Unrecognized service-state layout; primary-source review required\n" + text[:16_000]


def custom_spec(data: dict) -> DocumentSpec:
    return DocumentSpec(
        data["key"], data["provider"], data["title"], data["url"], data["scrape_url"],
        "custom", custom=True,
    )


def custom_dict(spec: DocumentSpec) -> dict:
    return {"key": spec.key, "provider": spec.provider, "title": spec.title, "url": spec.url, "scrape_url": spec.scrape_url}
