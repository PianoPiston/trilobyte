# DriftCI product and API contract

DriftCI connects live pull requests and CI to official web evidence and a targeted repository dependency inventory. The Release Room is the primary workflow: recent GitHub changes, checks, reviews and Context.dev observations share one durable event timeline. Context.dev supplies normalized page content, scoped research, public GitHub metadata bytes and an actual repository-hosted hourly monitor. DriftCI owns repository selection, local source/advisory analysis, snapshots, evidence matching, monitor reconciliation and local review state.

## Product principles

1. **A source needs memory.** The first successful retrieval establishes a baseline. A later normalized hash difference produces an observation; the initial page does not.
2. **Evidence before action.** Each signal links primary source receipts and exact repository locations. Reviewers resolve non-CVE signals after external validation; CVEs resolve through their incident checklist.
3. **Live, cached and replay are different.** Retrieval mode and source health remain visible. Source failures preserve last-known evidence.
4. **Coverage and cost are product data.** Source reads, manifest parsing, unresolved declarations, native comparisons and advisory-query completion are separate coverage signals. Local Context.dev usage, in-flight reservations and monitor commitments are visible beside the configured ceiling, including retained prior overcommitment.
5. **Repository code stays local.** Only manifests and allowlisted source text are read. Code is not sent to Context.dev or executed.

6. **Release decisions have exact scope.** A named reviewer records a local ready/hold decision for one PR head, evidence fingerprint and check-run snapshot. Human review flags alone do not change the external-evidence fingerprint. GitHub approvals, CI results and DriftCI decisions remain separate records.

## Main screens

