# DriftCI evidence and validation

These are measured prototype results with explicit coverage boundaries. Live repository, CI and monitor facts can change; the timestamps and exact commits below identify each measurement. No result here is a production-safety audit or an application-exploitability claim.

## Current public workspace

**https://driftci.ajc.contexio.fi** serves the public **`nodejs/node`** workspace at commit **`c07db8c5c1b1b18e1e0e088b83f56922c142c0cf`**. It uses GitHub structured metadata, dependency-graph data and selective immutable raw reads. No repository archive, clone, install, import or repository-code execution is used.

| Evidence | Observed value |
|---|---:|
| GitHub tree entries | 56,696, not truncated |
| Selected text-file records | 1,600 |
| Bytes read | 20,521,906 |
| Discovered manifests read | 525 / 525 |
| Native-version files read | 67 |
| Dependency-graph package versions | 753 |
| Parsed dependency records | 7,082 |
| Invalid test-fixture manifests reported | 5 |
| Oversized files | 1 |
| Failed / timed-out reads | 0 / 0 |
| Budget-skipped wider-source files | 44,730 |
| Wider-source coverage complete | No |
| Archive downloaded | No |

All discovered manifest candidates were read; five invalid fixtures still mean `dependency_manifest_complete=false`. The oversized `deps/simdjson/simdjson.h` declaration requires a separate review path under the 2 MB file cap. Real native declarations include brotli, c-ares, libuv, nghttp2, nghttp3, ngtcp2, zlib and generated OpenSSL declarations. They remain platform-specific native evidence rather than registry-version assertions.

The expanded scanner covers application/package manifests, lockfiles, bundled dependencies, monorepo packages, examples, tests, documentation, dependency-graph records and native declarations with scope labels. `production_models` is empty for this Node snapshot: bare `o1`–`o5` FFI variables are not treated as configured model identifiers.

## Vulnerability results

The current public state was reconciled after the scoped-incident implementation was deployed:

| Measurement | Result |
|---|---:|
| Supported exact registry comparisons | 5,581 eligible; 5,581 checked; 0 pending |
| Full advisory details | 157 requested; 157 retrieved; 0 pending |
| Unresolved declarations retained | 1,437 |
| Native/project/unsupported comparisons excluded from unrelated registries | 64 |
| Persisted package/version/manifest findings | 206 |
| Unique CVEs among those findings | 98 |
| Bundled scope | 204 findings |
| Dependency-graph scope | 2 findings |
| Application scope | 0 findings |
| Findings with their evidence manifest | 206 |
| Correlation with the retrieved CISA KEV catalogue | 0 |

The 206 findings are occurrences, not 206 distinct vulnerabilities or production exploits. Examples originate in V8 fuzzing/Turbolizer tooling, libuv documentation requirements and vendored crates. An advisory range match proves the recorded package-version relationship. It does not prove application execution, reachable vulnerable behavior or deployment exposure.

One exact-version OSV query can produce multiple manifest occurrences. Every occurrence retains scope and manifest through the finding, incident, UI and Markdown export. Only application manifests are eligible for direct deterministic patches; bundled, test, example, dependency-graph and other non-application records must be handled through their owning workflows.

## Latency measurements

These measurements are separate. They are not combined into a synthetic cold result.

| Run | Construction and cache state | Result |
|---|---|---:|
| Fresh isolated Node `service.connect()` | New SQLite DB; real production service/HTTP client/settings construction; no GitHub token; Context.dev metadata transport; targeted raw reads; live documentation/search, OSV/CISA, release index and existing remote monitor reconciliation | **80.384 seconds** |
| Earlier deployed Node refresh | Actual application process with warm repository/advisory cache | **54.895883 seconds** |
| Public incident-scope reconciliation | `POST /api/scan` on the retained public Node workspace, cached repository/advisory data | **24.799 seconds** |

**The approximate cold-under-60 target was not achieved.** The completed fresh service measurement was:

- `github_metadata_and_selective_reads`: **37.393 seconds**;
- narrower raw selective-source phase (`source_read_seconds`): **18.271 seconds**;
- documentation/search phase: **36.485 seconds**;
- OSV/CISA phase: **21.861 seconds**, overlapping other post-read phases;
- lightweight release index: **2.347 seconds**;
- remote monitor reconciliation: **2.596 seconds**.

The repository/connect API has a 90-second deadline. The fresh harness called `service.connect()` directly to measure its real orchestration; it did not measure an outer HTTP request and should not be cited as an HTTP-under-60 proof. The public warm/reconciliation timings are real application HTTP operations against retained state.

