"""Parse an original CubiCasa5k `model.svg` annotation (Kalervo et al. 2019, CC BY-NC-SA 4.0) into rooms,
doors, windows, fixtures and floors in SVG pixel coordinates (they align with our cubicasa PNGs, see
scripts/calibrate_cubicasa_svg.py).

LEAKAGE RULE: these human annotations literally contain the answers. They may be read ONLY for drawings in
the TRAIN split (detector training labels and rule calibration). `load_annotation` enforces this; nothing at
inference time may call it.
"""
import math, os, re
import defusedxml.ElementTree as ET

CC5K_ROOT = os.environ.get("CC5K_ROOT", os.path.join(os.path.dirname(__file__), "../../../DATA/cubicasa5k-orig/cubicasa5k"))
NS = "{http://www.w3.org/2000/svg}"
_TF = re.compile(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)")


def _mat(tf):
    m = (1, 0, 0, 1, 0, 0)
    for kind, args in _TF.findall(tf or ""):
        v = [float(x) for x in re.split(r"[ ,]+", args.strip()) if x]
        if kind == "matrix":
            n = tuple(v[:6])
        elif kind == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif kind == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        else:
            a = math.radians(v[0]); c, s = math.cos(a), math.sin(a)
            n = (c, s, -s, c, 0, 0)
            if len(v) == 3:  # rotate(a, cx, cy)
                cx, cy = v[1], v[2]
                n = _mul(_mul((1, 0, 0, 1, cx, cy), n), (1, 0, 0, 1, -cx, -cy))
        m = _mul(m, n)
    return m


def _mul(A, B):
    a, b, c, d, e, f = A; g, h, i, j, k, l = B
    return (a * g + c * h, b * g + d * h, a * i + c * j, b * i + d * j, a * k + c * l + e, b * k + d * l + f)


def _apply(m, pts):
    a, b, c, d, e, f = m
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]


def _pts(s):
    v = [float(x) for x in re.split(r"[ ,]+", (s or "").strip()) if x]
    pts = list(zip(v[0::2], v[1::2]))
    while len(pts) > 1 and pts[-1] == pts[-2]:
        pts.pop()
    if len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    return pts


def _cls(el):
    return (el.get("class") or "").strip()


def parse_svg(svg_path):
    root = ET.parse(svg_path).getroot()
    out = {"width": float(root.get("width") or 0), "height": float(root.get("height") or 0),
           "floors": [], "rooms": [], "doors": [], "windows": [], "fixtures": []}

    def first_poly(el, m, sub=None):
        """first <polygon> under el (or under its child group whose class == sub), transformed to page coords"""
        stack = [(el, m)]
        while stack:
            node, mm = stack.pop(0)
            for ch in list(node):
                cm = _mul(mm, _mat(ch.get("transform")))
                if ch.tag == NS + "polygon" and (sub is None or _cls(node) == sub):
                    return _apply(cm, _pts(ch.get("points")))
                if ch.tag == NS + "g":
                    stack.append((ch, cm))
        return None

    def label_text(el):
        for g in el.iter(NS + "g"):
            if _cls(g) == "TextLabel NameLabel":
                t = "".join(g.itertext()).strip()
                if t:
                    return t
        return None

    def walk(el, m, floor):
        for ch in list(el):
            if ch.tag != NS + "g":
                continue
            cm = _mul(m, _mat(ch.get("transform")))
            c = _cls(ch)
            if c.startswith("Floorplan"):
                out["floors"].append(c.split()[-1])
                walk(ch, cm, len(out["floors"]) - 1)
                continue
            head = c.split(" ")[0] if c else ""
            if head == "Space":
                out["rooms"].append({"cls": c, "poly": first_poly(ch, cm), "label": label_text(ch), "floor": floor})
                walk(ch, cm, floor)  # spaces can contain nested elements
            elif head == "Door":
                out["doors"].append({"cls": c, "poly": first_poly(ch, cm), "floor": floor})
            elif head == "Window":
                out["windows"].append({"cls": c, "poly": first_poly(ch, cm), "floor": floor})
            elif head == "FixedFurniture":
                p = first_poly(ch, cm, sub="BoundaryPolygon") or first_poly(ch, cm)
                out["fixtures"].append({"cls": c, "poly": p, "floor": floor})
            else:
                walk(ch, cm, floor)
    walk(root, (1, 0, 0, 1, 0, 0), -1)
    return out


def svg_for(q_path):
    """data/cubicasa5k/<style>-<id>.png -> original model.svg"""
    stem = os.path.splitext(os.path.basename(q_path))[0]
    style, num = stem.rsplit("-", 1)
    return os.path.join(CC5K_ROOT, style, num, "model.svg")


def load_annotation(q_path, split):
    if split != "train":
        raise PermissionError(f"CubiCasa annotations may only be read for TRAIN drawings (got {split}: {q_path})")
    return parse_svg(svg_for(q_path))
