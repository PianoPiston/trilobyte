# DriftCI — condensed project handoff

**Status (2026-11-15):** salvageable prototype, not a validated Context.dev monitor submission. Pause redesign until the user reposts the official challenge/monitor details. This file is the short operational memory; the original long-form docs are not a substitute for those requirements.

## Preserve what works

- Location: `/home/user/junction/driftci`; latest code commit: **`a73494f`**.
- FastAPI/SQLite backend in `server/`, React/TypeScript frontend in `web/`.
- Standalone deployment: **https://driftci.ajc.contexio.fi**, local port 8100, systemd user service `driftci-app`. Do not interfere with the separate Stoa service on port 8090.
- GitHub connections use tree metadata and selected raw files at a pinned commit—no archive/clone. Defaults: 64 files / 2 MB / 25-second source batch, per-file and whole-connect deadlines. Partial file/package coverage is displayed.
- OSV/CISA advisory analysis, repository evidence, deterministic patches with approval/export, CVE checklists/history, and Markdown IR exports are implemented.
- **30 backend tests**, production frontend build and Chromium workflows passed. The real public `nodejs/node` browser connection completed in **4.6 s** (fresh uncached backend probe: 9.92 s), with zero browser errors.
- Public workspace is intentionally left on **`nodejs/node`**: 64 files, 189 scoped dependency records, 10 findings, OSV 32/76 checked / 44 explicitly pending. This is bounded npm/Python evidence, not exhaustive native/C++ SBOM coverage.
- Curated offline fixture remains at `examples/orders-ai`; replay/history are examples, not new live announcements. No GitHub token is attached, so PR creation is unavailable; patch export is real. Repository code is never executed.

## Context.dev facts and limits

- Actual client: `server/contextdev.py`, `POST https://api.context.dev/v1/web/scrape`, using the externally stored `CONTEXTDEV_API_KEY`.
- Local evidence: **two successful scrape retrievals** at 2026-11-15 01:50:14Z and 01:50:19Z; locally accumulated `context_credits = 2`.
- Later runs reused six-hour caches. Current Node workspace reports `context_queries = 0` after demo resets and cache hits. It has model findings from **OSV/CISA**, not a demonstrable Context.dev change → repository impact.
- **Account-side API usage has not been reconciled with the user's dashboard.** “Configured key” and locally cached evidence are not proof of ongoing account activity.
- **No real Context.dev monitors are implemented:** no monitor resources/IDs, schedules, check/run records, webhooks, monitor diffs, or alert timeline. `watcher.enabled` is only a local polling timer; the UI “Monitoring” label is only presentation state.
- Earlier descriptions of live watchers/monitoring overstated this. Correct description: periodic cached scraping plus repository/advisory analysis.

## Challenge and evidence record

- Only `driftci/SUBMISSION.md` exists: a **local draft**, not a registered submission.
- No confirmed Junction project/submission ID or official monitor specification is saved for DriftCI/Context.dev.
- The original workspace primary challenge is Stoa/Verda; do not replace or merge it without a decision.
- A teammate may have created an external entry, but none has been shared or verified here.

## On receipt of the official brief

1. Treat it as the new ground truth; extract the exact monitor lifecycle, required platform APIs/artifacts, dashboard evidence and judging/registration requirements.
2. Reframe the idea around those requirements while preserving the useful repository-to-remediation workflow and operational UI.
3. Show the correction plan before changing the core concept, then implement real monitor resources and persistent observed-change/run evidence.
4. Verify actual Context.dev monitor/API usage in the authoritative account/dashboard, not only a local counter. Update all overstated submission/demo claims.
5. Add tests for source failures, replay/history labeling, monitor lifecycle, partial coverage and performance; keep the same reproducible offline example.

Do not fabricate monitor records, wipe the existing Node workspace without a deliberate demo decision, or call this challenge-ready before those steps.
