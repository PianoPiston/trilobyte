# DriftCI evidence and validation

The assertions below describe measured prototype behavior. It is an evidence trail, not a claim of production readiness. Live counters can change; timestamps and coverage limits are part of the evidence.

## Live public integration

DriftCI is deployed at **https://driftci.ajc.contexio.fi** and connects the public **`vercel/ai`** repository through read-only GitHub API/raw requests plus Context.dev scrape/search.

The final connection measurement selected **120 / 6,817 candidate files**, read **1,120,611 bytes**, skipped one oversized file and used **2.765 seconds** for the selective source reads. The index was pinned to main-branch commit `8ba3940d3dd1f3cd3c4365bbaec505c6ef0eb1e3`; the tree contained 10,213 files and was not truncated by GitHub. No archive, clone, package installation or repository-code execution was used.

At the **2026-11-15T05:01:03Z** measurement:

| Item | Observed state |
|---|---|
| Recent PR window | 10 records, 8 open |
| PRs with complete bounded file/review/check detail | 5 of the 10 records; two detail retrievals remained pending in the current pass |
| GitHub release retrieval | Live; no current retrieval error |
| GitHub token / webhook secret | Not configured; anonymous read-only API and polling |
| Context.dev ordinary sources | Five relevant official deprecation/pricing/release pages |
| Activity-scoped status source | OpenAI service status, retrieved through Context.dev |
| Scoped research | Five same-host results |
| Local cumulative Context.dev counters | 15 queries / 20 credits; not account-side billing reconciliation |
| Observed post-baseline official-page diffs | **0** in that snapshot |

The five ordinary sources were OpenAI model deprecations and pricing, Anthropic model deprecations and release notes, and Next.js releases. The provider-status source is a separate, activity-scoped watch. Sources and their retrieval modes are visible in Web Watch.

**No later official-page change should be inferred from the initial baselines or the zero-observation snapshot.** The first successful snapshot is stored without an alert. Existing lifecycle matches may be relevant without having been newly observed today. The historical replay is separately labelled.

The source inventory is a partial base-branch index. Each PR has its own exact head and bounded changed-file diffs; a model identifier in an SDK compatibility catalog is not evidence that a production application invokes that model.

## Freshness and rate limits

Anonymous GitHub capacity was exhausted during initial public-repository setup. A direct response reported core quota **60 used / 0 remaining**, with reset at **2026-11-15T04:56:52Z**. Existing PR evidence and local decisions stayed available, while source health showed retained/error state rather than fresh success. The subsequent public connection succeeded after capacity returned, with quota/retry health visible in `/api/health`.

The implementation persists ETags and retry windows across restarts. It uses GitHub reset headers, honors `Retry-After`, and applies bounded backoff when an error lacks retry metadata. When a 403 omits usable reset headers, one bounded `/rate_limit` lookup can provide the actual core reset. Suppressed retries do not make an upstream PR request. Stable, known coverage limits avoid downloading the same oversized/incomplete PR detail each cycle.

A ready decision is rejected while GitHub freshness is unavailable, detail coverage is incomplete, or checks are pending/failing. A reviewer can still record a hold that explicitly explains the limitation. No source error is converted into a successful refresh or synthetic activity.

## Public browser verification

`DRIFTCI_RELEASE_DECISION_QA=1 scripts/browser-smoke-docker.sh https://driftci.ajc.contexio.fi` passed against the connected HTTPS workspace:

- real PR cards and an independently connected browser SSE stream;
- a PR inspector with exact head, current changed files, checks and source/coverage details;
- a named **local QA pause**, persisted across reload;
- independent browser receipt of the corresponding `decision` event, including the expected PR number, monotonically increasing sequence and `baseline=false`;
- downloaded Markdown containing the same full head, reviewer note and explicit local-only scope;
- 390px Release Room and evidence drawer layouts without horizontal overflow;
- no JavaScript page or console errors.

A subsequent read-only public browser pass additionally verified the repository-derived official watches, research receipts and Web Watch layout. Artifacts include:

- `docs/screenshots/release-room.png`
- `docs/screenshots/release-evidence.png`
- `docs/screenshots/release-decision.png`
- `docs/screenshots/release-mobile.png`
- `docs/screenshots/web-watch.png`
- `docs/screenshots/release-decision.md`

