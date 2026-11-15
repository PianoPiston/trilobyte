# DriftCI security model

DriftCI handles two highly untrusted inputs: public web content and source repositories. The prototype is deliberately designed around constrained parsing rather than agentic execution.

## Hard boundaries

- **No repository code execution.** The scanner only reads allowlisted text manifests and source extensions. It never runs package lifecycle scripts, project test commands, generated tools, or repository-provided executables.
- **Bounded archives.** GitHub archive downloads require the GitHub host, limit bytes/files/path depth, reject traversal and symlinks, and discard common secret/build/vendor directories. GitHub credentials are sent only to `api.github.com`.
- **Official-source allowlists.** Live model signals come from configured official documentation sources. Other URLs are shown as evidence, not silently added as executable watchers.
- **Web text is data.** Context.dev responses are length-capped, treated as untrusted, and never evaluated or interpolated into shell commands. Remediation replacements are constrained identifiers/versions, not free-form instructions from a page.
- **Reachability is not exploit proof.** `confirmed` means exact source usage was found. `likely` identifies a relevant pattern such as authorization middleware. Exploitability still requires deployment-aware validation.
- **Targeted checks are labelled.** DriftCI reports static assertions actually run by its engine. It does not claim application tests, builds, exploit checks, or eval suites ran when they did not.
- **Human approval and protected integrity.** Patch generation is deterministic and reviewable. Export and GitHub PR creation are separate explicit actions. DriftCI never merges, pushes to the default branch, deploys, or auto-resolves incidents solely from web content.
- **Secret hygiene.** API keys come from environment variables, are never returned by the API or written to evidence receipts, and are excluded from logs. Repository scanner output should still be treated as sensitive and access controlled in a production deployment.

## Production follow-ups

Add organization SSO and role-based incident ownership, encrypted secrets and database storage, outbound network isolation, archive fuzzing, immutable evidence-object storage, webhook signature validation, tenant isolation, audit-log export, and isolated CI runners for application-owned validation.
