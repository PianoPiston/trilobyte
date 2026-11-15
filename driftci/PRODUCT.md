# DriftCI product and API contract

DriftCI turns official web changes into repository-aware review decisions. Context.dev supplies normalized page content and scoped research. DriftCI owns repository selection, local polling, snapshots, change observations, evidence matching, review state and vulnerability response.

## Product principles

1. **A source needs memory.** The first successful retrieval establishes a baseline. A later normalized hash difference produces an observation; the initial page does not.
2. **Evidence before action.** Each signal links primary source receipts and exact repository locations. Reviewers resolve non-CVE signals after external validation; CVEs resolve through their incident checklist.
3. **Live, cached and replay are different.** Retrieval mode and source health remain visible. Source failures preserve last-known evidence.
4. **Coverage and cost are product data.** Partial repository/package scans are warnings, and local Context.dev usage is visible beside its ceiling.
5. **Repository code stays local.** Only manifests and allowlisted source text are read. Code is not sent to Context.dev or executed.

## Main screens

- **Mission Control:** Context.dev pulse, risk/decision metrics, ranked signals, source health, highest-impact dependencies and recent activity.
- **Web Watch:** daily usage/credit ceiling, custom-watch form, observed-change diffs, inferred watchlist and official-domain research results.
- **Change Inbox:** searchable/filterable deprecation, vulnerability, API, pricing and status signals. No patch-generation actions.
- **Vulnerabilities:** active incidents, CVE history, reachability clues, ordered checklist and Markdown response export.
- **Evidence:** source receipts connected to decisions and affected source files.
- **Repository drawer:** pinned-commit source coverage, public GitHub connection, example restore and labelled historical replay.

## Backend API

All endpoints are under `/api`. JSON API responses use `Cache-Control: no-cache`.

### `GET /api/health`

```json
{
  "ok": true,
  "version": "1.1.0",
  "context_dev": {
    "configured": true,
    "mode": "live",
    "usage": {
      "queries": 7,
      "credits": 11,
      "daily_queries": 7,
      "daily_credits": 9,
      "daily_credit_limit": 80,
      "cache_ttl_seconds": 21600
    }
  },
  "github": {"configured": false, "mode": "read-only"},
  "last_scan_at": "2026-11-15T03:18:37Z",
  "source_counts": {"live": 6, "cached": 2, "partial": 0, "errors": 0, "replay": 0},
  "watcher": {
    "enabled": true,
    "interval_seconds": 900,
    "scan_cooldown_seconds": 30,
    "implementation": "local polling with independent Context.dev cache and credit budget"
  }
}
```

Counters are locally recorded, not remote account reconciliation. `watcher` describes DriftCI's local timer, not a Context.dev monitor resource.

### `GET /api/bootstrap`

Returns:

- `workspace`: repository identity, branch and optional selective-read coverage.
- `summary`: risk, active changes, affected dependencies, production models, watched sources and observed changes.
- `signals`: complete decision objects ordered by state/severity.
- `sources`: source health, category, baseline/change timestamps and at most 12 public observations per source. Internal markdown snapshots are omitted.
- `changes`: flattened observations ordered newest first, each with optional `signal_id` and repository-matched terms.
- `discoveries`: up to five official-host research results.
- `research`: scoped query, retrieval timestamp and mode when available.
- `dependencies`, `activity`, `incidents`, `history`, and local usage `metrics`.

### Signal object

