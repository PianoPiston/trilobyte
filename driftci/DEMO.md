# DriftCI demo guide

**Public demo:** https://driftci.ajc.contexio.fi

The public workspace connects **`vercel/ai`**, a real AI SDK monorepo. It reads public GitHub metadata and a selective 120-file source index. DriftCI is not a Vercel-operated approval system, and identifier matches in SDK catalogs do not establish production model invocation.

## The five-minute tour

1. **Start in Release Room.** Show recent pull requests, exact head commits, GitHub checks and the independent event-stream connection. Select a PR whose file/check coverage is complete.
2. **Inspect the release evidence.** Open **Inspect release**. The drawer contains the exact head, evidence hash, current files, checks, remote reviews and any matching external evidence. GitHub approvals and DriftCI local decisions are not the same thing.
3. **Go to Web Watch.** Show the repository-derived official sources, persistent baselines, local Context.dev credit ceiling and scoped research. Ordinary pages use a six-hour cache; provider status watches accelerate only during defined release activity.
4. **Inspect source-to-code evidence.** In Change Inbox or Workspace, inspect a model lifecycle or vulnerability record. Follow the primary receipt and code locations. Explain the difference between a source identifier, a supported SDK API definition and a runtime invocation.
5. **Record a local decision.** Return to the PR inspector, select **Record decision**, supply a named reviewer and evidence notes, then record ready or hold. Ready requires a fresh GitHub source and complete bounded coverage. A pause can deliberately preserve a limitation.
6. **Observe the event without reloading.** The new decision appears in the live event memory and updates the PR card. Explain that the same channel carries later commit, review, CI and external-web observations.
7. **Export the receipt.** Select **Export decision**. The Markdown file includes the exact head, source/evidence fingerprints, checks, files, owner, note and residual limitations. A later head, external change or check-run update can expire that decision.
8. **Show the supporting incident workflow.** Vulnerabilities combines OSV/CISA evidence with repository reachability clues, an ordered response checklist, retained history and a Markdown IR record. Heuristics do not prove exploitability.

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

Describe polling accurately as DriftCI-local polling. Do not claim a Context.dev monitor resource, ID, webhook or remote run history.

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

- `vercel/ai`: public selective index, currently 120 files at a pinned main-branch commit. Large monorepo coverage is partial.
- `junction/orders-ai`: deliberately outdated example, useful for compact OpenAI/Next.js evidence. The historical replay is explicitly labelled.
- **Repository → demo controls** switches the workspace. `POST /api/demo/reset` clears the current workspace’s release records and signals, so do not run destructive QA against the public Release Room when preparing a recording.
- Context.dev scrape/search is locally accounted; quota values are not account-side billing reconciliation. Current API health shows usage and remaining local credit capacity.
- Anonymous GitHub API access can run out during a busy setup. If needed, use a read-only token and keep it outside source. The application keeps retained evidence visible and reports freshness instead of faking an update.

For exact limits and endpoints, see `README.md` and `PRODUCT.md`. For measured results, see `EVIDENCE.md`.
