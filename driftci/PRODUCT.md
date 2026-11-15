# DriftCI

> Your dependencies changed. Your codebase got the memo.

DriftCI is a live-web operations console for AI application teams. It watches official model/API documentation through Context.dev, resolves live vulnerability intelligence from OSV and CISA KEV, maps material changes to exact repository files, and produces reviewable remediation patches with citations and targeted checks.

## Product principles

1. **Live web to action**, not search or chat. Every material signal has repository evidence and a next action.
2. **No invented certainty.** Installed != exploitable. Reachability is a heuristic and is labelled accordingly. Live, cached, historical replay, and controlled demo evidence are explicitly distinguished.
3. **Human approval.** DriftCI never silently merges or deploys. Without GitHub credentials it exports a real patch and says so.
4. **Primary sources.** Official documentation/advisories are displayed alongside every decision. Web content is untrusted data and is never executed.
5. **Useful offline.** The checked-in example workspace and historical replay make the demo reproducible. Live mode uses Context.dev, OSV, and CISA.

## Initial experience

The seeded repository is `junction/orders-ai`, a TypeScript/Next.js support operations application. It contains a legacy OpenAI snapshot model and a Next.js version with known advisories. The UI starts at a populated Mission Control overview. Users can inspect signal evidence, generate a targeted fix, approve/export it, and work a CVE incident checklist. `Replay historical incident` replays the documented OpenAI `gpt-4-0314` shutdown (2026-03-26), announced 2025-09-26; it is not represented as a newly announced event. The official pages are now `https://developers.openai.com/api/docs/deprecations` and its `.md` representation.

## Main screens

- **Mission Control:** risk summary, decision queue, dependency blast radius, live source status, recent activity.
- **Change radar:** model/API/pricing/deprecation events with filters and source-to-code evidence.
- **Vulnerabilities:** active incidents, CVE history, CVSS/KEV metadata, reachability clues, response checklist, fix action.
- **Evidence:** immutable-looking source receipt cards (retrieval timestamp, mode, publisher, URL) and affected files.
- **Repository drawer:** connect a GitHub repository or restore the example workspace.

## Backend API contract

All endpoints are under `/api`.

### `GET /api/health`
```json
{
  "ok": true,
  "version": "1.0.0",
  "context_dev": {"configured": true, "mode": "live"},
  "github": {"configured": false, "mode": "patch export"},
  "last_scan_at": "ISO timestamp or null",
  "source_counts": {"live": 2, "cached": 0, "replay": 1}
}
```

### `GET /api/bootstrap`
```json
{
  "workspace": {"id":"demo","name":"Orders AI","repository":"junction/orders-ai","branch":"main","environment":"Production","source":"demo"},
  "summary": {"risk_score":82,"active_changes":2,"critical_vulnerabilities":1,"affected_dependencies":2,"remediations_ready":1,"production_models":2,"resolved_this_month":4,"mean_response_hours":1.7},
  "signals": ["Signal objects"],
  "dependencies": [{"name":"next","ecosystem":"npm","version":"14.2.3","kind":"framework","health":"critical","usage_count":2,"issues":1}],
  "activity": [{"id":"a1","type":"scan","title":"Live sources checked","detail":"3 official sources · 2 decisions required","created_at":"ISO"}],
  "sources": [{"id":"src1","publisher":"OpenAI","title":"Model deprecations","url":"https://...","status":"cached","last_checked_at":"ISO","event_count":1}],
  "incidents": ["Incident objects"],
  "history": ["Incident objects"],
  "remediations": ["Remediation objects"],
  "metrics": {"source_receipts":3,"files_indexed":8,"dependencies_indexed":5,"context_queries":1}
}
```

### Signal object
```json
{
  "id":"sig-model-gpt4-0314",
  "kind":"deprecation",
  "severity":"critical",
  "state":"needs_action",
  "title":"A retired model is still configured",
  "summary":"gpt-4-0314 was shut down on 26 Mar 2026. Two production call sites still select it.",
  "provider":"OpenAI",
  "affected_assets":["Support summaries","Escalation drafts"],
  "deadline":"2026-03-26T00:00:00Z",
  "cve":null,
  "cvss":null,
  "kev":false,
  "fixed_version":null,
  "replacement":"gpt-4.1",
  "reachability":"confirmed",
  "recommendation":"Replace the snapshot identifier and run the existing evaluation workflow before deployment.",
  "evidence":[{"file":"src/lib/ai.ts","line":6,"snippet":"export const SUMMARY_MODEL = \"gpt-4-0314\";","reason":"Exact production model identifier"}],
  "source_receipts":[{"publisher":"OpenAI","title":"Model deprecations","url":"https://developers.openai.com/api/docs/deprecations","retrieved_at":"2026-03-26T00:00:00Z","mode":"historical_replay","quote":"Mar 26, 2026: gpt-4-0314 — recommended replacement gpt-5, or gpt-4.1 for latency-sensitive tasks"}],
  "remediation_id":null,
  "created_at":"ISO"
}
```
Allowed kinds: `deprecation`, `vulnerability`, `api`, `pricing`, `status`. Allowed severities: `critical`, `high`, `medium`, `low`, `info`. States: `needs_action`, `acknowledged`, `fix_ready`, `resolved`, `monitoring`.