The pause is explicitly attributed to `DriftCI browser QA`, with a note that no GitHub review, merge or deployment occurred. It is not a statement by a repository maintainer.

## Isolated browser workflows

The legacy seven-workflow browser suite passed with zero JavaScript errors:

1. labelled offline Mission Control state;
2. source-to-code evidence and persisted human review;
3. offline-empty watch state without fabricated sources or research;
4. searchable change inbox with no patch-generation actions;
5. CVE evidence, response checklist, IR export and history;
6. explicit partial-source/OSV coverage and the 120-file source bound;
7. 390px Mission Control and Web Watch layouts without overflow.

`DRIFTCI_QA_SCRIPT=browser-smoke.cjs scripts/browser-smoke-docker.sh` always starts a temporary offline backend with a new SQLite database. Its reset/replay actions and browser-injected large-repository coverage fixture cannot replace the public connected workspace. The real source-watch/research checks belong to the public Release Room QA instead of manufacturing watches in offline mode.

The coverage fixture is a UI fixture. It does not imply a second real repository was indexed. Measured large-repository behavior comes from `vercel/ai`, the source-reader tests and the API source-coverage record.

## Server and polling tests

`make test` completed the production frontend build and **48 backend tests**, with one existing Starlette/httpx deprecation warning. Frontend TypeScript/Vite build passed. Python compilation, shell syntax and both Node browser-script syntax checks passed.

The regression suite includes:

- **Webhook verification and control:** HMAC-SHA256, delivery deduplication, repository validation, body limits and replayable SSE.
- **Baseline separation:** first PR imports and retained lifecycle findings do not become fake later activity.
- **Exact-head evidence:** PR head changes, external observation changes and check-run updates expire local decisions.
- **Current diff matching:** removed lines and deleted files cannot match a current model identifier.
- **Evidence fingerprint boundaries:** acknowledging a signal or resolving it does not invent a new external fact and therefore does not expire a decision by itself.
- **Check reconciliation:** running checks are re-read at an unchanged head; completion updates the event/evidence state.
- **Readiness guards:** partial detail, oversized diffs, pending/failing CI and stale GitHub evidence block ready. Holds remain available for a documented limitation.
- **Human workflow:** reviewer records survive reload, export the same head/evidence hash and remain distinct from GitHub approvals.
- **Coverage accounting:** 30-file and 12,000-character patch bounds survive polling without needless re-downloads; request failures remain retryable.
- **Rate-limit handling:** header-based reset, missing-header quota fallback, persisted retry windows, request suppression and a regression against stale local health overwriting the server’s retry state.
- **Provider-status normalization and relevance mapping:** a changed relevant provider state can invalidate a matching release; an unrelated provider does not.
- **Source selection:** prioritized manifests/runtime integration files, bounded large-tree reads and test/fixture/snapshot exclusions.
- **Context.dev controls:** cache behavior, pacing, research-host filtering, exact credit reservation and budget denial.

## Controlled status transition test

The mocked status-watch test uses an unchanged PR with completed checks and an existing local decision. It first establishes a fresh GitHub retrieval baseline and an OpenAI “Operational” snapshot through the controlled Context.dev fixture. A degraded-status snapshot with an elevated-error incident then creates an external observation and expires the local decision. This tests genuine normalization, matching and invalidation logic without falsely claiming that OpenAI degraded during a public demonstration.

## Current limitations

- Verification proves this prototype and its observable API behavior, not universal correctness under all GitHub or provider payloads.
- The public application is a single-workspace demonstration with anonymous local reviewer names. It has the authentication, audit-integrity and tenancy limitations described in `THREAT_MODEL.md`.
- GitHub checks are observed results. DriftCI did not run the application’s test suite, merge a branch or deploy an application.
- Selective source coverage, first-page PR detail, omitted patches and dependency query bounds mean absence is not proof of safety.
- Exact source identifiers are not production runtime call-site evidence, especially in SDK catalogs.
- No Context.dev monitor resources, IDs, remote schedules, monitor-side run history or monitor webhooks are claimed. The optional GitHub webhook is separate.
- The source does not currently contain the verbatim challenge brief or an authoritative account-side Context.dev usage statement.