The keep-alive pace is deliberate: ordinary Context.dev requests retain the configured **6.2-second guard**. Repeated repository inventory work is now snapshot-cached on exact file content and relevant metadata. On the retained 1,600-file snapshot, repeated inventory calls fell from approximately **3.0 seconds to 0.03 seconds**, and document selection fell from **4.375 to 1.262 seconds**. Advisory issue counts remain current overlays, and returned dictionaries cannot mutate the cached rows.

A retained-cache continuation that still had 83 package queries and 93 advisory details pending is not counted as a completed cold run. An earlier GitHub-rate-limit abort and an array-envelope failure are also excluded from successful timings. No archive-based timing is claimed for the current implementation.

## Context.dev transport and monitoring

The implementation has a real Context.dev metadata transport for public, credential-free `api.github.com` JSON. It preserves bytes, validates base64/body limits/content type/JSON shape, and exposes direct-GitHub fallback errors. The fresh Node run recorded **10 measured ordinary credits across nine requests**, locally measured in its own database; these measurements include Context.dev GitHub metadata retrieval, the three relevant package-release pages and one scoped search. That isolated search returned five legitimate research results.

Before the ceiling change, the public workspace had retained **60 ordinary daily credits** of prior use. Its hourly Context.dev monitor has a **48-credit/day commitment**. The combined 108 committed credits exceeded the then-configured 80-credit default because earlier ordinary usage predated combined monitor accounting. That state was retained and explicitly explained in Web Watch rather than reset or hidden. The existing schedule was retained; additional ordinary requests and new hosted schedules were blocked at that time.

On 2026-11-15 the operator explicitly raised the configured application ceiling to **10,000 credits/day** so public users can run bounded live web work. The cache, 6.2-second pacing, ledger and monitor remain intact. This is local accounting, not an authoritative account-side billing statement; the overcommitment warning still applies if future commitments exceed the configured ceiling.

The deployed public API and browser both verified the 10,000-credit ceiling and 9,892 available credits at that check, with the historical 60 ordinary plus 48 monitor commitment unchanged. The served HTML matched the rebuilt production frontend and carries `Cache-Control: no-cache`. The final public coverage run checked credit arithmetic, preserved monitor/run identity, and recorded no browser mutations or JavaScript errors (`/tmp/driftci-final-10000-coverage.log`). The final Release Room pass covered incomplete current-head detail and disabled ready (`/tmp/driftci-final-10000-release.log`). Seven isolated legacy workflows also passed against a fresh offline database (`/tmp/driftci-final-legacy.log`; its initial curl probes occur before the temporary server is ready and are followed by a successful report).

The public incident reconciliation did not increase ordinary Context.dev request/credit counts: **55 queries / 60 daily ordinary credits** remained unchanged. Two additional credits observed afterward belonged to a genuine scheduled monitor run, not browser QA or an artificial visual assertion.

### Real remote monitor

- Monitor: **`mon_69e93e826b1f4d3993f6334286174703`**.
- Query: `site:nodejs.org/en/blog/vulnerability "Node.js"`.
- State: active, hourly, owned/tagged for this DriftCI Node workspace and reused rather than duplicated.
- Verified baseline: `run_c8b940f05b9743c99e760d59cf0ca822`.
- Earlier verified scheduled run: `run_dd91e816859d49ea9a1d19e92ac651dc`, 2026-11-15T05:58:15.950Z–05:58:23.700Z, two credits, no change.
- Independently reconciled following run: `run_05d7ed5ce9b748908cd8fbec8ca133f8`, 2026-11-15T06:58:13.663Z–06:58:19.288Z, two credits, no change.
- Latest run in the public browser verification: **`run_d35ba1012a29453591c5e087af4b35fe`**, 2026-11-15T07:58:11.304Z–07:58:15.411Z, scheduled/completed, two credits, `change_detected=false`.
- Next run reported by that reconciliation: 2026-11-15T08:57:50.649Z.
- Monitor accounting at that point: **8 spent / 40 reserved = 48 committed**.

These are real remotely scheduled records. Baselines and no-change runs do not create advisory incidents. No genuine hosted-monitor change has been observed, so none is presented or fabricated. Monitor citations are host-filtered and the returned text cannot authorize a patch. **Context.dev monitor webhooks are not implemented.** The optional HMAC-verified GitHub webhook is separate.

The current public optional research source has no retrieved results: its recorded error is `Optional repository research skipped: the daily scrape/search budget is reserved for active remote monitors.` The UI shows this exact budget state. The five-result isolated cold-run search is separate evidence and was not copied into public accounting or fabricated into the public UI.

## Current browser verification

### Public coverage, incident and monitor workflow

`coverage-smoke.cjs` passed against the real Node application with:

