# DriftCI — current handoff

Read this first. DriftCI is now a **Release Room** connecting live GitHub PR/CI evidence to official-web intelligence from Context.dev. The earlier preserved code also provides source-to-code vulnerability evidence, response checklists and Markdown incident records.

## Public state

- **https://driftci.ajc.contexio.fi**, service `driftci-app`, backend `127.0.0.1:8100`.
- Connected workspace: **`vercel/ai`**, read-only public repository. At the last connection its pinned main-branch source index contained **120 files**, with partial coverage explicitly displayed.
- Firebase/Vercel maintainers and other repository authors do not operate DriftCI. The local QA hold is explicitly labelled and is not a GitHub approval.
- Current state is observable through `/api/health` and `/api/bootstrap`. Do not recycle old PR counts, check conclusions, source timestamps or error states without checking them.
- Keep `junction/orders-ai` as the compact historical example, separate from real observations. Do not replace the public connected workspace for generic visual QA.

## Completed Release Room behavior

- Public recent-PR ingestion with exact heads, bounded changed files, reviews and check-run snapshots.
- Monotonically sequenced SQLite events with deduplicated keys and replayable SSE. `Last-Event-ID` and `after=SEQ` both work.
- Optional HMAC-verified GitHub webhook with repository validation, delivery deduplication and downstream state reconciliation. Polling remains functional without it.
- Context.dev official lifecycle/pricing/release notes plus activity-scoped provider status. Ordinary documentation/search is not hot-polled.
- Evidence matching based on added/context diff lines and non-deleted paths. The base-branch source inventory is separate from each PR’s bounded head diff.
- Readiness states for incomplete detail, pending/failing checks, later external evidence and changed heads. Resolved findings remain history but no longer create active review work.
- Local named `ready`/`hold` decisions bound to a head, evidence fingerprint and check state. GitHub approval remains a distinct concept. Stale GitHub evidence blocks ready; a documented hold remains possible.
- Exact-head Markdown receipts with source fingerprints, CI snapshot, owner note and residual coverage limits.
- End-to-end Release Room, Web Watch and responsive frontend UI, with the Release Room as the default landing view.
- No visible patch-generation UI. The old backend remediation endpoints remain a separate compatibility surface and are not part of the Release Room workflow.

## Verification delivered

- **48 backend tests** and production frontend TypeScript/Vite build passed with `make test`.
- Public HTTPS Chromium verification passed for real PR metadata, changed files, checks and independently connected SSE.
- A local QA pause created a genuine browser-received SSE event, survived reload and exported an exact-head Markdown receipt. No GitHub write occurred.
- Public Web Watch showed the repository-derived official sources and research receipts.
- Seven legacy Chromium workflows passed on a **separate offline server and fresh SQLite database**, including review state, history, IR export, source-budget disclosure and mobile layouts.
- Server compilation, shell and Node script syntax checks passed.
- A measured anonymous-GitHub quota window was handled as stale retained evidence, with a later genuine recovery. Retry state cannot be overwritten by the stale health dictionary held by the refresh coroutine.
- A mocked Context.dev status transition proved status parsing and matching release-decision invalidation; no real provider outage is claimed.

See `EVIDENCE.md` for measurement timestamps, exact claim boundaries and screenshot paths. `DEMO.md` contains the two-minute script.

## QA isolation: important

The wrapper defaults to the read-only Release Room script:

```bash
DRIFTCI_QA_SCRIPT=release-smoke.cjs \
  scripts/browser-smoke-docker.sh https://driftci.ajc.contexio.fi
```

An explicitly enabled local pause is still a local record, never a GitHub mutation:

```bash
DRIFTCI_RELEASE_DECISION_QA=1 \
  DRIFTCI_QA_SCRIPT=release-smoke.cjs \
  scripts/browser-smoke-docker.sh https://driftci.ajc.contexio.fi
```

The legacy workflow always starts its own temporary server and database, even if the caller passed the public URL:

```bash
DRIFTCI_QA_OUT=/tmp/driftci-legacy-final \
  DRIFTCI_QA_SCRIPT=browser-smoke.cjs \
  scripts/browser-smoke-docker.sh
```

Do not run destructive reset/replay workflows directly against the connected workspace. `scripts/browser-smoke-docker.sh` takes at most one positional base URL and validates the selected script; do not reintroduce a default legacy script against arbitrary targets.

## Operating controls

