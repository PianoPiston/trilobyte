# DriftCI — local submission draft

This is submission copy, not confirmation that a Junction platform entry is finalized. The verbatim challenge brief and platform submission status are not stored here.

## Name

**DriftCI**

## Punchline

**Live release evidence, from GitHub to the official web.**

## Short description

DriftCI connects live GitHub pull requests and CI to the official web pages around them. Context.dev retrieves official model lifecycle, pricing, SDK-release and status information. DriftCI records the source snapshots, maps relevant evidence to bounded PR diffs and repository code, and publishes every arrival to one durable live timeline.

A reviewer can see the PR head, check state, source receipt and observation time together, then record a local ready or hold decision for that exact evidence set. Later code, CI or external changes expire the previous decision. The exported Markdown record preserves what was reviewed and the remaining coverage limits. OSV and CISA KEV support the adjacent vulnerability-response workflow without conflating installed versions with exploitability.

## Challenge fit

**The Web, Watched.** External official pages are operational inputs to a release, not static background reference material. Context.dev supplies live retrieval and scoped research; DriftCI turns that material into an inspectable, repository-specific release workflow.

GitHub events come from read-only API polling with ETags, or an optional separately authenticated webhook. They do not consume Context.dev credits. Context.dev remains the external-web intelligence layer; polling, snapshots, impact matching and review state are owned by DriftCI.

## Technologies

Context.dev Web Scrape API, Context.dev Web Search API, GitHub REST/raw APIs, FastAPI, Python, SQLite, httpx, OSV, CISA Known Exploited Vulnerabilities, React, TypeScript, Vite.

## Innovation

Conventional dependency tools know manifests. Review tools know code. Search tools return links. DriftCI connects the release event to the external fact that may make its review stale.

Its differentiator is **evidence freshness at an exact PR head**. The evidence fingerprint includes relevant external facts, source fingerprints, mapped paths and check-run state. An old approval can become observably outdated; a local release decision cannot silently survive a changed head or evidence set. A human review flag by itself does not masquerade as a new external fact.

The product also makes resource discipline inspectable. Source reads are bounded, initial imports are baselines, web changes retain before/after excerpts, Context.dev usage has a credit ceiling, and GitHub retries stop during quota windows. Quiet polling does not repeatedly download a large diff just because its declared coverage limit remains partial.

## Impact

A PR can pass review just before a model retirement becomes relevant, a provider degrades, or an SDK/framework change affects its integration. DriftCI gives the person deciding whether to ship one place to inspect those facts, the current PR head and the CI state, then leave an accountable release record.

A large real AI SDK monorepo demonstrates that useful signals can be obtained without cloning the repository, executing untrusted code or generating a speculative patch. Its model catalog identifiers are explicitly distinguished from production invocation.

## Implementation

- Recent public PR ingestion with exact heads, bounded file patches, reviews and check runs.
- Durable, deduplicated event records and replayable server-sent events.
- Optional HMAC-verified GitHub webhooks with delivery deduplication and downstream state reconciliation.
- Repository-derived official deprecation, pricing, SDK/framework-release and provider-status watches through Context.dev.
- Normalized status snapshots; ordinary page snapshots with bounded diffs, hashes and retrieval provenance.
- Current-diff matching that excludes deleted files and removed lines.
- Readiness states for missing coverage, pending/failing CI, stale external evidence and changed heads.
- Named local ready/hold decisions bound to the head, evidence and check-run fingerprint, with Markdown exports.
- Six-hour ordinary Context.dev caches, 6.2-second pacing and an 80-credit daily ceiling. Provider-status caching uses activity-scoped 300/45-second TTLs on the 90-second release poller.
- GitHub ETags through a persistent SQLite store, rate-limit-aware retry backoff and no refetching unchanged bounded partial diffs.
- A selective 120-file / 4 MB pinned-commit repository reader with explicit partial coverage.
- OSV/CISA evidence, uncertainty labels, ordered response checklists, history and Markdown IR exports.
- **48 backend tests**, production frontend build, public HTTPS Chromium workflows, independent browser SSE observation and mobile layout checks.

## Live demo

https://driftci.ajc.contexio.fi

The public evaluation workspace currently connects the public **`vercel/ai`** repository. It is not a Vercel-operated console, and local QA decisions do not represent maintainer approvals. Dataset/source provenance and partial coverage are disclosed in the UI.

## Claims to verify when pitching

- Say that live API retrieval, source baselines and real GitHub observations are implemented. Cite the current source health timestamps.
- Verify the present number of active PRs, complete detail snapshots and actual web observations immediately before recording. These vary as the public repository changes.
- If no official page has changed recently, say so. Baselines and historical examples are not new live changes.
- Describe GitHub checks as observed results. DriftCI did not run the application’s tests or prove deployment safety.
- Keep local source identifiers distinct from production invocation, especially in SDK compatibility catalogs.

## Claims to avoid

- Do not claim remote Context.dev monitor resources, IDs, schedules, webhooks or monitor-side run history exist.
- Do not describe the GitHub-only webhook as a Context.dev monitor integration.
- Do not claim a live official-page change without a real later observation.
- Do not call local ledger counters an account-reconciled billing statement.
- Do not treat a selective repository index, check result or heuristic reachability clue as proof of safety or exploitability.
- Do not say DriftCI automatically merges, deploys or generates/manages approvals on GitHub.
