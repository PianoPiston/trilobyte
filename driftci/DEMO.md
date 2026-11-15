# DriftCI demo guide

**Public demo:** https://driftci.ajc.contexio.fi

The public workspace connects **`nodejs/node`** at a pinned commit. It reads GitHub metadata, dependency-graph records and a targeted 1,600-file source index without an archive, clone or repository execution. DriftCI is not a Node.js-operated approval system. Its 206 scoped advisory matches are package/version/manifest evidence, mostly in bundled tooling, not 206 production exploits. Native declarations and unresolved/source/parser gaps remain visible.

## The five-minute tour

1. **Start in Release Room.** Show recent pull requests, exact head commits, GitHub checks and the independent event-stream connection. Select a PR whose file/check coverage is complete.
2. **Inspect the release evidence.** Open **Inspect release**. The drawer contains the exact head, evidence hash, current files, checks, remote reviews and any matching external evidence. GitHub approvals and DriftCI local decisions are not the same thing.
3. **Go to Web Watch.** Show repository-derived official sources, persistent baselines and the actual Context.dev remote monitor, including monitor/run IDs, hourly schedule, next run and completed no-change status. Explain the difference between the remote scheduler, local reconciliation and the app's 15-minute ordinary polling. The committed-budget card explains the retained 60 ordinary + 48 monitor commitments. Optional Node research was budget-skipped and has no retrieved results; show that explicit state rather than inventing results. Ordinary pages use a six-hour cache.
4. **Inspect scoped dependency evidence.** In Vulnerabilities, select a bundled or dependency-graph finding and open its source receipt and full evidence manifest. Explain that an exact advisory range match is not execution or deployment exploitability. Open Repository controls to show manifest/native/source coverage separately: 7,082 records, 5,581 supported exact queries, 157 full advisory details, five parse failures, unresolved declarations and partial wider-source coverage.
5. **Record a local decision.** Return to the PR inspector, select **Record decision**, supply a named reviewer and evidence notes, then record ready or hold. Ready requires a fresh GitHub source and complete bounded coverage. A pause can deliberately preserve a limitation.
6. **Observe the event without reloading.** The new decision appears in the live event memory and updates the PR card. Explain that the same channel carries later commit, review, CI and external-web observations.
7. **Export the receipt.** Select **Export decision**. The Markdown file includes the exact head, source/evidence fingerprints, checks, files, owner, note and residual limitations. A later head, external change or check-run update can expire that decision.
8. **Show ownership and residual limits.** Vulnerabilities combines OSV/CISA evidence with dependency scope, source manifests, an ordered response checklist, retained history and a Markdown IR record. Only application manifests can be patched directly. Bundled, test and dependency-graph findings belong to their owning workflows. Native comparisons and unresolved/unread files remain review gaps.

## Two-minute video outline

### 0:00–0:15 — two release timelines

Open Release Room with the PR queue and live event memory visible.

> “GitHub tells us what changed in the pull request. Official web pages tell us what changed around it. DriftCI places those timelines beside each other so review evidence has a freshness, a commit and an owner.”

Identify the real public repository and its bounded source coverage. Do not call the workspace production or imply endorsement by its maintainers.

### 0:15–0:40 — evidence at the exact head

Open a complete PR inspector. Point to the head SHA, changed files and check runs.

> “These are actual GitHub metadata and check results, not generated test results. File and patch bounds are explicit. Deleted code is not treated as current configuration, and incomplete evidence cannot be marked ready.”

### 0:40–1:05 — the external source

Open Web Watch and a relevant official-source receipt.

> “Context.dev retrieves the official model, pricing, release-note and status pages relevant to the code. DriftCI keeps their snapshots and diffs locally. The first page is a baseline, never an invented alert. Request pacing, caching and a credit ceiling are visible controls.”

Distinguish DriftCI-local polling from the real Context.dev hourly monitor and its remote run records. The UI exposes the genuine monitor and run IDs. Baselines and no-change completions are not alerts. Context.dev monitor webhooks are not implemented; the optional GitHub webhook is separate. Optional research is currently budget-skipped in the public Node workspace.

### 1:05–1:25 — one owner, one evidence set

Return to the inspector and open the decision dialog.

> “A named reviewer records ready or hold for this exact head, external evidence and check-run state. It is a local DriftCI record, not a GitHub approval or an automatic merge. A stale source or incomplete evidence requires a fresh review before ready.”

A pause may be recorded as a local QA example. Its note should explicitly say that no GitHub review, merge or deployment was performed.

### 1:25–2:00 — the record and the next change

Show the event arrive without a page reload, download the Markdown record, then briefly show Web Watch’s primary sources.

> “The exported record preserves the head, evidence fingerprints, CI snapshot, source links, owner and remaining limits. If the head, external facts or checks change later, that decision becomes stale. DriftCI keeps the evidence inspectable rather than generating an unexplained patch or claiming production safety.”

## Demonstrating genuine change

Only show a web or GitHub event as live when the corresponding source actually produced it. Existing model lifecycle matches can be historical baselines with `observed_at=null`; they are not proof that the page changed today.

- **GitHub activity:** verify the release health timestamp, then inspect the arrived event and its PR/head. Initial imports are baselines.
- **Official web changes:** use a fresh Context.dev observation with its before/after excerpt and source hashes. Do not turn an unchanged live retrieval into a change alert.
- **Review freshness:** show the observation time beside the latest retrieved GitHub approval. Do not call an old lifecycle page a newly observed change.
- **Decision expiry:** use a real head, check-run or external fact change. A mark-reviewed action alone does not invalidate an otherwise current decision.

The `Release paused locally` audit records created by the browser QA are explicitly identified as QA, not maintainer approvals. They demonstrate a local state transition over real SSE.

## Controlled fixtures versus the public demo

The pytest suite uses changing mocked Context.dev and GitHub responses to test transitions that cannot be scheduled safely on a public provider. Those tests are hermetic. They do not imply that a real external page changed during the public demonstration.

For a controlled writable pull-request workflow, obtain explicit authorization and an appropriately scoped GitHub token. Do not create reviews, merges, deployments or robot-authored approval records merely to make the demo look live. Read-only public polling and the small labelled historical replay are sufficient without those permissions.

## Repository and cost notes

- `nodejs/node`: 1,600 selective records at `c07db8c5c1b1b18e1e0e088b83f56922c142c0cf`; all 525 manifest candidates read, 67 native-version files, 753 graph packages and partial wider-source coverage. A fresh isolated `service.connect()` measured 80.384 seconds; do not present it as cold-under-60 or conflate warm timings.
- `junction/orders-ai`: deliberately outdated example, useful for compact OpenAI/Next.js evidence. The historical replay is explicitly labelled.
- **Repository → demo controls** switches the workspace. `POST /api/demo/reset` clears the current workspace’s release records and signals, so do not run destructive QA against the public Release Room when preparing a recording.
- Context.dev scrape/search is locally accounted; quota values are not account-side billing reconciliation. Current API health shows usage and remaining local credit capacity.
- Anonymous GitHub API access can run out during a busy setup. If needed, use a read-only token and keep it outside source. The application keeps retained evidence visible and reports freshness instead of faking an update.

For exact limits and endpoints, see `README.md` and `PRODUCT.md`. For measured results, see `EVIDENCE.md`.
