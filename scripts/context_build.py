#!/usr/bin/env python3
"""Build context/<source>/<stem>.json for every historic drawing, plus context/COVERAGE.md.

  set -a; . ~/.config/contextdev/api.env; set +a
  python scripts/context_build.py                       # archive records only (cached after the first run)
  python scripts/context_build.py --web --estimate      # print the context.dev cost of the web step, spend nothing
  python scripts/context_build.py --web [--web-limit N] # + context.dev web search (one query per building key)
  python scripts/context_build.py --only-stems a,b      # restrict (pilot / eval drawings)
"""
import argparse, collections, concurrent.futures as cf, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src"))
from stoa.context.licenses import drawings, HISTORIC_SOURCES, ROOT
from stoa.context.archives import FETCHERS
from stoa.context.build import build_context, write_context, CTX_DIR
from stoa.context import fetch, web as W

ap = argparse.ArgumentParser()
ap.add_argument("sources", nargs="*", default=list(HISTORIC_SOURCES))
ap.add_argument("--web", action="store_true"); ap.add_argument("--estimate", action="store_true")
ap.add_argument("--web-limit", type=int); ap.add_argument("--only-stems"); ap.add_argument("--workers", type=int, default=4)
a = ap.parse_args()
only = set(a.only_stems.split(",")) if a.only_stems else None
if a.only_stems and os.path.exists(a.only_stems):
    only = {json.loads(l)["stem"] if l.strip().startswith("{") else l.strip() for l in open(a.only_stems) if l.strip()}

c0 = fetch.credits_spent()
stats = {}
for s in a.sources:
    ds = drawings(s)
    if only and s != "finna":  # finna batches need the canonical full list to hit the cache
        ds = [d for d in ds if d["stem"] in only]
    recs = FETCHERS[s](ds)  # full list in canonical order -> identical (cached) batch URLs
    if only:
        ds = [d for d in ds if d["stem"] in only]
    ctxs = {d["stem"]: build_context(s, d, recs.get(d["stem"])) for d in ds}
    if a.web:
        qs = collections.OrderedDict()
        for d in ds:
            q = W.query_for(s, ctxs[d["stem"]])
            if q:
                qs.setdefault(q, []).append(d["stem"])
        keys = list(qs)[: a.web_limit] if a.web_limit else list(qs)
        uncached = [q for q in keys if fetch._cached("cd_search", json.dumps([q, 5, True, 800, W.OWN_DOMAIN.get(s) or []], ensure_ascii=False)) is None]
        print(f"{s}: {len(ds)} drawings -> {len(qs)} unique web queries ({len(keys)} selected, {len(uncached)} uncached, "
              f"est. {2 * len(uncached)} credits)", flush=True)
        if not a.estimate:
            def one(q):
                try:
                    return q, W.search_for(s, ctxs[qs[q][0]])[1]
                except fetch.BudgetExceeded as e:
                    print("STOP:", e, flush=True)
                    return q, None
            with cf.ThreadPoolExecutor(a.workers) as ex:
                for k, (q, res) in enumerate(ex.map(one, keys)):
                    if res is None:
                        continue
                    for stem in qs[q]:
                        ctxs[stem] = build_context(s, next(d for d in ds if d["stem"] == stem), recs.get(stem), web=res)
                        ctxs[stem]["web_query"] = q
                    if k % 200 == 0:
                        print(f"  {s} web {k}/{len(keys)} credits so far {fetch.credits_spent() - c0}", flush=True)
    if a.estimate:
        continue
    for ctx in ctxs.values():
        write_context(ctx)
    cnt = collections.Counter()
    for ctx in ctxs.values():
        cnt["record_ok"] += ctx["record_ok"]
        cnt["web>=1"] += bool(ctx.get("web"))
        for k in ctx["fields"]:
            cnt[k] += 1
    stats[s] = (len(ctxs), cnt)
    print(f"{s}: wrote {len(ctxs)} context files", flush=True)

if stats and not only:
    fields = ["record_ok", "building", "place", "country", "year", "building_dates", "architect_or_author", "delineator",
              "drawing_type", "floor", "scale", "sheet", "language", "subjects", "description", "significance", "key_terms", "web>=1"]
    lines = ["# Historic context coverage", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `scripts/context_build.py`. "
             "Share of drawings whose context file has each field (a field is present only when the record or search supports it).", "",
             "| field | " + " | ".join(f"{s} (n={stats[s][0]})" for s in stats) + " | all |", "|---|" + "---|" * (len(stats) + 1)]
    tot = sum(n for n, _ in stats.values())
    for f in fields:
        row = [f"{stats[s][1][f]} ({100 * stats[s][1][f] / max(1, stats[s][0]):.0f}%)" for s in stats]
        allc = sum(stats[s][1][f] for s in stats)
        lines.append(f"| {f} | " + " | ".join(row) + f" | {allc} ({100 * allc / max(1, tot):.0f}%) |")
    led = [json.loads(l) for l in open(fetch.LEDGER)] if os.path.exists(fetch.LEDGER) else []
    by = collections.Counter()
    for l in led:
        by[l["kind"]] += l.get("credits", 0)
    lines += ["", f"context.dev credits used so far (ledger `context/credits_log.jsonl`): **{sum(by.values())}** "
              f"(scrape {by['scrape']}, search {by['search']}); last reported balance {led[-1]['remaining'] if led else 'n/a'}."]
    open(os.path.join(CTX_DIR, "COVERAGE.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
print("credits this run:", fetch.credits_spent() - c0)
