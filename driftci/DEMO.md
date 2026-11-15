# DriftCI — 90-second live demo

## Opening (10 seconds)

> “Dependabot sees package versions. It misses the web pages that say your model is disappearing, your API is changing, or a new CVE now affects code you shipped. DriftCI turns those live changes into an evidence-backed response.”

Open **Mission Control** on the seeded `junction/orders-ai` workspace. Point out that risk counts and file evidence come from the repository inventory, not hardcoded cards.

## 1. Understand blast radius (20 seconds)

Select the **OpenAI `gpt-4-0314` retirement** signal.

- Show the official OpenAI deprecation receipt, announcement and shutdown dates, and the `historical replay` badge.
- Open both affected source locations: shared support-summary configuration and escalation-drafting call site.
- Say: “This is a documented historical event being replayed for a reproducible demo. Scan now retrieves the current official page through Context.dev.”

Generate the remediation. Show that DriftCI produces a real unified diff, lists targeted checks actually performed, and leaves application-owned model evaluations explicitly for CI.

## 2. Work a live security incident (30 seconds)

Open **Vulnerabilities** and select the Next.js middleware advisory.

- Show the OSV/GitHub advisory receipt, affected range, fixed version and CVSS where supplied by upstream.
- Explain that `likely reachable` comes from `middleware.ts` containing route authorization; it is not represented as exploit proof.
- Show the distinction between installed, usage-confirmed, and pattern-likely evidence.
- Advance the incident checklist from acknowledge through containment and patch preparation. The timeline records these actions.
- Click **Export IR record** to download a Markdown handoff containing impact, evidence uncertainty, checklist timestamps and primary advisories.

Use **Scan now** if network access is available. Live OSV/CISA results can reveal additional advisories; DriftCI keeps a failing source's last-known evidence rather than silently deleting it.

## 3. Turn evidence into a reviewable fix (20 seconds)

From the vulnerability signal, generate a patch.

- Inspect the version-only `package.json` diff and fixed-version evidence.
- Approve it, then export the patch. Without a GitHub token, the product says it is exporting a patch rather than pretending a PR was opened.
- If GitHub integration is configured, show the draft PR body: exact source citations, files changed, checks performed, and remaining human validation.

## Close (10 seconds)

> “DriftCI closes the gap between the live web and the code that depends on it: one change, a precise blast radius, a reviewable fix, and an incident record. Same workflow for model retirement, API drift, and CVE response.”

## Validated release

- FastAPI serves the built React console at https://driftci.ajc.contexio.fi through a public HTTPS proxy.
- Backend unit/integration tests run without live-network dependencies.
- `scripts/browser-smoke.cjs` has passed against both localhost and the public route with zero JavaScript errors: source drawer, two-file model patch, approval-gated download, CVE checklist/report, history and 390px mobile layout.
- A real first scan completed in 7.4 seconds with 2 Context.dev retrievals and live OSV/CISA results; details are in `EVIDENCE.md`.

## Demo recovery

- **Reset demo** restores the deterministic example workspace.
- **Replay historical incident** never masquerades as a new current event.
- **Patch export** works without credentials.
- Context.dev, OSV or CISA outages preserve cached evidence and surface source-specific errors.
- If time is short, prioritize the model-source-to-diff flow, then the CVE incident checklist.

## Questions judges may ask

**Why not Dependabot/Renovate?** They primarily react to package versions. DriftCI watches unstructured official documentation and operational model changes, maps them to source usage, and works security incidents with evidence. Package upgrade generation is intentionally one remediation type.

**Is a CVE in a dependency proof of exploitability?** No. DriftCI labels installed versus exact-use versus heuristic reachability, and directs teams to deployment-specific testing.

**Did DriftCI run my test suite?** No. It reports the targeted static checks it actually ran. The diff tells reviewers which application CI checks remain necessary.

**Can it merge automatically?** No. Human approval is required, and GitHub integration opens a separate branch and pull request only.