- canonical repository identity and no archive use;
- rendered manifest/native/source coverage, five parse-failure details and platform-specific native declarations;
- reconciled OSV eligibility/query/detail counters;
- all-scope incident selection, bundled scope and full evidence-manifest display;
- actual monitor ID, completed-run state, run credits, scheduling/reconciliation distinction and the absence of Context.dev monitor webhook ingestion;
- committed-credit arithmetic, current ceiling and overcommitment handling;
- 390px repository and monitor/budget layouts without overflow;
- zero JavaScript/page errors and **zero browser requests other than GET/HEAD/OPTIONS**.

The report is `/tmp/driftci-coverage-final-2.log`; its screenshots are under `/tmp/driftci-coverage-final-2/public/`. Current captures have been copied into `docs/screenshots/`.

### Public HTTPS Release Room

The final read-only `release-smoke.cjs` report returned `ok: true` for **https://driftci.ajc.contexio.fi**:

- real PR cards and a connected durable SSE stream;
- a persisted Node PR with current changed files and checks selected from actual `detail_complete`/`files_complete` data;
- empty index-only PR arrays remaining visibly incomplete;
- all repository-derived watch rows matching the source records;
- the actual research-budget skip when no results have been retrieved;
- 390px Release Room and evidence-drawer layouts with no horizontal overflow or JavaScript errors;
- no local decision, GitHub approval, PR mutation, merge or deployment during this pass.

Log for that complete-detail pass: `/tmp/driftci-release-current-final-5.log`. `DRIFTCI_RELEASE_DECISION_QA` was explicitly unset for this read-only pass.

Upstream PR heads then advanced while the GitHub quota retry window was active. The application cleared old-head detail, correctly leaving empty/incomplete records rather than showing stale files as current. A subsequent read-only pass opened that real pending state and verified that the decision dialog disabled **Record ready**. It also recorded no browser mutations and no JavaScript/overflow failures. Log: `/tmp/driftci-release-verified-final-2.log`; screenshots use `release-pending-evidence.png` for this state. This is evidence of the readiness guard, not a claim that all PRs had detailed files or passing CI at that moment.

### Isolated legacy browser suite

Seven workflows passed on the wrapper-created offline server and fresh SQLite database: labelled demo state, source evidence and persisted review, offline-empty watches, change-inbox filtering, CVE response/export/history, independent manifest/source misses and 390px layouts. Its coverage interception is an explicit **UI fixture**, not a claimed second real repository index. The log is `/tmp/driftci-legacy-current-final-2.log`.

### Earlier release evidence retained as history

The earlier Vercel/AI public exercise verified a genuine local QA hold received by an independent SSE connection, persisted across reload and exported as an exact-head Markdown receipt. A mocked status transition also proved that a relevant degraded-status observation invalidates a matching local decision. These are historical test evidence, not a real provider outage, a Node maintainer approval or a new web change today.

## Backend and build verification

- **67 backend tests passed**.
- Production TypeScript/Vite build passed.
- Python `compileall`, JavaScript syntax for all three browser workflows, shell syntax and `git diff --check` passed.
- The only backend test output besides passes is the existing Starlette/httpx `TestClient` deprecation warning.

Regression coverage includes selective manifests/native declarations, structured SQLite file records, exact snapshot cache invalidation and issue overlays, import-root usage counts, FFI/model ambiguity, source-success completeness, OSV full-detail/pagination/error/timeout accounting, duplicate manifest occurrences, application-only remediation, shared ordinary/monitor/in-flight credit accounting, real-monitor-shaped run deduplication/citation filtering/no automatic patching, index-only PR detail, stale-head invalidation, HMAC/SSE, scoped exports and transport fallbacks.

The checked-in tests prohibit archive/Codeload retrieval. Live public benchmarks used GitHub metadata and selective commit-pinned raw files instead. No GitHub credential was used to bypass a measured anonymous quota problem.

## Current limitations

- Cold `service.connect()` took 80.384 seconds; the approximate 60-second target remains unmet. Warm and cold timings must stay distinct.
- Wider-source coverage, native platform checks, unresolved declarations, the oversized native header and five invalid manifest fixtures remain review work.
- A dependency match, SDK identifier or import/reference count is not proof of invocation, exploitability, deployment or application CI execution.
- Public optional research is budget-limited and has no current results. Its real skip is shown rather than filled with fixture data.
- GitHub freshness can be stale during transport/quota failures. The Release Room exposes this and blocks ready while freshness/coverage/check requirements fail. A documented local hold remains possible.
- Initial imports are baselines. No genuine recent official-page diff or remote security-monitor alert is claimed.
- Local reviewer strings are not authenticated organizational identities. The public workspace is a single-workspace demonstration without tenant isolation or tamper-proof audit ownership.
- The older 120-file Vercel/AI reading and video/document captures are historical material from the earlier implementation. They are not current large-repository coverage or latency measurements.
- `SUBMISSION.md` is a local draft. The verbatim official challenge brief and authoritative platform submission state are not stored here; precise judging/compliance claims need verification.
