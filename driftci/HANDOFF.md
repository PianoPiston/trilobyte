# DriftCI — current handoff

Read this first. DriftCI is a **Release Room** for connecting exact GitHub PR/CI evidence to official-web intelligence from Context.dev. It also builds a targeted, dependency-scoped repository inventory and turns OSV/CISA matches into reviewable incident records.

## Public state

- **https://driftci.ajc.contexio.fi**, service `driftci-app`, backend `127.0.0.1:8100`.
- Connected workspace: **`nodejs/node`**, pinned to `c07db8c5c1b1b18e1e0e088b83f56922c142c0cf`. No archive, clone, install or repository-code execution is used.
- The deployed selective index contains **1,600 records / 20,521,906 bytes**, all **525 discovered manifest candidates**, **67 native-version files** and **753 dependency-graph package versions**. The complete tree contains 56,696 entries and is not truncated; broader source coverage remains partial.
- Five invalid test-fixture `package.json` files, one oversized file, budget-skipped source files, unresolved declarations and unsupported native comparisons are explicit. Read manifests are not the same as successfully parsed manifests.
- The deployed OSV pass checked **5,581/5,581** supported exact package-version comparisons, retrieved **157/157** full advisory details and persisted **206 package/manifest matches**. They cover 98 unique CVEs: **204 bundled** and **two dependency-graph** findings. These are not 206 production exploits. There are no application-scope findings in this workspace.
- The retained public GitHub workspace must not be replaced merely to make a browser fixture pass. The compact `junction/orders-ai` example is separate and deliberately outdated. Update this document after any deliberate workspace replacement.
- Node.js maintainers do not operate DriftCI. Existing local QA decisions are not maintainer approvals, GitHub reviews, merges or deployments.

## Repository analysis

`server/repository.py` resolves a canonical public repository to an immutable commit, reads its tree and dependency graph, and selectively reads manifests, native declarations and remaining relevant source for each phase. Root manifests, lockfiles, monorepo packages, tests, examples, documentation and bundled dependencies are inventoried with scope labels. Test/vendor paths do not become application-runtime model evidence.

- Defaults: **1,600 files, 32 MB total, 2 MB per file, 40 source-read seconds**, with connection-level deadlines and bounded raw-read concurrency. Capacity reservations are based on actual consumption; manifest/native reads share the remaining source budget without being deducted twice.
- `source_complete` compares eligible tree paths with successfully read content and also requires a complete tree. A placeholder for an oversized or failed read is not read content.
- `server/scanner.py` covers npm, Python, Rust, Go, Ruby, PHP, Dart, Gradle/Maven, NuGet, GitHub Actions, dependency-graph and native declarations. Exact locks, declared ranges, graph versions, project versions and native macros remain different evidence types.
- Inventory memoization is keyed by exact file contents and relevant metadata. Returned dependency dictionaries are copied, and current advisory counts are overlaid after the shared parse rather than frozen into the snapshot.
- Usage counts identify referencing files. npm deep imports and Python module roots are normalized. Bare `o1`–`o5` FFI variables do not become configured-model evidence.
- Native declarations remain native evidence; they are never sent to unrelated registries. Unresolved ranges remain visible and are not converted into exact versions.

## Vulnerability evidence and scope

`server/intel.py` uses OSV batches for exact supported registry versions, then retrieves full `/v1/vulns/{id}` records for range verification. Batch `{id, modified}` descriptors alone do not establish a finding. Pagination, detail failures, timeouts and skipped package comparisons leave package queries pending. Full advisory details are cached independently; a stale error does not contaminate a later successful detail.

One exact-version query fans verified results out to every manifest occurrence. `dependency_scope` and `manifest` follow the finding, incident, UI and Markdown export. A range match proves an advisory-version relationship, not application execution, reachability or deployment exploitability. CISA KEV correlation is reported separately.

Only application manifests may receive a direct deterministic vulnerability patch. Bundled, dependency-graph, test, example and metadata records require their owning component/workflow. The hidden compatibility patch API enforces this boundary; there is no patch-generation UI.

## Context.dev integration

- Up to six relevant official pages derive from repository package/model evidence. Scoped search returns at most five results. Ordinary documents use a six-hour cache and the configured 6.2-second pacing guard.
- Public, credential-free `api.github.com` repository/tree/ref/SBOM documents can be retrieved through Context.dev's **byte-preserving** metadata transport. Base64 bodies, size, JSON type and GitHub error envelopes are validated. Four such metadata reads were used for the deployed Node scan. These measured metadata reads consume ordinary Context.dev credits; direct GitHub/raw, OSV and CISA requests do not intrinsically consume them.
- Selective raw source files remain direct read-only content fetches pinned to commit SHAs. Repository archives are prohibited. Source contents are never sent to Context.dev.
- Direct GitHub retrieval remains a visible fallback. Metadata transport, last retrieval and fallback errors are reported. GitHub authorization is never sent through Context.dev or to raw-content hosts.
- **A genuine remote hourly monitor exists:** `mon_69e93e826b1f4d3993f6334286174703`, with `driftci`, `nodejs-node` and `driftci-repo:nodejs-node` tags. It is reused rather than duplicated.
- Verified records include baseline `run_c8b940f05b9743c99e760d59cf0ca822` and completed scheduled run `run_dd91e816859d49ea9a1d19e92ac651dc` (2026-11-15T05:58:15.950Z–05:58:23.700Z, two credits, no change). These are not vulnerability alerts. Check current API state for later runs.
- Local reconciliation reads real monitor/run/change records. A baseline, no-change run, failure or skip never creates an incident. Monitor text is untrusted evidence and cannot authorize a patch.
- **Context.dev monitor webhooks are not implemented.** The optional HMAC-verified GitHub webhook is separate.

