# DriftCI — local submission draft

This is product copy, not confirmation of a finalized Junction platform entry. The verbatim official challenge brief, challenge identifier and authoritative platform submission state are not stored here.

## Name

**DriftCI**

## Punchline

**From repository inventory to accountable releases.**

## Short description

DriftCI turns a public repository into inspectable release and security evidence. It reads GitHub metadata, dependency-graph data and selected commit-pinned manifests/source—without an archive, clone or repository execution—then resolves dependency scope and checks exact supported versions against full OSV advisory records. Every package/version/manifest match keeps its source, scope and uncertainty through the incident UI and Markdown export.

Context.dev supplies official-web snapshots and scoped research, byte-preserving public GitHub metadata, and a genuine remotely scheduled hourly monitor. Its run and change records arrive beside GitHub PR heads, file diffs, reviews and CI in one durable event timeline. A named reviewer can record a local ready or hold decision for an exact head, external-evidence fingerprint and check-run state. DriftCI does not approve or merge GitHub PRs, deploy, or claim production safety.

## Challenge fit

**The web becomes an operational input to the repository.** Official dependency releases, model lifecycle facts, pricing and provider-status pages are compared over time through Context.dev. The hosted Node security monitor executes remotely every hour and produces identifiable run records, including baselines and no-change results. Local reconciliation preserves those facts and filters monitor citations.

This is not just retrieval. DriftCI connects source changes to exact repository evidence and an accountable local decision. A later head, check result or relevant official observation can make an earlier decision stale. Initial imports are baselines, and a failed or budget-skipped retrieval cannot masquerade as new evidence.

## Demonstrated repository scale and security scope

The public demo indexes **`nodejs/node`** at one immutable 56,696-file tree without downloading the project archive. It reads 1,600 text-file records, all 525 discovered manifest candidates, 67 native-version files and 753 dependency-graph package versions. Wider-source partiality, five invalid test fixtures, the oversized declaration file, unresolved ranges and native comparisons are explicit.

The public OSV phase checked **5,581/5,581 supported exact comparisons**, retrieved **157/157 full advisory details**, and persisted **206 package/version/manifest matches covering 98 unique CVEs**. Of those occurrences, **204 are bundled and two are dependency-graph evidence; zero are application-scope matches**. Tooling, test, documentation and bundled dependency findings are useful inventory work, not assertions of production exploitation. Native declarations remain native evidence and are never sent to unrelated package registries.

## Context.dev use that can be inspected

- **Web Scrape:** up to six repository-relevant official pages per refresh, with bounded normalized snapshots, hashes and subsequent added/removed excerpts.
- **Web Search:** one scoped query returning at most five host-validated research results when ordinary budget is available. A public budget skip is displayed as such rather than replaced with fixture results.
- **Byte-preserving repository metadata:** validated public `api.github.com` JSON for repository/ref/tree/SBOM and bounded PR reads. Raw repository source is never sent to Context.dev. Direct GitHub fallback and transport failures remain visible.
- **Remote monitoring:** active hourly monitor `mon_69e93e826b1f4d3993f6334286174703`, reused rather than duplicated. Its real baseline and scheduled no-change completions are visible with run IDs, timestamps and charged credits.
- **Resource accounting:** six-hour ordinary caches, 6.2-second pacing, a 10,000-credit daily default and a 48-credit daily hosted-monitor reservation. Settled ordinary use, monitor commitments and in-flight reservations share the availability calculation.

Context.dev monitor webhooks are not implemented. An optional HMAC-verified GitHub webhook is a different integration. Local 15-minute polling, remote hourly scheduling and local reconciliation are distinguished throughout the UI.

## Release workflow and innovation

**Repository history matters as well as the latest diff.** The targeted inventory includes old application code, unused/stale model references and nested/bundled dependencies, while current PR matching is restricted to added/context lines at an exact head. Index-only PR metadata stays empty and incomplete until bounded file/review/check evidence arrives.

The evidence fingerprint binds relevant official observations, source fingerprints, mapped paths and CI state to one local release decision. A human review flag alone does not pretend to change an external fact. Real GitHub reviews remain separate from local DriftCI decisions. Every receipt carries exact head/evidence hashes, checks, source locations and residual coverage gaps.

Security findings follow their ownership boundary. Only application manifests can receive direct deterministic vulnerability patches; bundled/test/dependency-graph findings are routed to the owning component/workflow. There is no speculative patch-generation UI.

## Measured implementation

- Durable SQLite-sequenced events, replayable SSE, independent GitHub freshness and pending evidence handling.
- Exact PR heads, bounded changed files/reviews/checks, local named decisions and Markdown release records.
- Targeted multi-ecosystem and native inventory with source/parser/OSV coverage reported separately.
- Snapshot-keyed inventory reuse: approximately 3.0 seconds → 0.03 seconds for repeated processing of the retained Node snapshot; current issue overlays remain independent.
- A completed fresh isolated `service.connect()` measurement of **80.384 seconds**. The approximate cold-under-60 target is unmet and this is disclosed, along with the 37.393-second metadata/selective-read phase and 36.485-second documentation phase.
- An actual public cached incident reconciliation of **24.799 seconds**, with ordinary Context.dev request/credit counts unchanged. An earlier 54.896-second warm refresh is recorded separately.
- **67 backend tests**, production TypeScript/Vite build, Python/JavaScript/shell checks, public HTTPS Release Room QA, public coverage/incident/monitor QA and seven isolated legacy browser workflows.
- Real read-only public browser checks, including incident scope/manifest, native declarations, advisory counters, genuine remote-run identity and mobile layouts. The coverage workflow rejects browser mutations.

See `EVIDENCE.md` for exact measurements, coverage gaps and which results are live, warm, cold, cached, partial or historical.

## Technologies

Context.dev Web Scrape/Search and Monitors APIs; Context.dev byte transport for public GitHub metadata; GitHub REST, tree/dependency-graph and immutable raw APIs; FastAPI, Python, SQLite and httpx; OSV and CISA KEV; React, TypeScript, Vite and Inter.

## Live demo

**https://driftci.ajc.contexio.fi**

The current public workspace belongs to Node.js upstream; its maintainers do not operate DriftCI. Local reviewer names and QA holds are not maintainer approvals. The small `junction/orders-ai` example and historical OpenAI retirement replay are explicitly separate from current live evidence.

## Claims that must remain qualified

- Hosted monitoring and real run reconciliation are implemented; Context.dev monitor webhooks are not.
- Baselines and no-change runs are not new alerts. No genuine hosted-monitor change is claimed.
- A match against full advisory ranges is not application reachability or deployment exploitability.
- `5,581/5,581` covers supported exact registry comparisons, including unresolved/native review gaps visible beside it. It is not a claim that every repository file or component is safe.
- All discovered manifests read is not the same as successful parsing or complete wider-source coverage.
- GitHub CI is observed, not executed by DriftCI. Anonymous local reviewer names are not organizational authorization.
- Public ordinary credits were spent before combined monitor accounting was introduced, temporarily exceeding the earlier 80-credit default. The ledger and monitor were preserved. On 2026-11-15 the operator raised the configured ceiling to 10,000 credits to permit bounded live web work in the public demo. Local accounting is not account-side billing reconciliation; the overcommitment warning remains available whenever commitments exceed the configured ceiling.
- The cold 80.384-second result is not presented as cold-under-60 success.
- Exact final platform submission/compliance must be verified against the official brief rather than inferred from this draft.
