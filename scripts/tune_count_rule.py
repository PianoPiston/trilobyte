"""Tune a count rule (threshold + duplicate merging) per class on VAL gold counts only; report VAL exact-count accuracy."""
import collections, json, sys, itertools
sys.path.insert(0, "src")
from stoa.data import load_questions
DETS = {json.loads(l)["path"]: json.loads(l) for l in open("artifacts/det2/dets_det2_all.jsonl")}
TH = json.load(open("results/detpolicy_det2.json"))["thresholds"]
def inter(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
def area(a): return max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))
def count(dets, t, cov, gap):
    bs = sorted([d for d in dets if d["score"] >= t], key=lambda d: -d["score"])
    keep = []
    for d in bs:
        b = d["bbox_px"]; dup = False
        for k in keep:
            # duplicate if mostly overlapping, or collinear and touching within `gap` px (same opening split in two)
            if inter(b, k) / min(area(b), area(k)) > cov: dup = True; break
            if gap >= 0:
                horiz = (b[2] - b[0]) > (b[3] - b[1]) and (k[2] - k[0]) > (k[3] - k[1])
                vert = not horiz and (b[3] - b[1]) >= (b[2] - b[0]) and (k[3] - k[1]) >= (k[2] - k[0])
                if horiz and abs((b[1] + b[3]) - (k[1] + k[3])) / 2 < 4 and (max(b[0], k[0]) - min(b[2], k[2])) <= gap: dup = True; break
                if vert and abs((b[0] + b[2]) - (k[0] + k[2])) / 2 < 4 and (max(b[1], k[1]) - min(b[3], k[3])) <= gap: dup = True; break
        if not dup: keep.append(b)
    return len(keep)
data = {"val": collections.defaultdict(list), "train": collections.defaultdict(list)}
for q in load_questions():
    if q.source != "cubicasa5k" or not q.lang_en or q.split not in data: continue
    t = q.question.lower()
    k = "window" if t.startswith("how many windows") else "door" if t.startswith("how many doors") else None
    if k and q.path in DETS: data[q.split][k].append((DETS[q.path]["dets"], int(q.answer)))
for k in ("window", "door"):
    V = [([x for x in d if x["cls"] == k], g) for d, g in data["val"][k]]
    base = sum(count(d, TH[k], 0.7, -1) == g for d, g in V) / len(V)
    best = max(((sum(count(d, t, c, gap) == g for d, g in V) / len(V), t, c, gap)
                for t in [0.3, 0.4, 0.5, 0.55, 0.6, 0.66, 0.7, 0.75, 0.82]
                for c in [0.3, 0.5, 0.7] for gap in [-1, 0, 3, 8]))
    print(f"{k}: VAL n={len(V)} current rule exact={base:.3f} -> best {best[0]:.3f} (threshold {best[1]}, overlap-merge {best[2]}, collinear gap {best[3]})")