## Budgets

Ordinary Context.dev work has a **10,000-credit daily default**. Hosted hourly monitoring is budgeted at **48 credits/day**. Settled scrape/search usage, monitor spent/reserved credits and ordinary in-flight reservations all reduce local availability; reservations are released in `finally` paths. Cache hits consume no new Context.dev request.

This is local accounting, not an authoritative provider billing statement. The operator raised the demo ceiling from 80 to 10,000 credits on 2026-11-15 so public users can run bounded live web work. Preserve the ledger, cache and pacing; do not reset the public store or spend credits merely to obtain screenshots. Optional research reports a visible skip if budget is unavailable.

## Release Room

- Public recent-PR indexing, exact heads, bounded files/reviews/checks and independent GitHub freshness. Initial repository connect uses `detail_limit=0`; detailed evidence remains incomplete until a bounded refresh retrieves it. A changed head clears old-head detail.
- SQLite sequenced events, deduplication and replayable `/api/events/stream` with numeric cursors/`Last-Event-ID`.
- Optional HMAC GitHub webhook; polling remains the fallback.
- Evidence matching on added/context diff lines and non-deleted paths. The base-branch source inventory is separate from each PR's bounded head diff.
- Local named `ready`/`hold` decisions bound to head, evidence fingerprint and CI snapshot. Later relevant evidence, changed heads and CI changes expire readiness appropriately. Human review/resolve actions do not by themselves invalidate a decision.
- Fresh GitHub evidence, sufficiently complete detail and successful checks are required for ready. A documented hold can retain limitations. No GitHub approval, merge or deployment is performed.
- Exact-head Markdown receipts and status watching with 300-second normal/45-second hot TTLs.

## Verification delivered

- **67 backend tests** pass. Production TypeScript/Vite build, Python compilation, JavaScript syntax, shell syntax and diff whitespace checks have been run during this work.
- Isolated real Node scans exercised targeted source, the complete OSV pipeline and real Context.dev metadata/monitor records. Measurements are labelled cold, warm, continuation or partial in `EVIDENCE.md`; they must not be combined into a stronger claim.
- The public deployed refresh measured **54.896 seconds warm**, with cached source reads. It is not cold-connect proof.
- Public Chromium coverage QA checks rendered coverage, advisory accounting, native declarations, parse failures, mobile overflow, incident scope/manifest, hosted monitor identity and credit commitments. It rejects all browser methods other than GET/HEAD/OPTIONS.
- Existing Release Room QA verified independent SSE observations and a persisted local hold. Legacy destructive QA runs against a fresh offline server/database only.

## QA commands

```bash
# Read-only real connected-repository coverage/monitor/incident workflow.
DRIFTCI_QA_SCRIPT=coverage-smoke.cjs \
  DRIFTCI_QA_OUT=/tmp/driftci-coverage-final \
  DRIFTCI_REPOSITORY=nodejs-node \
  scripts/browser-smoke-docker.sh http://10.0.2.2:8100

# Read-only Release Room workflow by default.
DRIFTCI_QA_SCRIPT=release-smoke.cjs \
  scripts/browser-smoke-docker.sh https://driftci.ajc.contexio.fi

# Optional explicit local hold on a shared workspace; no GitHub mutation.
DRIFTCI_RELEASE_DECISION_QA=1 \
  DRIFTCI_QA_SCRIPT=release-smoke.cjs \
  scripts/browser-smoke-docker.sh http://10.0.2.2:8100

# Legacy reset/replay/review workflows: forced isolated database and server.
DRIFTCI_QA_SCRIPT=browser-smoke.cjs \
  DRIFTCI_QA_OUT=/tmp/driftci-legacy-final \
  scripts/browser-smoke-docker.sh
```

## Remaining work and boundaries

1. The validated fresh `service.connect()` result is **80.384 seconds**, so the approximate cold-under-60 target is unmet. A profiled/staged repository start would need to preserve both source completeness flags and the Context.dev pacing controls; do not disguise warm, partial or continued state as cold.
2. Reconciliation persisted scope/manifest on all **206 public incidents**. Coverage/monitor/incident browser QA and public HTTPS read-only Release Room QA now pass, as do seven isolated legacy workflows. Ordinary public request/credit counts were unchanged by reconciliation.
3. A current targeted `vercel/ai` comparison was not rerun. Old 120-file measurements and older pitch captures are historical, not current evidence.
4. Public ordinary usage was already **60 credits** when combined accounting introduced the 48-credit existing-monitor commitment: 108 committed against the former 80-credit default. That historical ledger and the existing monitor were retained. The current default is 10,000 credits, so the workspace is no longer over its local ceiling; additional usage remains paced, cached and visible.
5. `SUBMISSION.md` and `EVIDENCE.md` are updated with measurements and boundaries. `SUBMISSION.md` remains a draft; exact platform compliance still requires the official brief. Current screenshots are in `docs/screenshots/`, and the old pitch video remains historical material.
6. Do not perform a writable PR demonstration without explicit authorization and suitable least-privilege credentials. No GitHub token is needed for the current public read-only workflow.
7. Production hardening remains: gateway authentication, per-tenant access control/budgets, authoritative private-data handling, tamper-evident audit ownership and application-owned CI validation. Free-form local reviewers are not production authorization.
8. Broader unselected source, native platform comparisons, parsed native headers over the byte cap and failed manifest reads remain review gaps, not proof of safety.

See `EVIDENCE.md` for measurements and proof boundaries, `DEMO.md` for the script, `THREAT_MODEL.md` for adversarial limits and root `AGENTS.md` for workspace-wide instructions. Keep DriftCI standalone and do not disturb Stoa or unrelated root-level work.
