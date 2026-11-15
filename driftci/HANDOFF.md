# DriftCI — current handoff

**Status (2026-11-15 ~05:20 EET):** Context.dev watch prototype implemented, deployed and validated. The official brief supplied by the user asks for a product reacting to the live web and lists “The Web, Watched” as inspiration; it does not specify a remote monitor resource contract.

## Product now

- Context.dev **scrape + scoped search** is central to the workflow. Repository model/dependency inventory selects up to six relevant official deprecation, pricing and SDK/framework release pages.
- Every source keeps a normalized baseline. Later differing content creates a bounded persistent observation with hashes, line counts and added/removed excerpts. First baselines do not create fake alerts.
- Changed pricing/model text maps to exact model identifiers; release watches map to installed dependency declarations. Users inspect primary receipts/code and mark signals reviewed or resolved.
- Public custom HTTPS watches share the same pipeline. Research accepts only results on the requested official hostname.
- Context.dev controls: six-hour cache, 6.2-second pacing, six scrapes and one search per refresh, shared lock/cooldown and an 80-credit daily default with pre-request reservation. UI counters are local, not account reconciliation.
- Visible AI/deterministic patch-generation and patch-review buttons have been removed from Mission Control, Change Inbox, SignalDrawer and Vulnerabilities. Existing backend remediation code/tests remain for compatibility but are not product-facing.
- CVE response retains OSV/CISA, labelled reachability clues, ordered checklists, history and Markdown export.

## Deployment and data

- Public UI: **https://driftci.ajc.contexio.fi**, service `driftci-app`, loopback port 8100.
- Current public workspace is deliberately **`junction/orders-ai`**, not the old `nodejs/node` stress case. It demonstrates two configured OpenAI models and five relevant Context.dev watches.
- A single live refresh completed in **34.4 seconds** at 05:10–05:11 EET: five scrapes + one search, six queries and seven credits for that refresh, zero initial change observations (correct baseline behavior).
- The local cumulative ledger is 11 credits: two earlier credits, seven for the initial five-scrape/one-search refresh, and two for a refined official-domain query. Subsequent browser QA refreshes used cache.
- No genuine live external-page diff has been observed yet. Diff behavior is tested with changing mocked responses. Do not call seeded baseline sources “observed changes.”
- Live OSV returns many real advisories for the intentionally old Next.js version. Keep them; do not hardcode a quieter result.

## Source coverage

- GitHub connections still use pinned-commit tree metadata and selected raw files, never archives or code execution.
- GitHub read defaults are **120 files/4 MB**, with 1 MB per file, 25-second source batch, per-file/whole-connect deadlines and explicit partial coverage.
- Source contents do not go to Context.dev. Custom watch URLs are validated public HTTPS and capped at 12.

## Validation and docs

- **35 backend tests pass**, production frontend build passes.
- Chromium workflow suite passed all seven checks with zero JavaScript errors, including 390px Web Watch and Mission Control.
- `README.md` is the main guide; `DEMO.md` is the two-minute script; `EVIDENCE.md` records actual live/browser validation; `THREAT_MODEL.md` documents boundaries; `SUBMISSION.md` remains a local draft.
- The current Context.dev integration is Web Scrape/Search. **Do not claim remote monitor IDs, schedules or webhooks.** `watcher.enabled` is a local polling timer.
- Run `systemctl --user restart driftci-app` after backend changes and `cd web && npm run build` after frontend changes. Avoid another service on ports 8090/8100.

## Useful next work

- Add authenticated private-repository support and per-tenant persistence before exposing real customer code.
- Reconcile local Context.dev credits with the account dashboard when someone with account access can do so.
- Collect a real later-page-change observation organically; never manufacture one for the public live demo.
- Reduce vulnerability alert noise with source-backed grouping if time permits, without hiding advisories or overstating reachability.
