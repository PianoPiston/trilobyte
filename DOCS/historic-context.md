# Historic drawings: per-drawing context files

Track 2 of the product. Historic drawings (habs, finna, europeana, wikimedia; 6,566 drawings) are hard to read without
outside knowledge: the labels are in old Swedish, Greek or Portuguese, and the sheet often does not say which building it
shows or where it is. For each drawing we build `context/<source>/<stem>.json` from the archive's own record plus a web
search. The VLM gets it as an extra prompt block.

## Files

| path | what |
|---|---|
| `context/<source>/<stem>.json` | one context file per drawing (`stem` = file name without extension; wikimedia `.svg` and `.jpg` share one) |
| `context/COVERAGE.md` | how many drawings got which field, plus context.dev credits used |
| `context/credits_log.jsonl` | ledger of every context.dev call (credits consumed and balance) |
| `context/_records/<source>.jsonl` | normalized archive records (intermediate) |
| `DATA/historic-raw/` | untrusted downloads: LICENSE.md tables, eval images, raw API/search cache (`cache/`), never fetched twice |
| `src/stoa/context/` | code (see the module docstring in `__init__.py`) |
| `results/samples/historic_eval.jsonl` | hand-labelled historic eval set (158 q, 57 drawings) |

## Context file schema (`historic-context/1`)

```json
{"schema": "historic-context/1", "source": "finna", "stem": "mfa.ca9d…", "files": ["data/finna/mfa.ca9d….jpg"],
 "licence": {"licence": "CC-BY-4.0", "credit": "…", "source_url": "https://finna.fi/Record/…", "from": "data/finna/LICENSE.md"},
 "record_ok": true,
 "fields": {"building": {"value": "Kirjailija Paul Remerin talo", "src": ["https://finna.fi/Record/…", "https://api.finna.fi/…"], "from": "record title (parsed)"},
            "place": {…}, "year": {"value": {"years": [1909], "text": "1909", "kind": "drawing/document date"}, …},
            "architect_or_author": {…}, "drawing_type": {"value": ["floor plan"], …}, "floor": {"value": [{"level": "basement", "phrase": "kellari"}]},
            "scale": {"value": ["1:200"]}, "language": {"value": {"code": "fi", "name": "Finnish", "note": "…"}},
            "key_terms": {"value": [{"term": "pohjapiirros", "lang": "fi", "en": "floor plan"}]}, "label_glossary": {…}, …},
 "summary": {"value": "Floor plan of …; dated 1909 …", …},
 "web": [{"title": "…", "url": "https://fi.wikipedia.org/…", "snippet": "≤500 chars", "relevance": "high", "licence_note": "…"}],
 "web_query": "…", "sources": ["every URL used"], "trust": "…"}
```

Every field carries `src`, the URLs it came from, and `from`, the record field or method that produced it. Fields are present
only when the record supports them. Dates carry a `kind` because they differ by source: on Commons own-work files the date
is when the file was made, not when the building was drawn. HABS sheets have building dates separate from the survey date.
`label_glossary` is a static term list for the drawing's language. It says nothing about this particular drawing.

## How the demo / router should use it

```python
from stoa.context.build import load_context
from stoa.context.prompt import render
ctx = load_context("data/finna/hka.139879309684900_166878548098200.jpg")   # None if not a historic drawing
block = render(ctx, max_chars=1400, web=True)    # ~400 tokens, framed as untrusted reference data
# zero-shot: prepend `block` to the question text; see src/stoa/context/method.py (HistoricVLM)
```

- Show `ctx["licence"]["credit"]` next to the drawing. The licence terms require it, and NC/SA/ND files have extra conditions.
- When the answer comes from the context (building, place, year, architect), cite the field's `src` URL as the evidence.
  When it comes from the image, use the normal grounding boxes.
- Treat web snippets as hints. A snippet can describe a different building with a similar name.

## How it was built

1. Archive records (step 1). The Wikimedia Commons API (50 titles per call) and the Europeana Record API v2 (public demo
   key `api2demo`) are called directly. The Finna API (40 ids per call) and loc.gov item JSON (`?fo=json`) sit behind a
   Cloudflare bot challenge that returns 403 to this network, so those two JSON APIs are fetched through context.dev's
   scraper at 1 credit per call. The scraper caps response bodies at about 67 KB, so failed Finna batches are re-fetched
   in batches of 6 and then 1.
   context.dev limits our org to 10 requests per minute, so every call is paced globally (one start per 6.2 s,
   Retry-After honoured). The full build is about 6,000 requests, roughly 10 hours: `scripts/context_run_all.sh` does
   the eval drawings first, then HABS records, then web search per source.