### `GET /api/signals?kind=&severity=` and `GET /api/signals/{id}`
Return filtered signal lists or one signal with all evidence.

### `POST /api/scan`
Runs a live refresh where credentials/network permit, then returns the new bootstrap payload. Individual source failures never erase last-known evidence; errors appear in source status/activity.

### `POST /api/demo/replay` and `POST /api/demo/reset`
Replay/reset the labelled historical OpenAI retirement example. Return bootstrap.

### `GET /api/incidents`
```json
{"active":["Incident objects"],"history":["Incident objects"],"metrics":{"active":1,"critical":1,"resolved":4,"mean_response_hours":1.7}}
```

### Incident object
```json
{
  "id":"inc-CVE-2025-29927",
  "cve":"CVE-2025-29927",
  "title":"Next.js middleware authorization bypass",
  "severity":"critical",
  "cvss":9.1,
  "kev":false,
  "state":"triaging",
  "first_seen_at":"ISO",
  "resolved_at":null,
  "affected_package":"next",
  "affected_version":"14.2.3",
  "fixed_version":"14.2.25",
  "reachability":"likely",
  "reachability_reason":"middleware.ts contains authorization logic; verify deployment behavior before relying on this heuristic.",
  "summary":"Official OSV/GitHub advisory summary.",
  "affected_files":[{"file":"middleware.ts","line":1,"snippet":"...","reason":"Middleware present"}],
  "source_receipts":[],
  "actions":[{"id":"ack","label":"Acknowledge incident","detail":"Assign an incident owner","status":"done","completed_at":"ISO"},{"id":"contain","label":"Contain exposure","detail":"Move authorization checks to a defense-in-depth layer","status":"pending","completed_at":null},{"id":"patch","label":"Apply fixed version","detail":"Upgrade next to 14.2.25 or later","status":"pending","completed_at":null},{"id":"verify","label":"Verify remediation","detail":"Confirm dependency version and run application security tests","status":"pending","completed_at":null},{"id":"resolve","label":"Resolve & document","detail":"Record residual risk and close the incident","status":"pending","completed_at":null}],
  "signal_id":"sig-CVE-2025-29927"
}
```

### `POST /api/incidents/{id}/actions/{action_id}`
Body `{"status":"done"|"pending"}`. Updates incident state/timeline and returns the incident. Validate transitions.

### `GET /api/incidents/{id}/report`
Returns a downloadable Markdown incident-response record: impact, reachability uncertainty, exact code evidence, checklist timestamps, advisory receipts and remaining human validation.

### `POST /api/remediations`
Body `{"signal_id":"sig-model-gpt4-0314"}`. Generates and stores a deterministic patch.

### Remediation object
```json
{
  "id":"rem-abc123",
  "signal_id":"sig-model-gpt4-0314",
  "title":"Replace retired OpenAI snapshot",
  "status":"ready_for_review",
  "summary":"1 file changed · 2 targeted checks",
  "files":[{"path":"src/lib/ai.ts","before":"...","after":"...","diff":"unified diff","additions":1,"deletions":1}],
  "checks":[{"name":"Retired identifier removed","status":"passed","detail":"No references to gpt-4-0314 remain in changed files"},{"name":"Targeted configuration check","status":"passed","detail":"Replacement is explicit and reviewable"}],
  "source_receipts":[],
  "can_open_pr":false,
  "created_at":"ISO",
  "approved_at":null,
  "pr_url":null,
  "pr_number":null
}
```
`POST /api/remediations/{id}/approve` marks human approval and returns remediation. `GET /api/remediations/{id}/patch` returns `text/x-patch`. `POST /api/remediations/{id}/open-pr` uses GitHub only when configured, otherwise returns HTTP 409 with a clear patch-export message.

### `POST /api/repositories/connect`
Body `{"url":"https://github.com/owner/repo"}`. Public repository download/scan. No arbitrary local paths or command execution. Returns bootstrap.

### `DELETE /api/workspace`
Restore the built-in demo.

## Frontend direction

Polished, information-dense operations console. Deep ink/navy surfaces, warm white primary content where useful, electric mint for healthy/live states, coral for critical, amber for warnings. Avoid generic purple gradients, glassmorphism overload, emojis, and chatbot UI. Typography: Geist/Inter-style sans plus monospace for identifiers and diffs. Use lucide-react icons. Responsive desktop-first with usable mobile stacking.

Suggested layout: slim dark sidebar with DriftCI logo and workspace switcher; main content with a compact command bar, an editorial page heading, decision cards, source receipts, and a right-side signal detail drawer when selected. Every chart must encode real API data. No fake sparklines or unsupported customer logos. A demo replay control should be visible but clearly labelled.

## Build/run

Backend: FastAPI + SQLite + httpx, Python 3.11+. Frontend: Vite + React + TypeScript. A single production FastAPI process serves `web/dist`. Document setup and environment variables in `README.md`; never check in credentials.
