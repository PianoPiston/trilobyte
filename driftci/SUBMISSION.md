# DriftCI — local submission draft

This file is submission copy, not proof that a Junction platform entry has been finalized.

## Name

**DriftCI**

## Punchline

**The web, watched. The blast radius, known.**

## Short description

Production software depends on official web pages that package managers do not watch: model lifecycle tables, changing prices, SDK releases and operational policies. DriftCI uses Context.dev to retrieve those pages, remembers their snapshots, detects subsequent changes and maps them to exact repository dependencies and model identifiers. Reviewers get a citable decision, affected code locations and an accountable review state. OSV and CISA KEV feed the same repository-aware workflow for CVE response.

## Challenge fit

**The Web, Watched.** DriftCI turns live web data into repository-aware decisions and review actions. Context.dev is used directly for both structured page scraping and scoped web search. The product adds durable baselines, observed-change diffs, source-to-code impact mapping, persistent review states and incident-response records.

## Technologies

Context.dev Web Scrape API, Context.dev Web Search API, FastAPI, Python, SQLite, httpx, OSV, CISA Known Exploited Vulnerabilities, GitHub REST/raw APIs, React, TypeScript, Vite.

## Innovation

Dependency tools see manifests. Search tools return links. DriftCI connects both sides of an operational change: a normalized official-page snapshot and the exact code that depends on it. The first retrieval establishes a baseline; only a later differing snapshot becomes a change observation. Users can inspect added and removed lines, source hashes, retrieval mode and affected files instead of trusting an unexplained AI alert.

## Impact

A missed model retirement breaks production call sites; a price change alters unit economics; an SDK or framework release can require code review. DriftCI shortens the path from official publication to understood repository impact and accountable review. Its selective source reader works on large public repositories without archives or code execution, and its bounded source/vulnerability checks state their coverage rather than implying safety from missing findings.

## Implementation

- Repository-derived OpenAI/Anthropic deprecation, pricing and release watches.
- At most six Context.dev scrapes plus one official-domain search per refresh.
- Six-hour caches, 6.2-second pacing and an 80-credit local daily ceiling with pre-request reservation.
- Persistent normalized snapshots, content hashes, bounded added/removed diffs and observation history.
- Exact model/dependency evidence, source receipts and human review transitions.
- Public HTTPS custom watches; repository code is never sent to Context.dev.
- Selective pinned-commit GitHub reads at 120 files / 4 MB by default.
- OSV/CISA vulnerability analysis, reachability uncertainty, persistent checklists, CVE history and Markdown IR export.
- 35 deterministic backend tests and real desktop/mobile Chromium workflows.

## Two-minute video outline

### 0:00–0:15 — the invisible dependency

Show an official model lifecycle page beside the two production model identifiers.

> “Your production stack depends on web pages, not just packages. This model retirement exists in official documentation and in two call sites. DriftCI connects the two.”

### 0:15–0:40 — the web, watched

Open **Web Watch**.

> “Context.dev retrieves five relevant official pages and one scoped research set for this repository. DriftCI paces requests, caches them for six hours and enforces a daily credit ceiling. Every first retrieval is a baseline, so the product does not create an alert merely because a page exists.”

Show the local usage meter, live/cached labels and official research results. Describe polling accurately as DriftCI-local polling with Context.dev scrape/search.

### 0:40–1:10 — exact blast radius and review

Open the `gpt-4-0314` decision, its receipt and both source files. Click **Mark reviewed**.

> “The official retirement is mapped to support summaries and escalation drafts. Reviewers see the exact source evidence, migration recommendation and remaining validation. Changed pricing or release snapshots follow the same path with added and removed lines.”

### 1:10–1:40 — vulnerability response

Open the Next.js advisory, response checklist and Markdown export.

> “OSV and CISA feed the same operational loop. Installed-version evidence is not presented as proof of exploitability. The team acknowledges, contains, patches, verifies and resolves one persistent incident with a portable response record.”

### 1:40–2:00 — close

Return to Mission Control.

> “DriftCI: the web, watched. The blast radius, known. Live Context.dev evidence becomes an inspectable decision, with explicit costs, coverage and uncertainty.”

## Claims to avoid

- Do not claim remote Context.dev monitor resources, IDs, schedules or webhooks exist.
- Do not call local ledger counters an account-reconciled billing statement.
- Do not label initial baselines or historical replay as newly observed live changes.
- Do not claim CVE reachability is proof of exploitability or that application CI/model evaluations ran.
- Do not claim Context.dev was used for OSV/CISA; those use separate public endpoints.
- Do not imply exhaustive source or SBOM coverage for a partial large-repository index.
