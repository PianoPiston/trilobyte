"""Choose the detector count policy (per-class score threshold + "uncertain band") on the TRAIN hold-out drawings
(5% of train, never used for training; their counts come from the train-split annotations).
usage: python -I scripts/calibrate_detector.py dets_holdout.jsonl det_train.jsonl OUT_policy.json"""
import collections, json, sys

sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "src"))
from stoa.convert.raster_model import nms_cross_class
from stoa.detector import CLASSES

dets = {json.loads(l)["path"]: json.loads(l) for l in open(sys.argv[1])}
labels = {r["path"]: r for r in map(json.loads, open(sys.argv[2])) if r["holdout"]}
paths = [p for p in labels if p in dets]
print("holdout drawings with detections:", len(paths))
D = {p: nms_cross_class(dets[p]["dets"]) for p in paths}
policy = {"thresholds": {}, "band": 1.0, "band_scale": {}, "report": {}}
for c in CLASSES:
    gold = {p: labels[p]["counts"].get(c, 0) for p in paths}
    best = (0, 0.5)
    for t in [x / 100 for x in range(10, 100, 2)]:
        acc = sum(sum(1 for d in D[p] if d["cls"] == c and d["score"] >= t) == gold[p] for p in paths) / len(paths)
        if acc > best[0]:
            best = (acc, t)
    t = best[1]
    policy["thresholds"][c] = t
    # band: largest |score - t| window such that drawings with no detection inside it are counted exactly
    # in >= 99% of cases; report the share of such "clean" drawings
    bb = None
    for b in [0.4, 0.35, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05]:
        clean = [p for p in paths if not any(d["cls"] == c and abs(d["score"] - t) < b for d in D[p])]
        ok = sum(sum(1 for d in D[p] if d["cls"] == c and d["score"] >= t) == gold[p] for p in clean)
        if clean and ok / len(clean) >= 0.99:
            bb = (b, len(clean) / len(paths), ok / len(clean))
    if bb is None:
        bb = (0.45, 0, 0)
    policy["band_scale"][c] = bb[0]
    policy["report"][c] = {"threshold": t, "exact_count_acc": round(best[0], 3), "band": bb[0],
                           "clean_share": round(bb[1], 3), "clean_precision": round(bb[2], 3)}
    print(c, policy["report"][c])
json.dump(policy, open(sys.argv[3], "w"), indent=1)
