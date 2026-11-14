#!/usr/bin/env python3
"""Fetch + normalize archive records for all historic drawings -> context/_records/<source>.jsonl.
Usage: set -a; . ~/.config/contextdev/api.env; set +a
       python scripts/context_fetch_archives.py [habs finna europeana wikimedia] [--limit N]"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src"))
from stoa.context.licenses import drawings, HISTORIC_SOURCES, ROOT
from stoa.context.archives import FETCHERS
from stoa.context import fetch

ap = argparse.ArgumentParser(); ap.add_argument("sources", nargs="*", default=list(HISTORIC_SOURCES))
ap.add_argument("--limit", type=int); a = ap.parse_args()
os.makedirs(os.path.join(ROOT, "context/_records"), exist_ok=True)
for s in a.sources:
    t0, c0 = time.time(), fetch.credits_spent()
    ds = drawings(s)[: a.limit] if a.limit else drawings(s)
    recs = FETCHERS[s](ds)
    with open(os.path.join(ROOT, f"context/_records/{s}.jsonl"), "w") as f:
        for d in ds:
            f.write(json.dumps({"stem": d["stem"], "license": d, "record": recs.get(d["stem"])}, ensure_ascii=False) + "\n")
    ok = sum(1 for v in recs.values() if v and v.get("ok"))
    print(f"{s}: {len(ds)} drawings, {ok} records ok, {time.time()-t0:.0f}s, credits {fetch.credits_spent()-c0}", flush=True)
