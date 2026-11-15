# DriftCI product and API contract

DriftCI connects live pull requests and CI to official web evidence. The Release Room is the primary workflow: recent GitHub changes, checks, reviews and Context.dev observations share one durable event timeline. Repository-aware review and vulnerability response remain available alongside it. Context.dev supplies normalized page content and scoped research. DriftCI owns repository selection, local polling, snapshots, change observations, evidence matching, review state and vulnerability response.

## Product principles

1. **A source needs memory.** The first successful retrieval establishes a baseline. A later normalized hash difference produces an observation; the initial page does not.
2. **Evidence before action.** Each signal links primary source receipts and exact repository locations. Reviewers resolve non-CVE signals after external validation; CVEs resolve through their incident checklist.
3. **Live, cached and replay are different.** Retrieval mode and source health remain visible. Source failures preserve last-known evidence.
4. **Coverage and cost are product data.** Partial repository/package scans are warnings, and local Context.dev usage is visible beside its ceiling.
5. **Repository code stays local.** Only manifests and allowlisted source text are read. Code is not sent to Context.dev or executed.

6. **Release decisions have exact scope.** A named reviewer records a local ready/hold decision for one PR head, evidence fingerprint and check-run snapshot. Human review flags alone do not change the external-evidence fingerprint. GitHub approvals, CI results and DriftCI decisions remain separate records.

## Main screens

- **Release Room:** recent PRs, exact heads, bounded changed files, checks, review freshness, matching external evidence, the live event timeline and local release decisions.
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
  "version": "2.0.0",
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
  },
  "release_stream": {
    "enabled": true,
    "poll_interval_seconds": 90,
    "webhook_configured": false,
    "last_polled_at": "2026-11-15T04:22:17Z",
    "last_success_at": "2026-11-15T04:22:17Z",
    "last_error": null,
    "detail_pending": 0,
    "sse_path": "/api/events/stream",
    "status_cache_ttl_seconds": 300,
    "status_hot_ttl_seconds": 45
  }
}
```

The values above illustrate response shape rather than current billing. Counters are locally recorded, not remote account reconciliation. `watcher` describes DriftCI's ordinary web timer, not a Context.dev monitor resource. `release_stream` separately describes GitHub ingestion and activity-scoped status watches. Its last successful retrieval and last error remain visible when retained evidence is stale.

### `GET /api/bootstrap`

Returns:

- `workspace`: repository identity, branch and optional selective-read coverage.
- `summary`: risk, active changes, affected dependencies, production models, watched sources and observed changes.
- `release.pull_requests`: recent PRs with exact head SHA, bounded files/checks/reviews, matched external evidence and a fact-based evidence hash. Decisions are returned only when the current head/evidence hash matches. An expired decision is returned separately.
- `release.events`: sequenced, deduplicated GitHub, web and local-decision records. Initial imports carry `baseline=true`. Publication/occurrence and local receipt timestamps are distinct.
- `release.latest_seq` and `release.status`: the event cursor and independent GitHub freshness/transport state.
- `signals`: complete decision objects ordered by state/severity.
- `sources`: source health, category, baseline/change timestamps and at most 12 public observations per source. Internal markdown snapshots are omitted.
- `changes`: flattened observations ordered newest first, each with optional `signal_id` and repository-matched terms.
- `discoveries`: up to five official-host research results.
- `research`: scoped query, retrieval timestamp and mode when available.
- `dependencies`, `activity`, `incidents`, `history`, and local usage `metrics`.

### Release ingestion and events

`POST /api/releases/refresh` retrieves a recent PR window and bounded detail, then refreshes only status sources with activity-scoped TTLs. It does not run the full repository source reader or ordinary six-hour documentation/search refresh.

- At most 10 recent PRs are retained in the display window, with at most 2 detail turns per pass.
- A detail turn fetches at most 30 files and 12,000 diff characters per file, plus at most 50 reviews and 50 check runs. Omitted, truncated or potentially paginated evidence remains incomplete.
- An unchanged settled PR is quiet after its coverage settles. Known structural limits are not repeatedly downloaded; request failures and known-pending checks remain retryable.
- Pending or failing checks block ready, irrespective of complete file coverage.
- Matching uses current paths and added/context diff lines. Removed lines and deleted files are excluded. The associated repository index and PR detail stay explicitly partial.

`GET /api/events/stream` returns durable monotonically sequenced events over SSE. `after=SEQ` and `Last-Event-ID` replay unseen records. Connection and keepalive comments are not changes. Baseline imports are distinguished from later observations. The browser advances its cursor, coalesces refreshes and remains usable if the upstream GitHub API is rate limited.

`POST /api/github/webhook` requires `DRIFTCI_GITHUB_WEBHOOK_SECRET` and live mode. It requires an HMAC-SHA256 signature, supported event and expected repository, deduplicates the delivery, then reconciles actual state through the GitHub reader. Request bodies are limited to 512 KB. Missing configuration returns 503 and invalid signatures return 401. Webhooks do not send release commands to GitHub.

GitHub polling persists ETags and transport health. Rate-limit and retry headers drive a window in which scheduled upstream requests are suppressed. Repeated failures without retry metadata use bounded exponential backoff. Partial evidence and source errors cannot be presented as fresh or complete coverage.

### Release decisions and receipts

`POST /api/releases/{pr_id}/decision` accepts:

```json
{"decision": "ready", "reviewer": "Release owner", "note": "Evidence and application-owned validation reviewed."}
```

Allowed decisions are `ready` and `hold`. A reviewer name of 1–80 characters and a note of at most 1000 characters are required; only the note may be empty. Incomplete detail or running/failing checks block ready. A hold can record those limitations without claiming a GitHub approval.

The evidence hash covers relevant observation timestamps and source fingerprints, lifecycle/fixed-version facts, mapped paths and check-run ID/status/conclusion. Marking a signal reviewed or resolved does not itself invalidate the decision. A new head, changed relevant evidence or changed check-run snapshot does. Resolved findings do not create new active-review work, while their source history stays inspectable.

`GET /api/releases/{pr_id}/report` exports Markdown containing the current head, evidence hash, check/file coverage, current and expired local decisions, reviewer notes, external source fingerprints and limitations. It never claims that DriftCI executed application CI, approved/merged a GitHub PR, deployed the change or proved runtime safety.

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
- Ordinary cache TTL defaults to six hours for both methods; status sources use 300 seconds normally and 45 seconds during defined release activity, on the next 90-second release poll.
- Request starts are paced at 6.2 seconds.
- Scrape/search calls reserve 1/2 expected credits before a fresh request and stop at the configured daily ceiling.
- Successful live responses record `credits_consumed` from `key_metadata`, with conservative fallback estimates.
- Result pages must match the scoped official hostname. Text is sanitized and excerpts are bounded.
- Built-in sources are fixed mappings derived from model/package inventory. Custom pages require public HTTPS URLs.
- Local polling creates no Context.dev monitor resource or webhook and makes no claim that one exists.
