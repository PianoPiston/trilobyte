# Demo evidence verification

Checked against upstream sources on 2026-11-15.

| Demo item | Canonical source | Verified identity and remediation |
|---|---|---|
| OpenAI `gpt-4-0314` | https://developers.openai.com/api/docs/deprecations | Shutdown 2026-03-26; announced 2025-09-26; recommended replacement `gpt-5`, or `gpt-4.1` for latency-sensitive tasks |
| OpenAI `o1-mini` | https://developers.openai.com/api/docs/deprecations | Shutdown 2025-10-27; announced 2025-04-28; recommended replacement `o4-mini` |
| Next.js middleware bypass | https://osv.dev/vulnerability/GHSA-f82v-jwr5-mffw | Aliases include `CVE-2025-29927`; fixed releases include 12.3.5, 13.5.9, 14.2.25 and 15.2.3 |
| Next.js Server Actions SSRF history | https://osv.dev/vulnerability/GHSA-fr5h-rqp8-mj6g | Alias `CVE-2024-34351`; fixed in 14.1.1 |
| Known exploited enrichment | https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json | Live CISA catalog lookup; `CVE-2025-29927` was not listed when checked |

The initial workspace uses bundled historical snapshots so the demo is reproducible. **Scan now** replaces or augments them with current evidence. `next@14.2.3` belongs to many upstream advisory ranges; a live OSV run may therefore return substantially more issues than the focused seeded incident. This is expected, not an invented alert burst.

A direct Context.dev scrape of the OpenAI deprecations page returned a successful markdown representation during setup. Receipts must retain retrieval mode and timestamp; replay evidence must never be presented as current live retrieval.

## Measured release validation

2026-11-15 live service run against `examples/orders-ai`:

- First live scan: **7.4 seconds**, **2 Context.dev queries**, all four source health checks green (OpenAI, Anthropic, OSV, CISA).
- OSV: **37 deduplicated package-advisory matches** over the exact dependency inventory, with real fixed versions computed where available.
- After the live-document parser regression: **2 exact model signals** — `gpt-4-0314` (2 code/config locations) and `o1-mini` (1 location). Replacement-only models such as `gpt-4.1` and `o4-mini` were not incorrectly promoted.
- The later cached-source rescan retained retrieval provenance and produced the same intended model set. Latest dated lifecycle evidence was used for OpenAI's initial estimate followed by final shutdown.
- A second immediate manual scan received HTTP 429 from the shared public scan guard.
- API and Chromium workflow suites passed both through localhost and the public HTTPS deployment, including actual patch and Markdown incident-report downloads.

## Large-repository reader validation

GitHub connections no longer use Codeload/ZIP archives. Tree metadata and selected raw source files are both pinned to the resolved commit, and API tokens are not forwarded to the raw host. Nested npm/Python manifests retain distinct dependency scopes.

A real read-only probe of `microsoft/vscode` on 2026-11-15 resolved commit `776b518e720e780fb590f29872473f90bda9e079`. GitHub reported **1,758,894 KB** and the tree contained 21,443 files. With an intentionally small QA budget, DriftCI read **16 selected source files / 65,042 bytes**, consumed no archive and correctly marked coverage partial (GitHub tree not truncated; the source budget was the limit). This scans file evidence without cloning or downloading the repository; it does not claim exhaustive whole-repo coverage.

The browser suite includes the repository coverage view and partial-scan warning. Backend fixtures verify a mocked 90 MB repository, nested dependency manifests, absent Codeload calls, raw-host credential isolation, immutable commit requests and budget/partial accounting. Raw content is also streamed with a chunk-level per-file guard.

## Node-sized repository and blocking-request fix

After live Node-sized testing exposed an empty-scope bug and repeated source/indexing work, repository connections were changed to **64 files / 2 MB / 25 seconds of source reads**, with per-file and whole-connect deadlines. Test fixtures/documentation are excluded. Model evidence and import usage are each indexed once per source set; OSV performs bounded concurrent lookups (32 packages / 25 seconds by default) and exposes pending/package-budget coverage.

A temporary isolated `nodejs/node` connection at commit `e18f10645c3c02814ca04a9d798dd15c2f21ef6c` completed offline repository indexing in **5.19 seconds** (64/64 selected files read, 0 raw failures) and returned a second bootstrap in **0.104 seconds**. A separate live OSV/CISA connection completed in **9.92 seconds** without Context.dev in that probe: 189 scoped dependency records, 76 exact packages, **32 packages checked / 44 explicitly pending**, 10 findings, and a **0.114-second** follow-up bootstrap. These are partial scoped results, not a certification of every Node component. The deployed product's separately validated Context.dev retrieval was intentionally disabled in this probe to isolate repository and OSV/CISA behavior.

The complete **public Chromium + API flow** then connected `https://github.com/nodejs/node` successfully in **4.6 seconds** using the deployed live-configured/cached sources, with zero browser errors: 64/64 selected files, 1,916,532 bytes, 0 raw errors, 10 findings, and 32/76 packages checked (44 explicitly pending). It remained connected for the user to inspect rather than being reset to the fixture. This is the final production-route validation after the first live 9.92-second uncached probe.

Reachability in the example is inferred only from relevant code patterns, with comment-only keyword occurrences ignored. It is not represented as exploit proof.