- Ordinary Context.dev scrape/search uses six-hour caches, 6.2-second pacing, shared scan locks/cooldowns and a local **80-credit daily ceiling**. Reservation happens before a request.
- The 90-second release poller can read provider status with a **300-second normal TTL / 45-second hot TTL**. Hot mode applies only during defined PR activity. Ordinary documentation stays slow.
- Initial ordinary document snapshots are baselines, not alerts. No live change should be manufactured to improve the demo.
- A full ordinary web/OSV refresh runs every 15 minutes. PR ingestion does not rescan the source repository or force web research.
- GitHub uses persistent ETags, bounded recent-PR/detail windows and a stored retry window. Stable first-page/patch coverage limits are not redownloaded at each poll. Request failures and running checks still reconcile.
- `/api/events/stream` is durable event replay, not an in-process browser effect. The event ledger distinguishes baselines, live arrivals and local decisions.
- Context.dev counters are local request/credit counters. They are not account-side billing reconciliation.
- OSV/CISA and GitHub requests do not consume Context.dev credits.

## Repository evidence boundaries

The source inventory is a **base-branch pinned commit**. PR details are bounded snippets for the PR head, not a full new source index. SDK catalog model IDs indicate supported identifiers in selected code/config, not invocation of those models by a production service.

Source reads stop at 120 files / 4 MB total / 1 MB per file. PRs use at most 30 file patches with 12,000 characters each and up to 50 reviews/check runs. Missing or limited evidence remains partial; stable partial coverage is not hidden or called safe. Removed/deleted code does not count as current configuration.

The public app shows model lifecycle facts, citations, dependency evidence and check states without claiming to have run application CI, tested deployment safety or confirmed exploitability.

## Credentials and integrations

No GitHub token or webhook secret was needed for the final public demonstration. The anonymous rate-limit recovery is working, but a longer recording should use a least-privilege token if the operator supplies one through an authorized secret setup. Keep it outside Git repository files, with read-only contents, pull-request and checks permissions. Do not expose a personal token in the UI, chat or committed environment files.

To enable the optional webhook, a separately authorized deployment needs:

- `DRIFTCI_GITHUB_WEBHOOK_SECRET` set outside source;
- GitHub delivery to `POST https://driftci.ajc.contexio.fi/api/github/webhook`;
- content type `application/json`, HMAC-SHA256 and the supported PR/review/check events;
- successful GitHub delivery status and application health verified afterward.

Polling remains the fallback. A rejected webhook never becomes a synthetic event. This is a **GitHub webhook**, not a Context.dev monitor webhook. No Context.dev monitor resource/ID/remote schedule is claimed.

The public demo currently allows workspace replacement and free-form local reviewer names. Authentication, authorization and tamper-evident audit ownership are required before it controls a real organization’s releases. The fact that no GitHub write occurs in Release Room does not make anonymous local records authoritative.

Before any private repository or real organizational deployment, add gateway authentication, per-workspace access control and private-data handling. Add automated CI validation of the upstream application separately if required; DriftCI records observed CI state.

## What comes next, only when needed

1. **Obtain the exact challenge brief** before claiming precise platform compliance. `SUBMISSION.md` is a local draft, not a finalized platform entry.
2. **Record a genuine incoming web observation** if a suitable source changes. Use its actual before/after excerpt and retrieval time; do not substitute the historical replay.
3. **Use an authorized controlled repository** only if a writable end-to-end PR demonstration is specifically required. Read-only public PR polling already works and needs no token automation.
4. **Production hardening:** SSO/RBAC, separate per-tenant budgets and stores, immutable ownership/audit records, private-repository support, broader coverage and application-owned validation.
5. Preserve `vercel/ai` for the public connected demo unless deliberately preparing another scenario. Never reset it just to satisfy the legacy visual-test assumptions.

## Pitch assets

- `PITCH.md` contains the product positioning and short submission description.
- `pitch-video/` is a self-contained Remotion project with the narration script, generated audio, verified product captures and rebuild instructions.
- The rendered local video is `pitch-video/out/driftci-pitch.mp4`: 1920×1080, 30 fps, 103.47 seconds, H.264 + stereo AAC. Its conceptual motion graphics are separate from verified product captures; the exact-head QA hold remains explicitly local.

## Repository and unrelated work

Keep DriftCI standalone. Do not disturb Stoa, other Junction projects or root-level work that is not part of DriftCI. Source origin: `https://github.com/PianoPiston/trilobyte`; the code here is under `driftci/`. The current handoff accompanies the Release Room commit; the preceding checkpoint was `6c57e3c` (`Build Context.dev live web watches for DriftCI`).
