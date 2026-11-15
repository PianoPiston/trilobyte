# DriftCI — submission material

## Name

**DriftCI**

## Punchline

**Dependabot for the web your code depends on.**

Alternative: **Live dependency intelligence, from source change to reviewed fix.**

## Short description

Dependabot sees package versions. It misses the documentation pages that say your production model is disappearing, your API is changing, or your middleware now has a critical advisory. DriftCI watches the operational web with Context.dev, maps material changes to exact repository usage, and gives engineering teams an evidence-backed response: a reviewable patch, targeted checks, and a CVE incident timeline. It closes the gap between “something changed on the internet” and “we fixed the affected code.”

## Challenge fit

DriftCI is a product that reacts to the live web. Context.dev retrieves current official model/API documentation and preserves source provenance. OSV and CISA add live vulnerability and known-exploited intelligence. Repository analysis connects those external changes to internal assets, while remediation and incident workflows turn the signal into action.

## Technologies

Context.dev Web API, FastAPI, Python, SQLite, httpx, OSV, CISA Known Exploited Vulnerabilities, GitHub REST API, React, TypeScript, Vite.

## Innovation

Existing tools alert on versions. DriftCI treats official documentation and security intelligence as operational dependencies, builds a source-to-code blast radius, and carries uncertain evidence explicitly. Its UX combines change radar and incident response rather than producing another feed of alerts.

## Impact

A missed model retirement can silently break customer workflows; a missed middleware advisory can expose protected routes. DriftCI reduces the time from public disclosure to understood, assigned and reviewable remediation. Every decision includes its evidence and remaining validation steps.

## Implementation

The demo includes deterministic repository scanning, exact model/source matching, dependency inventories, OSV version resolution, CISA KEV enrichment, source receipts, live-source caching and failure handling, real unified patch generation, targeted static validation, persistent incident actions and optional GitHub PR creation. It never executes an untrusted repository or pretends application tests ran.

## Two-minute video outline

### 0:00–0:12 — the invisible dependency

Show code beside official documentation.

> “Your production stack depends on web pages, not just package versions. This model is disappearing. This middleware has a new advisory. None of that necessarily appears in your package manager.”

### 0:12–0:28 — connect code to the live web

Show DriftCI Mission Control and the repository inventory.

> “DriftCI uses Context.dev to watch official operational documentation, then maps material changes against the repository’s real dependencies and source files.”

### 0:28–0:55 — model retirement to reviewed patch

Open the `gpt-4-0314` signal, source receipt and two source locations. Generate the patch.

> “Here, OpenAI’s documented legacy snapshot retirement affects support summaries and escalation drafts. DriftCI finds both locations and creates a reviewable replacement patch—not a vague recommendation. Every diff carries its evidence and the exact targeted checks performed.”

### 0:55–1:25 — CVE incident response

Open Vulnerabilities and the Next.js middleware incident.

> “The same engine works when a vulnerability drops. OSV supplies affected ranges and fixes; CISA adds known-exploited intelligence. DriftCI finds authorization middleware in the repository and marks reachability as likely, not magically proven. The team can acknowledge, contain, patch, verify and resolve one persistent incident.”

### 1:25–1:45 — from alert to action

Approve, export or open a PR.

> “The result is a branch and reviewable pull request when GitHub is connected, or a real patch export when it is not. Application tests and model evaluations stay explicit, because DriftCI does not claim checks it never ran.”

### 1:45–2:00 — close

Return to Mission Control with resolved timeline.

> “DriftCI: live dependency intelligence, from source change to reviewed fix. Dependabot for the web your code depends on.”

## Demo claims to avoid

- Do not claim CVE reachability is proof of exploitability.
- Do not claim application CI or model evals ran; only DriftCI's listed targeted checks ran.
- Do not label historical replay as a newly announced live event.
- Do not claim a PR was opened when using patch-export mode.
- Do not claim Context.dev was used for OSV/CISA; those are separate public intelligence sources integrated into the same response workflow.