- **Release Room:** recent PRs, exact heads, bounded changed files, checks, review freshness, matching external evidence, the live event timeline and local release decisions.
- **Mission Control:** Context.dev pulse, risk/decision metrics, ranked signals, source health, highest-impact dependencies and recent activity.
- **Web Watch:** daily usage/credit ceiling, custom-watch form, observed-change diffs, inferred watchlist and official-domain research results.
- **Change Inbox:** searchable/filterable deprecation, vulnerability, API, pricing and status signals. No patch-generation actions.
- **Vulnerabilities:** active incidents, dependency scope, evidence manifest, CVE history, reachability uncertainty, ordered checklist and Markdown response export.
- **Evidence:** source receipts connected to decisions and affected source files.
- **Repository drawer:** pinned-commit manifest/native/source coverage, parser and advisory-query gaps, public GitHub connection, example restore and labelled historical replay.

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
      "daily_credit_limit": 10000,
      "monitor_credits_today": 6,
      "monitor_reserved_today": 42,
      "monitor_spent_and_reserved": 48,
      "ordinary_reserved_credits": 0,
      "daily_available": 9943,
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
    "metadata_transport": "context.dev_bytes",
    "last_metadata_retrieved_at": "2026-11-15T04:22:17Z",
    "context_metadata_error": null,
    "detail_pending": 0,
    "sse_path": "/api/events/stream",
    "status_cache_ttl_seconds": 300,
    "status_hot_ttl_seconds": 45
  }
}
```

The values above illustrate response shape rather than current billing. Counters are locally recorded, not remote account reconciliation. Monitor spent/reserved and in-flight ordinary reservations reduce remaining availability alongside settled ordinary usage; monitor creation uses the same calculation. `watcher` describes DriftCI's ordinary web timer, not a Context.dev monitor resource. `release_stream` separately describes GitHub ingestion and activity-scoped status watches. Its last successful retrieval and last error remain visible when retained evidence is stale.

### `GET /api/bootstrap`

Returns:

- `workspace`: repository identity, branch and targeted manifest/native/source/parser coverage with metadata transport/fallback state.
- `monitor`: the real remote monitor, schedule, latest/baseline state, run timing/credits and local reconciliation state when configured; null when unavailable.
- `summary`: risk, active changes, affected dependencies, production models, watched sources and observed changes.
- `release.pull_requests`: recent PRs with exact head SHA, bounded files/checks/reviews, matched external evidence and a fact-based evidence hash. Decisions are returned only when the current head/evidence hash matches. An expired decision is returned separately.
- `release.events`: sequenced, deduplicated GitHub, web and local-decision records. Initial imports carry `baseline=true`. Publication/occurrence and local receipt timestamps are distinct.
- `release.latest_seq` and `release.status`: the event cursor and independent GitHub freshness/transport state. Repository connect is initially PR-index-only; index-only records carry empty file/review/check arrays and incomplete coverage flags until bounded detail is retrieved.
- `signals`: complete decision objects ordered by state/severity.
- `sources`: source health, watch/category identity, baseline/change timestamps, up to 12 public observations and separate OSV batch/full-detail accounting. Internal markdown snapshots are omitted.
- `changes`: flattened observations ordered newest first, each with optional `signal_id` and repository-matched terms.
- `discoveries`: up to five official-host research results.
- `research`: scoped query, retrieval timestamp and mode when available.
- `dependencies`, `activity`, `incidents`, `history`, and local usage `metrics`. Dependencies distinguish declaration, resolved version, exactness, scope, manifest and advisory support. Vulnerability findings and incidents preserve `dependency_scope` and `manifest`; advisory ranges do not establish execution or exploitability.

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

Kinds: `deprecation`, `vulnerability`, `api`, `pricing`, `status`, `security_update`. States: `needs_action`, `acknowledged`, `monitoring`, `resolved`; older stored records may include `fix_ready`. Exact model lifecycle events use `deprecation`; generic page observations use the content/source classification.

### Signal endpoints

- `GET /api/signals?kind=&severity=` returns filtered signals.
- `GET /api/signals/{id}` returns one complete signal.
- `POST /api/signals/{id}/state` with `{"state":"acknowledged"|"monitoring"|"needs_action"|"resolved"}` records review state. Resolving a vulnerability through this endpoint returns HTTP 409; use the incident checklist.

### Refresh and watches

- `POST /api/scan` refreshes Context.dev documents/search, scoped OSV/CISA matches, the hosted-monitor record and PR status with shared locks/cooldowns/caches. Returns bootstrap. It uses the retained pinned repository snapshot; PR-detail freshness and repository-wide source coverage remain separate.
- `POST /api/watches` with `{"url":"https://status.example.com/provider","title":"Provider status"}` adds a custom public HTTPS watch, retrieves its baseline through the same bounded document refresh and returns bootstrap. Invalid private/local URLs return 400 before entering the scan gate.
- `DELETE /api/watches/{key}` removes the custom source and its associated web signals. Built-in watches cannot be deleted through this route.

Custom watch keys come from the source ID after removing its `src-` prefix.

### Repository connection

`POST /api/repositories/connect` with `{"url":"https://github.com/owner/repo"}` reads GitHub structured metadata, dependency-graph/SBOM data, manifests, native declarations and selected source at an immutable commit, then performs the normal scoped advisory/web/release/monitor scan. Defaults: 1,600 records, 32 MB total, 2 MB per file, 40 source-read seconds, 16 concurrent file reads, 6-second per-file reads and a 90-second connection deadline. Archives, clones and repository execution are prohibited.

`workspace.coverage` includes commit SHA, tree truncation, selected/read file counts, bytes, manifests/native files read, missing/parse-failed manifests, structured packages, skipped/failed/timed-out files, source-read time, metadata transport/fallback and independent wider-source completeness. Source and advisory-eligibility completion are different concepts. Nested manifests keep separate dependency scopes. `DELETE /api/workspace` restores the example.

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
- Scrape/metadata/search calls reserve expected credits before a fresh request. Settled ordinary usage, monitor spent/reserved credits and in-flight ordinary reservations share the daily availability calculation; reservations are released in `finally` paths.
- Hosted hourly monitoring is budgeted at 48 credits/day. Remote monitor/run/change APIs are reconciled explicitly. A baseline, failure, skip or no-change completion never becomes an advisory. Monitor text/citations cannot create automatic patches. Monitor webhooks are not implemented.
- Public `api.github.com` JSON may use `formats.bytes` through the scrape transport. Base64/body-size/content-type/JSON/envelope validation is applied. No GitHub authorization or repository source content is sent to Context.dev.
- Direct immutable raw source reads use `raw.githubusercontent.com` without GitHub authorization. OSV sends supported exact package/version tuples only; native declarations and unresolved ranges are retained as review gaps.
- OSV `{id, modified}` descriptors are expanded to full advisory records before range matching. Failed/paginated detail retrieval leaves affected package queries pending. Full advisory details have independent caches.
- Only application manifests may receive direct deterministic vulnerability patches; other scopes require their owning workflows.
- Successful live responses record `credits_consumed` from `key_metadata`, with conservative fallback estimates.
- Result pages must match the scoped official hostname. Text is sanitized and excerpts are bounded.
- Built-in sources are fixed mappings derived from model/package inventory. Custom pages require public HTTPS URLs.
- Local polling and Context.dev's remote scheduler are distinct. The optional HMAC GitHub webhook is separate and sends no release command to GitHub.
