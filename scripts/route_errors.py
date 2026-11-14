"""Run a deterministic route over TRAIN/VAL questions (never test) and dump per-rule accuracy + errors.
usage: python -I scripts/route_errors.py swiss|ifc [--split train,val] [--limit N] [--out file.jsonl]"""
import argparse, asyncio, collections, json, os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions
from stoa.scoring import is_correct

ap = argparse.ArgumentParser(); ap.add_argument("route"); ap.add_argument("--split", default="train,val")
ap.add_argument("--limit", type=int); ap.add_argument("--out"); ap.add_argument("--source")
a = ap.parse_args()
splits = set(a.split.split(",")); assert "test" not in splits, "never tune on test"
if a.route == "swiss":
    from stoa.methods.swiss_dxf import answer_dxf as fn; src = "swiss_dwellings"
elif a.route == "ifc":
    from stoa.methods.ifc_route import answer_ifc as fn; src = "ifc_models"
elif a.route == "std":
    from stoa.answer import answer_std as fn; src = a.source
qs, seen = [], set()
for q in load_questions():
    if q.source == src and q.split in splits and q.pair not in seen:
        seen.add(q.pair); qs.append(q)
if a.limit:
    random.Random(0).shuffle(qs); qs = qs[: a.limit]
by = collections.defaultdict(lambda: [0, 0, 0]); rows = []
for i, q in enumerate(qs):
    try:
        r = fn(q.path, q.question)
    except Exception as e:
        r = {"value": None, "error": repr(e)[:200]}
    m = r.get("method") or ("abstain:" + str(r.get("abstain_reason") or r.get("error"))[:40])
    ok = is_correct(q.type, r.get("value"), q.answer)
    by[(q.split, m)][0] += 1; by[(q.split, m)][1] += ok; by[(q.split, m)][2] += r.get("value") is None
    rows.append({"split": q.split, "path": q.path, "q": q.question, "gold": q.answer, "type": q.type, "pred": r.get("value"),
                 "method": m, "ok": ok, "conf": r.get("confidence"), "flags": r.get("flags")})
for (s, m), (n, k, ab) in sorted(by.items()):
    print(f"{s:5s} {m:45s} n={n:5d} acc={k/n:.3f} abst={ab/n:.2f}")
if a.out:
    with open(a.out, "w") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