```json
{
  "id": "sig-web-abc123",
  "kind": "pricing",
  "severity": "medium",
  "state": "needs_action",
  "title": "OpenAI API pricing changed",
  "summary": "Context.dev observed 1 added and 1 removed lines against the previous snapshot. 2 repository locations are attached for review.",
  "provider": "OpenAI",
  "affected_assets": ["gpt-4-0314"],
  "deadline": null,
  "cve": null,
  "cvss": null,
  "kev": false,
  "fixed_version": null,
  "replacement": null,
  "reachability": "confirmed",
  "recommendation": "Compare the added and removed lines, open the primary source, and validate any repository impact before changing production.",
  "evidence": [{"file": "src/lib/ai.ts", "line": 6, "snippet": "...", "reason": "Exact configured model identifier"}],
  "source_receipts": [{"publisher": "OpenAI", "title": "API pricing", "url": "https://developers.openai.com/api/docs/pricing", "retrieved_at": "ISO", "mode": "live", "quote": "..."}],
  "remediation_id": null,
  "created_at": "ISO",
  "watch_id": "src-openai-pricing",
  "change": {
    "id": "obs-abc123",
    "source_id": "src-openai-pricing",
    "observed_at": "ISO",
    "content_hash": "sha256",
    "previous_hash": "sha256",
    "added_lines": 1,
    "removed_lines": 1,
    "added": ["new official line"],
    "removed": ["old official line"]
  }
}
```

Kinds: `deprecation`, `vulnerability`, `api`, `pricing`, `status`. States: `needs_action`, `acknowledged`, `monitoring`, `resolved`; older stored records may include `fix_ready`. Exact model lifecycle events use `deprecation`; generic page observations use the content/source classification.

### Signal endpoints

- `GET /api/signals?kind=&severity=` returns filtered signals.
- `GET /api/signals/{id}` returns one complete signal.
- `POST /api/signals/{id}/state` with `{"state":"acknowledged"|"monitoring"|"needs_action"|"resolved"}` records review state. Resolving a vulnerability through this endpoint returns HTTP 409; use the incident checklist.

### Refresh and watches

- `POST /api/scan` refreshes Context.dev documents/search and OSV/CISA with shared lock, cooldown and caches. Returns bootstrap.
- `POST /api/watches` with `{"url":"https://status.example.com/provider","title":"Provider status"}` adds a custom public HTTPS watch, retrieves its baseline through the same bounded document refresh and returns bootstrap. Invalid private/local URLs return 400 before entering the scan gate.
- `DELETE /api/watches/{key}` removes the custom source and its associated web signals. Built-in watches cannot be deleted through this route.

Custom watch keys come from the source ID after removing its `src-` prefix.

### Repository connection

`POST /api/repositories/connect` with `{"url":"https://github.com/owner/repo"}` reads selected production manifests/source files at a pinned commit and runs the normal scan. Defaults: 120 files, 4 MB total, 1 MB per file, 25-second source batch, 6-second per-file reads and a 90-second whole-connection deadline.

`workspace.coverage` includes commit SHA, repository/candidate/read file counts, bytes, skipped/failed/timed-out files, source-read time and partial/complete state. Nested manifests keep separate dependency scopes. `DELETE /api/workspace` restores the example.

### Incidents and exports

- `GET /api/incidents` returns active incidents, resolved history and aggregate metrics.
- `POST /api/incidents/{id}/actions/{action}` with `{"status":"done"|"pending"}` updates ordered response state. Completing a later step first returns HTTP 409.
- `GET /api/incidents/{id}/report` returns `text/markdown` with impact, fixed-version guidance, reachability uncertainty, source evidence, checklist timestamps and remaining validation.

### Demo

`POST /api/demo/replay` restores the explicitly labelled historical OpenAI retirement. `POST /api/demo/reset` restores the deterministic example workspace and clears current workspace source/signal state while retaining the global local Context.dev usage ledger.

## Context.dev implementation

- `POST https://api.context.dev/v1/web/scrape` retrieves markdown for at most six relevant sources per refresh.
- `POST https://api.context.dev/v1/web/search` runs at most one scoped query with five results and highlights enabled.
- Cache TTL defaults to six hours for both methods; request starts are paced at 6.2 seconds.
- Scrape/search calls reserve 1/2 expected credits before a fresh request and stop at the configured daily ceiling.
- Successful live responses record `credits_consumed` from `key_metadata`, with conservative fallback estimates.
- Result pages must match the scoped official hostname. Text is sanitized and excerpts are bounded.
- Built-in sources are fixed mappings derived from model/package inventory. Custom pages require public HTTPS URLs.
- Local polling creates no Context.dev monitor resource or webhook and makes no claim that one exists.
