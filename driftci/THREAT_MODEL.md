# DriftCI security model

DriftCI handles two highly untrusted inputs: public web content and source repositories. The prototype is deliberately designed around constrained parsing rather than agentic execution.

## Hard boundaries

- **No repository code execution.** The scanner only reads allowlisted text manifests and source extensions. It never runs package lifecycle scripts, project test commands, generated tools, or repository-provided executables.
- **Selective, bounded repository reads.** GitHub connections accept only canonical public `github.com/owner/repo` HTTPS URLs. The backend resolves a validated commit SHA, reads tree metadata at that commit, filters generated/vendor/media/documentation files and reads only allowlisted UTF-8 manifests/source/config text. Raw reads use the raw host at the same immutable commit. Separate selected-file, total-text-byte and per-file bounds apply regardless of repository size. It never downloads an archive or clone, so compression-bomb and filesystem path traversal are not part of this route.
- **Constrained network and coverage.** Only `api.github.com` and `raw.githubusercontent.com` repository endpoints are constructed. Redirects remain disabled, API credentials are sent only to `api.github.com`, and arbitrary repository URLs or local paths are refused. Individual malformed/unreadable files do not silently disappear: tree truncation, unreadable files and source-budget skips set partial coverage, shown in Mission Control and the repository drawer.
- **Official-source allowlists.** Live model signals come from configured official documentation sources. Other URLs are shown as evidence, not silently added as executable watchers.
- **Web text is data.** Context.dev responses are length-capped, treated as untrusted, and never evaluated or interpolated into shell commands. Remediation replacements are constrained identifiers/versions, not free-form instructions from a page.
- **Reachability is not exploit proof.** `confirmed` means exact source usage was found. `likely` identifies a relevant pattern such as authorization middleware. Exploitability still requires deployment-aware validation.
- **Targeted checks are labelled.** DriftCI reports static assertions actually run by its engine. It does not claim application tests, builds, exploit checks, or eval suites ran when they did not.
- **Human approval and protected integrity.** Patch generation is deterministic and reviewable. Export and GitHub PR creation are separate explicit actions. DriftCI never merges, pushes to the default branch, deploys, or auto-resolves incidents solely from web content.
- **Secret hygiene.** API keys come from environment variables, are never returned by the API or written to evidence receipts, and are excluded from logs. Repository scanner output should still be treated as sensitive and access controlled in a production deployment.

## Production follow-ups

Add organization SSO and role-based incident ownership, encrypted secrets and database storage, outbound network isolation, GitHub-app installation/private-repository support, incremental per-commit reindexing, exhaustive CI-based SBOMs for large monorepos, isolated CI runners for application-owned validation, immutable evidence-object storage, webhook signature validation, tenant isolation and audit-log export.