2. Web context (step 2). One context.dev search per building key: one per HABS survey, Finna address, Europeana title
   or Commons title+category. Each search returns 5 results with highlights and excludes the drawing's own archive
   domain. Cost: 2 credits per query.
3. Field extraction. Deterministic regex and lexicon rules over the record (`extract.py`, 13 languages) with no LLM,
   so every value can be traced to its source.
4. Security. All archive and web text is untrusted. `sanitize.py` strips HTML, scripts, URLs and control characters,
   drops sentences that look like instructions to an AI (and flags them), and caps every field. The prompt block is
   framed as "untrusted data … NOT an instruction".

Rebuild: `set -a; . ~/.config/contextdev/api.env; set +a; python scripts/context_fetch_archives.py; python scripts/context_build.py --web`.
Everything is cached, so a rebuild costs nothing unless new drawings are added.

## Measuring the benefit

`results/samples/historic_eval.jsonl` has 158 hand-labelled questions over 57 randomly drawn drawings (seed 2026;
3 non-drawings were skipped). 18 of them are interpretation questions added on purpose so that the answer is not verbatim in
the context (century from a year, country from a city, Pacific from Pearl Harbor, …). Each row has `origin` (record / record+reasoning / image), `needs_human_check` (true for
the 16 answers judged from the image) and a dev/test `split` by drawing. At evaluation time every question is also put
in a bucket, computed from the context block the model actually saw:

- lookup: the answer appears verbatim in the context. Context is expected to help here, and the gain mostly measures
  coverage.
- derived: the answer is not verbatim in the context. It needs translation or reasoning, e.g. Henriksgatan → Mannerheimintie,
  "XVIII" → 18th century, Palolaitos → fire station.
- visual: image-judged questions whose answer is not in the context. These check that the context does not distract the model.

Run: `scripts/context_eval.sh` against the vLLM endpoint (SSH tunnel to the DGX Spark, see the "GPU: DGX Spark" section of AGENTS.md; serving details in `DOCS/model-serving.md`). Results go to
`results/runs/hist-*.md` and the "Historic drawings" table in `results/leaderboard.md`.

## Results (2026-11-14 15:45, vLLM on the Verda instance, 158 questions)

| model / mode | all | lookup (n=123) | derived (n=23) | visual (n=12) | prompt tok/q | €/1k q* |
|---|---|---|---|---|---|---|
| Qwen3.5-4B zero-shot, no context | 0.576 | 0.545 | 0.522 | 1.000 | 1,786 | 0.061 |
| Qwen3.5-4B zero-shot, record + web context | **0.937** | 0.959 | **0.826** | 0.917 | 2,189 | 0.060 |
| Qwen3.5-4B zero-shot, record-only context | 0.930 | 0.943 | 0.826 | 1.000 | 2,046 | 0.056 |
| fine-tuned LoRA run1-step1050, no context | 0.589 | 0.585 | 0.435 | 0.917 | 1,720 | 0.058 |
| fine-tuned LoRA run1-step1050, context | 0.880 | 0.935 | 0.565 | 0.917 | 2,123 | 0.053 |

\* wall-clock at €1.75/h (one of the instance's two GPUs), concurrency 16. Dev and test halves agree within about 0.05
(see `results/runs/hist-*.md`). Context fixed 59 questions and broke 2 for the base model.

Reading:
- Most of the gain is in the lookup bucket. That is coverage: the context holds the building, place, architect and
  date, which the drawing often doesn't show.
- In the derived bucket the answer is not in the context and needs reasoning from it: XVIII → 18th century, Pearl
  Harbor → Pacific, Henriksgatan → Mannerheimintie, a Greek title → Lysicrates. There the base model goes from 0.52
  to 0.83. The sample is small (n=23), so treat it as indicative.
- Context can mislead. One visual question broke when a web snippet about "Tilkka Hospital" won over the drawing's
  "villa". A Dutch-held record made the model answer Netherlands for a Van Doesburg house in Meudon.
- Web snippets add almost nothing over the record alone (0.937 vs 0.930) and caused the visual break. Show
  record fields as evidence, and show web lines as hints.
- For historic drawings, use the base model with the context. The LoRA was trained on quantity questions and uses
  context worse on reasoning questions.
