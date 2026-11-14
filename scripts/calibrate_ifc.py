"""Calibrate the IFC route on TRAIN ifc_models questions only. usage: STOA_DATA=... python -I scripts/calibrate_ifc.py"""
import sys, os, collections, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions
from stoa.scoring import is_correct, rel_error
from stoa.methods.ifc_route import answer_ifc
split = sys.argv[1] if len(sys.argv) > 1 else "train"
qs = [q for q in load_questions() if q.source == "ifc_models" and q.split == split]
agg, bad = collections.defaultdict(lambda: [0, 0, 0]), collections.defaultdict(list)
for q in qs:
    try:
        r = answer_ifc(q.path, q.question)
    except Exception as e:
        r = {"value": None, "abstain_reason": "EXC " + repr(e)[:60]}
    k = r.get("method") or ("abstain:" + r.get("abstain_reason", ""))[:50]
    a = agg[(q.type, k)]; a[0] += 1
    if r.get("value") is None: a[2] += 1
    elif is_correct(q.type, r["value"], q.answer): a[1] += 1
    elif len(bad[k]) < 5: bad[k].append((q.answer, r["value"], q.question[:90], q.path.split("/")[-1][:50]))
    if r.get("value") is None and len(bad[k]) < 3: bad[k].append((q.answer, None, q.question[:90]))
for k, (n, c, ab) in sorted(agg.items(), key=lambda x: -x[1][0]):
    print(f"{k}: n={n} acc={c/n:.3f} abstain={ab/n:.2f}")
for k, v in bad.items():
    print("ERR", k, v)
