"""Window/door error analysis on VAL cubicasa drawings (never TEST).
Matches det2 detections (policy thresholds) to annotation boxes and classifies count errors.
VAL annotations are read for analysis only (same role as VAL policy calibration); nothing here is trained on."""
import collections, json, os, sys
from PIL import Image
sys.path.insert(0, "src")
from stoa.data import load_questions, DATA_ROOT
from stoa.convert.cubicasa_svg import parse_svg, svg_for

SIZES = json.load(open("DATA/cubicasa5k-orig/png_sizes.json"))
TH = json.load(open("results/detpolicy_det2.json"))["thresholds"]
DETS = {}
for l in open("artifacts/det2/dets_det2_all.jsonl"):
    r = json.loads(l); DETS[r["path"]] = r

def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0
def cover(a, b):  # share of a inside b
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x1 - x0) * max(0, y1 - y0); A = (a[2] - a[0]) * (a[3] - a[1])
    return i / A if A > 0 else 0

gold = {}
for q in load_questions():
    if q.source != "cubicasa5k" or q.split != "val" or not q.lang_en: continue
    t = q.question.lower()
    k = "window" if t.startswith("how many windows") else "door" if t.startswith("how many doors") else None
    if k: gold[(q.path, k)] = int(q.answer)

stats = {k: collections.Counter() for k in ("window", "door")}
plans = {k: collections.Counter() for k in ("window", "door")}
examples = collections.defaultdict(list)
for (p, k), g in sorted(gold.items()):
    stem = os.path.splitext(os.path.basename(p))[0]; style, num = stem.rsplit("-", 1)
    wh = SIZES.get(f"cubicasa5k/{style}/{num}/F1_scaled.png"); d = DETS.get(p)
    if not wh or not d or not os.path.exists(svg_for(p)): stats[k]["skipped"] += 1; continue
    W, H = d["size"]; sx, sy = W / wh[0], H / wh[1]
    A = parse_svg(svg_for(p))
    items = A["windows"] if k == "window" else A["doors"]
    ann = []
    for it in items:
        if not it["poly"]: continue
        xs = [x * sx for x, _ in it["poly"]]; ys = [y * sy for _, y in it["poly"]]
        b = [min(xs), min(ys), max(xs), max(ys)]
        if b[2] <= 0 or b[3] <= 0 or b[0] >= W or b[1] >= H: continue
        ann.append([b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2])
    dets_all = [x for x in d["dets"] if x["cls"] == k]
    dets = [x["bbox_px"] for x in dets_all if x["score"] >= TH[k]]
    if len(ann) != g: stats[k]["gold!=annotation"] += 1
    det_n = len(dets)
    if det_n == g: plans[k]["correct"] += 1; continue
    plans[k]["wrong"] += 1
    # classify errors
    used = set(); fn = fp = split = merge = fn_lowscore = 0
    for a in ann:
        ms = [i for i, b in enumerate(dets) if iou(a, b) > 0.25 or cover(b, a) > 0.6]
        if not ms:
            fn += 1
            low = max([x["score"] for x in dets_all if iou(a, x["bbox_px"]) > 0.25] or [0])
            if low > 0.2: fn_lowscore += 1
        elif len(ms) > 1: split += len(ms) - 1
        used.update(ms)
    for i, b in enumerate(dets):
        inside = [a for a in ann if cover(a, b) > 0.6]
        if len(inside) > 1: merge += len(inside) - 1
        if i not in used and not inside: fp += 1
    s = stats[k]
    s["missed"] += fn; s["missed_but_detected_below_threshold"] += fn_lowscore
    s["extra"] += fp; s["split (1 annotated -> >1 detected)"] += split; s["merged (>1 annotated -> 1 detected)"] += merge
    s["plans_with_" + ("too_few" if det_n < g else "too_many")] += 1
    if len(examples[k]) < 8: examples[k].append((p, g, det_n, fn, fp, split, merge))
for k in stats:
    n = plans[k]["correct"] + plans[k]["wrong"]
    print(f"\n== {k}: {n} VAL plans, exact {plans[k]['correct']/n:.2f}")
    for kk, v in stats[k].most_common(): print(f"   {kk}: {v}")
    for e in examples[k]: print("   e.g.", e)
