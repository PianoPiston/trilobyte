# Orders AI — intentionally outdated DriftCI fixture

A small Next.js support-operations application used to demonstrate DriftCI. **Do not deploy this fixture.** It intentionally contains an old Next.js release and retired model identifiers so dependency-to-source impact analysis has something meaningful to find.

Production-like assets:

- Support summaries and escalation drafts select `gpt-4-0314`.
- Priority triage selects `o1-mini`.
- `middleware.ts` performs session gating for `/ops/*`, making middleware advisories relevant to review.
- `scripts/evaluate-models.mjs` documents the application-owned quality gate. DriftCI never executes it.

All remediation changes should be reviewed and tested in the application's real CI environment.
