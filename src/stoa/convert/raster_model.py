"""Raster floor plan -> standardized drawing file from MODEL predictions (detector boxes, VLM facts).

producer.kind = "model", ground_truth_eligible = False: these files are predictions and must never be used as
labels or ground truth. Each detection keeps its score; the per-class count threshold and the "uncertain band"
(scores near the threshold) come from the detector policy (scripts/calibrate_detector.py, TRAIN hold-out + VAL).
"""
import datetime, json, os

CONVERTER = "raster_model@1.0"
SYMBOL_CLASSES = {"toilet", "sink", "shower", "bathtub", "sauna_stove"}
DEFAULT_POLICY = {"thresholds": {c: 0.5 for c in ["window", "door", "toilet", "sink", "shower", "bathtub", "sauna_stove"]},
                  "band": 0.25}


def load_policy(path=None):
    path = path or os.environ.get("STOA_DET_POLICY")
    if path and os.path.exists(path):
        return json.load(open(path))
    return DEFAULT_POLICY


def nms_cross_class(dets, iou=0.7):
    """drop lower-scored boxes that heavily overlap a higher-scored box of the SAME class"""
    out = []
    for d in sorted(dets, key=lambda d: -d["score"]):
        x0, y0, x1, y1 = d["bbox_px"]
        keep = True
        for o in out:
            if o["cls"] != d["cls"]:
                continue
            a0, b0, a1, b1 = o["bbox_px"]
            iw, ih = max(0, min(x1, a1) - max(x0, a0)), max(0, min(y1, b1) - max(y0, b0))
            inter = iw * ih
            u = (x1 - x0) * (y1 - y0) + (a1 - a0) * (b1 - b0) - inter
            if u > 0 and inter / u > iou:
                keep = False
                break
        if keep:
            out.append(d)
    return out


def dedupe_openings(dets, rules):
    """Count rule for openings (scripts/error_analysis_cubicasa.py, scripts/tune_count_rule.py; tuned on VAL only).
    VAL error analysis: most window/door count errors were one opening detected as two boxes (overlapping or
    split along the wall) and openings scored just under the threshold. For each class in `rules`, drop a
    lower-scored box that overlaps a kept box by > `overlap` of the smaller box, or that is collinear with it and
    within `gap` px along the wall (gap < 0 disables the collinear merge)."""
    if not rules:
        return dets
    out = []
    for d in sorted(dets, key=lambda d: -d["score"]):
        r = rules.get(d["cls"])
        if r is None:
            out.append(d)
            continue
        b, dup = d["bbox_px"], False
        for o in out:
            if o["cls"] != d["cls"]:
                continue
            k = o["bbox_px"]
            inter = max(0, min(b[2], k[2]) - max(b[0], k[0])) * max(0, min(b[3], k[3]) - max(b[1], k[1]))
            amin = max(1e-6, min((b[2] - b[0]) * (b[3] - b[1]), (k[2] - k[0]) * (k[3] - k[1])))
            if inter / amin > r.get("overlap", 0.3):
                dup = True
                break
            gap = r.get("gap", -1)
            if gap >= 0:
                hb, hk = (b[2] - b[0]) > (b[3] - b[1]), (k[2] - k[0]) > (k[3] - k[1])
                if hb and hk and abs((b[1] + b[3]) - (k[1] + k[3])) / 2 < 4 and max(b[0], k[0]) - min(b[2], k[2]) <= gap:
                    dup = True
                    break
                if not hb and not hk and abs((b[0] + b[2]) - (k[0] + k[2])) / 2 < 4 and max(b[1], k[1]) - min(b[3], k[3]) <= gap:
                    dup = True
                    break
        if not dup:
            out.append(d)
    return out


def tta_counts(tta, policy=None):
    """per-class counts on each augmented view (list of {cls: n})"""
    policy = policy or load_policy()
    th = policy["thresholds"]
    out = []
    for view in tta or []:
        c = {}
        for cls, s in view:
            if s >= th.get(cls, 0.5):
                c[cls] = c.get(cls, 0) + 1
        out.append(c)
    return out


def from_detections(q_path, size, dets, policy=None, model_name=None):
    model_name = model_name or ("det2" if os.environ.get("STOA_DET_CLASSES", "v1") == "v2" else "det1")
    policy = policy or load_policy()
    th, band = policy["thresholds"], policy.get("band", 0.25)
    W, H = size
    dets = nms_cross_class(dets)
    rules = policy.get("count_rules")
    if rules:  # only drop duplicates among boxes that pass the class threshold
        dets = dedupe_openings([d for d in dets if d["score"] >= th.get(d["cls"], 0.5)], rules) + \
            [d for d in dets if d["score"] < th.get(d["cls"], 0.5)]
    items = {"window": [], "door": [], "symbols": []}
    uncertain = {}
    for i, d in enumerate(dets):
        c, s = d["cls"], d["score"]
        t = th.get(c, 0.5)
        if abs(s - t) < band * (policy.get("band_scale", {}).get(c, 1.0)):
            uncertain[c] = uncertain.get(c, 0) + 1
        if s < t:
            continue
        x0, y0, x1, y1 = d["bbox_px"]
        it = {"id": f"{c[0].upper()}{i}", "kind": c, "geometry": {
            "bbox_px": [round(v, 1) for v in d["bbox_px"]],
            "bbox_norm": [round(x0 / W, 4), round(y0 / H, 4), round(x1 / W, 4), round(y1 / H, 4)]},
            "provenance": {"method": f"detector:{model_name}", "confidence": round(s, 3)}}
        if c.startswith("room_"):
            it["type"] = c[5:]; it["name"] = None; it["area_m2"] = None
            items.setdefault("rooms", []).append(it)
        else:
            (items["symbols"] if c in SYMBOL_CLASSES else items[c]).append(it)
    stem = os.path.splitext(os.path.basename(q_path))[0]
    return {
        "schema_version": "stoa-drawing/1.0", "drawing_id": "cubicasa5k/" + stem,
        "source": {"dataset_source": q_path.split("/")[1], "files": {"png": q_path}, "page": 0,
                   "licence": "CC BY-NC-SA 4.0" if "cubicasa" in q_path else None,
                   "credit": "CubiCasa5k (Kalervo et al. 2019), CC BY-NC-SA 4.0" if "cubicasa" in q_path else None},
        "producer": {"kind": "model", "converter": CONVERTER, "models": [f"detector:{model_name}"],
                     "created": datetime.date.today().isoformat()},
        "ground_truth_eligible": False,
        "frame": {"world_units": "px", "image_size_px": [W, H], "world_bounds": [0, 0, W, H],
                  "scale": {"m_per_px": None, "method": "unknown", "confidence": 0.0}},
        "levels": [], "units": [], "rooms": items.get("rooms", []), "doors": items["door"], "windows": items["window"],
        "symbols": items["symbols"], "elements": [], "facts": {},
        "quality": {"warnings": [], "uncertain_detections": uncertain},
    }
