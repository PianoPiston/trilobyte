"""Calibrate the swiss DXF rules on TRAIN drawings only: accuracy per question kind + error examples.
usage: STOA_DATA=... python -I scripts/calibrate_swiss_dxf.py [n_drawings]"""
import sys, os, collections, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions
from stoa.scoring import is_correct
from stoa.methods.swiss_dxf import answer_dxf
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
qs = [q for q in load_questions() if q.source == "swiss_dwellings" and q.split == "train"]
paths = sorted({q.path for q in qs})[:N]
ps = set(paths)
agg, bad = collections.defaultdict(lambda: [0, 0, 0]), collections.defaultdict(list)
for q in qs:
    if q.path not in ps:
        continue
    r = answer_dxf(q.path, q.question)
    k = r.get("method") or ("abstain:" + r.get("abstain_reason", ""))[:40]
    if q.type == "count" and k.startswith("abstain"):
        k += " " + re.sub(r"[«'\"].*?[»'\"]", "X", q.question)[:40]
    a = agg[(q.type, k)]
    a[0] += 1
    if r.get("value") is None:
        a[2] += 1
    elif is_correct(q.type, r["value"], q.answer):
        a[1] += 1
    elif len(bad[k]) < 4:
        bad[k].append((q.answer, r["value"], q.question[:80], q.path.split("/")[-1]))
for k, (n, c, ab) in sorted(agg.items(), key=lambda x: -x[1][0]):
    print(f"{k}: n={n} acc={c/n:.3f} abstain={ab/n:.2f}")
for k, v in bad.items():
    print("ERR", k, v)
