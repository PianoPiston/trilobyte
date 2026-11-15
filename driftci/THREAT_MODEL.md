# DriftCI security model

DriftCI handles two untrusted inputs: public web content and source repositories. The prototype uses constrained parsing and bounded reads rather than agentic execution.

## Hard boundaries

- **No repository code execution.** The scanner reads allowlisted text manifests and source extensions. It never runs package lifecycle scripts, project tests, generated tools or repository-provided executables.
- **Selective, bounded repository reads.** Connections accept only canonical public `github.com/owner/repo` HTTPS URLs. The backend resolves and validates a commit SHA, reads tree metadata at that commit, filters generated/vendor/media/documentation/test files and fetches selected UTF-8 text from the raw host at the same commit. File-count, total-byte, per-file, concurrency and time bounds apply regardless of repository size. Redirects are disabled and GitHub credentials never go to the raw host.
- **Coverage is explicit.** Tree truncation, unreadable files and source-budget skips set partial coverage in Mission Control and the repository drawer. OSV package caps and timeouts are also shown. Missing evidence in an unread file or unchecked package is not treated as absence or safety.
- **Relevant official watches.** Model/package watches are selected from fixed built-in mappings. Custom watches require a public HTTPS URL, reject embedded credentials and local/private IP addresses, and are capped at 12. The URL goes to Context.dev; repository source contents do not.
- **Research host validation.** Scoped queries contain an official `site:` restriction and returned result hosts are checked again server-side. Off-host results are discarded.
- **Web text is data.** Context.dev responses are length-capped, sanitized and parsed as text. They are never evaluated or interpolated into shell commands. Research titles, highlights and diffs are separately excerpted.
- **Bounded observation storage.** Normalized snapshots are capped at 120 KB, each source retains at most 12 observations, and public API responses omit internal snapshot text. Observations are created only when a later normalized hash differs from the previous baseline.
- **Rate and credit controls.** Context.dev requests share a 6-hour cache, 6.2-second minimum interval, six-scrape/one-search refresh caps, a daily 80-credit default ceiling and pre-request credit reservation. Fresh cache remains available if the local budget is exhausted. The local ledger is not presented as authoritative account billing.
- **Reachability is not exploit proof.** `confirmed` means exact source configuration was found. `likely` identifies a relevant pattern such as authorization middleware. Exploitability still requires deployment-aware validation.
- **Human decisions persist.** Web signals support reviewed/monitoring/resolved states. Vulnerability resolution goes through an ordered incident checklist. Web content cannot resolve an incident by itself.
- **Secret hygiene.** API keys come from environment variables, never appear in API responses or evidence receipts, and are excluded from logs. Repository source is not sent to Context.dev. OSV receives only package ecosystem/name/version queries.
- **Polling claims are precise.** `watcher.enabled` refers to a local periodic task. DriftCI does not claim Context.dev monitor IDs, remote schedules or webhooks.

## Production follow-ups

Add organization SSO and role-based incident ownership, encrypted secrets and database storage, DNS-aware egress policy for custom watchers, per-tenant budget isolation, GitHub App/private-repository support, incremental per-commit indexing, exhaustive CI-based SBOMs, isolated application-owned validation, immutable evidence-object storage, tenant isolation and audit-log export.
