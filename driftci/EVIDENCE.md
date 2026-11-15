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

Reachability in the example is inferred only from relevant code patterns, with comment-only keyword occurrences ignored. It is not represented as exploit proof.
