"""Build detector training labels from the original CubiCasa5k SVG annotations, for TRAIN-split drawings ONLY.

Output JSONL rows: {"path": data/cubicasa5k/<style>-<id>.png, "boxes": [[x0,y0,x1,y1],...] (PNG px), "labels": [cls,...],
                    "counts": {...}, "holdout": bool}
`holdout` = 5% of train drawings kept aside to tune the detector's count thresholds (still train split, never val/test).
usage: python -I scripts/build_det_dataset.py DATA/cubicasa5k-orig/png_sizes.json OUT.jsonl
"""
import collections, hashlib, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions, DATA_ROOT
from stoa.convert.cubicasa_svg import load_annotation, svg_for
from stoa.convert.cubicasa_rules import SINKS
from PIL import Image

CLASSES = ["window", "door", "toilet", "sink", "shower", "bathtub", "sauna_stove"]
WITH_ROOMS = os.environ.get("STOA_DET_CLASSES", "v1") == "v2"


def room_class(r):
    c = set(r["cls"].split()); lab = (r["label"] or "").upper()
    if "Bedroom" in c:
        return "room_bedroom"
    if "Kitchen" in c:
        return "room_kitchen"
    if "Bath" in c:
        return "room_wc" if lab == "WC" else "room_bath"
    if "Balcony" in c:
        return "room_balcony"
    if "Sauna" in c:
        return "room_sauna"
    return None


def fixture_class(cls):
    c = set(cls.split())
    if "Toilet" in c:
        return "toilet"
    if c & SINKS:
        return "sink"
    if "Shower" in c:
        return "shower"
    if "Bathtub" in c:
        return "bathtub"
    if any(x.startswith("SaunaStove") for x in c):
        return "sauna_stove"
    return None


def main():
    sizes = json.load(open(sys.argv[1]))
    split = {}
    for q in load_questions():
        if q.source == "cubicasa5k":
            split[q.path] = q.split
    n_ok = n_skip = 0
    cnt = collections.Counter(); n_out = [0]
    with open(sys.argv[2], "w") as f:
        for p, sp in sorted(split.items()):
            if sp != "train":
                continue  # LEAKAGE RULE: never touch val/test annotations
            stem = os.path.splitext(os.path.basename(p))[0]
            style, num = stem.rsplit("-", 1)
            wh = sizes.get(f"cubicasa5k/{style}/{num}/F1_scaled.png")
            if not wh or not os.path.exists(svg_for(p)):
                n_skip += 1
                continue
            W, H = Image.open(os.path.join(DATA_ROOT, p)).size
            sx, sy = W / wh[0], H / wh[1]
            if abs(sx - sy) / sx > 0.02:
                n_skip += 1
                continue
            A = load_annotation(p, sp)
            boxes, labels = [], []
            groups = [("window", A["windows"]), ("door", A["doors"]), (None, A["fixtures"])]
            if WITH_ROOMS:
                groups.append(("ROOM", A["rooms"]))
            for kind, items in groups:
                for it in items:
                    c = room_class(it) if kind == "ROOM" else (kind or fixture_class(it["cls"]))
                    if c is None or not it["poly"]:
                        continue
                    xs = [x * sx for x, _ in it["poly"]]; ys = [y * sy for _, y in it["poly"]]
                    b = [max(0, min(xs)), max(0, min(ys)), min(W, max(xs)), min(H, max(ys))]
                    if b[0] >= W or b[1] >= H or b[2] <= 0 or b[3] <= 0:
                        n_out[0] += 1
                        continue
                    if b[2] - b[0] < 2 or b[3] - b[1] < 2:
                        b = [b[0] - 2, b[1] - 2, b[2] + 2, b[3] + 2]
                    boxes.append([round(v, 1) for v in b]); labels.append(c); cnt[c] += 1
            hold = int(hashlib.sha256(("det-holdout:" + p).encode()).hexdigest()[:8], 16) % 20 == 0
            f.write(json.dumps({"path": p, "size": [W, H], "boxes": boxes, "labels": labels,
                                "counts": dict(collections.Counter(labels)), "holdout": hold}) + "\n")
            n_ok += 1
    print("drawings", n_ok, "skipped", n_skip, "boxes outside image", n_out[0], cnt)


if __name__ == "__main__":
    main()
