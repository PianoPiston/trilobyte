"""Coverage / precision trade-off of the logprob confidence on a VAL run (choose the "needs check" threshold here,
never on test). usage: python -I scripts/calibrate_confidence.py results/runs/<val-run>.jsonl"""
import json, sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.scoring import is_correct
rows = [json.loads(l) for l in open(sys.argv[1])]
by = collections.defaultdict(list)
for r in rows:
    c = r["pred"].get("confidence")
    if r["pred"].get("value") is None or c is None:
        continue
    by[r["source"]].append((c, is_correct(r["type"], r["pred"]["value"], r["answer"])))
    by["ALL"].append(by[r["source"]][-1])
print("| source | threshold | coverage | precision (answered) | errors per 100 q |")
print("|---|---|---|---|---|")
for s, v in sorted(by.items()):
    for th in (0.0, 0.3, 0.5, 0.7, 0.8, 0.9):
        kept = [ok for c, ok in v if c >= th]
        if not kept:
            continue
        print(f"| {s} | {th} | {len(kept)/len(v):.2f} | {sum(kept)/len(kept):.3f} | {100*(len(kept)-sum(kept))/len(v):.1f} |")
