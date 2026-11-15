"""Area accuracy of the exact-file route on TRAIN/VAL (never test), per source x rule x flag, with an error dump.
usage: python scripts/area_errors.py [--split train,val] [--out errors.jsonl]"""
import argparse, collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions
from stoa.scoring import is_correct
from stoa.answer import answer_std

ap = argparse.ArgumentParser(); ap.add_argument("--split", default="train,val"); ap.add_argument("--out"); ap.add_argument("--source", default="swiss_dwellings,ifc_models")
a = ap.parse_args(); SOURCES = a.source.split(",")
splits = set(a.split.split(",")); assert "test" not in splits or os.environ.get("STOA_ALLOW_TEST") == "1", "never tune on test"
seen, by, rows = set(), collections.defaultdict(lambda: [0, 0, 0]), []
for q in load_questions():
    if q.type != "area" or q.split not in splits or q.pair in seen or q.source not in SOURCES:
        continue
    seen.add(q.pair)
    try:
        r = answer_std(q.path, q.question)
    except Exception as e:
        r = {"value": None, "abstain_reason": repr(e)[:80]}
    ok = is_correct(q.type, r.get("value"), q.answer)
    auto = r.get("value") is not None and r.get("confidence", 0) >= 0.95
    key = (q.split, q.source, (r.get("method") or "abstain").split(":")[-1], ",".join(r.get("flags") or []))
    by[key][0] += 1; by[key][1] += ok; by[key][2] += auto
    for tot in ((q.split, q.source, "ALL", ""), (q.split, "ALL", "ALL", "")):
        by[tot][0] += 1; by[tot][1] += ok; by[tot][2] += auto
    if not ok:
        rows.append({"split": q.split, "path": q.path, "q": q.question, "gold": q.answer, "pred": r.get("value"),
                     "method": r.get("method"), "flags": r.get("flags"), "why": r.get("abstain_reason")})
for k, (n, c, au) in sorted(by.items()):
    print(f"{k[0]:5s} {k[1]:16s} {k[2]:22s} {k[3]:24s} n={n:5d} best-guess={c/n:.4f} auto={au/n:.3f}")
if a.out:
    with open(a.out, "w") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
