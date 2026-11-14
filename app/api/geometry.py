"""Map standardized-file evidence into the pixel frame of the image the UI shows.

swiss_dwellings: the standardized file stores DXF world coordinates (metres). The PNG sheet places the plan at an
unknown print scale and offset inside a frame with a title block, so we *register* the DXF onto the PNG: rasterize
the room/door/window outlines at candidate scales and rotations, cross-correlate with the PNG ink (FFT) and keep the
best. Result: affine world -> px, cached per drawing.

ifc_models: the rendered plan SVG carries `data-guid` on every element group, so each IFC GlobalId gets its exact
bbox in SVG user units, mapped linearly onto the PNG (same page).
"""
import json, math, os, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None


# ---------------------------------------------------------------------------------------------------- swiss
def _ink(png_path, ds):
    im = Image.open(png_path).convert("L")
    W, H = im.size
    sm = im.resize((max(1, W // ds), max(1, H // ds)), Image.BOX)
    a = (np.asarray(sm) < 235).astype(np.float32)
    return a, (W, H)


def _world_polys(doc):
    polys = []
    for key in ("rooms", "units", "doors", "windows"):
        for it in doc.get(key, []):
            p = (it.get("geometry") or {}).get("polygon")
            if p and len(p) >= 2:
                polys.append(np.asarray(p, dtype=np.float64))
    return polys


def _rot(pts, k):
    x, y = pts[:, 0], pts[:, 1]
    return [np.c_[x, y], np.c_[-y, x], np.c_[-x, -y], np.c_[y, -x]][k]


SCALE_DENOMS = (50, 100, 150, 200, 250, 500)
PAPER_LONG_MM = (297, 420, 594, 841)  # A4..A1


def _score_at(ink_d, integ, polys, allp, k, s, ds, h, w):
    pts_all = _rot(allp, k) * (s / ds)
    pts_all[:, 1] *= -1  # world y up -> image y down
    x0, y0 = pts_all.min(0)
    tw, th = int(math.ceil(np.ptp(pts_all[:, 0]))) + 3, int(math.ceil(np.ptp(pts_all[:, 1]))) + 3
    if tw >= w or th >= h or tw < 8 or th < 8:
        return None
    tpl = Image.new("L", (tw, th), 0)
    d = ImageDraw.Draw(tpl)
    for p in polys:
        q = _rot(p, k) * (s / ds)
        q[:, 1] *= -1
        q = q - [x0 - 1, y0 - 1]
        d.line([tuple(v) for v in q], fill=255, width=1)
    t = (np.asarray(tpl) > 0).astype(np.float32)
    n = t.sum()
    if n < 20:
        return None
    F_t = np.fft.rfft2(t[::-1, ::-1], s=(2 * h, 2 * w))
    corr = np.fft.irfft2(np.fft.rfft2(ink_d, s=(2 * h, 2 * w)) * F_t, s=(2 * h, 2 * w))
    valid = corr[th - 1:h, tw - 1:w] / n
    # ink density of each placement window (integral image): a template over a solid black area scores ~0
    dens = (integ[th:, tw:] - integ[:-th, tw:] - integ[th:, :-tw] + integ[:-th, :-tw]) / (tw * th)
    dens = dens[:valid.shape[0], :valid.shape[1]]
    sc = valid - dens
    iy, ix = np.unravel_index(np.argmax(sc), sc.shape)
    return float(sc[iy, ix]), float(valid[iy, ix]), ix - (x0 - 1), iy - (y0 - 1)


def register_swiss(png_path, doc, ds=4):
    """-> {"M": [[a,b,c],[d,e,f]] world->full-res px, "score", "rot", "px_per_m"}. Searches the standard print
    scales (1:50..1:500) on A4..A1 sheets, rotations 0/90/180/270, then refines the scale by +-3%."""
    ink, (W, H) = _ink(png_path, ds)
    ink_d = (np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0).astype(np.float32)
    h, w = ink.shape
    integ = np.zeros((h + 1, w + 1)); integ[1:, 1:] = ink_d.cumsum(0).cumsum(1)
    polys = _world_polys(doc)
    if not polys:
        return None
    allp = np.vstack(polys)
    cands = sorted({round(max(W, H) / L * 1000 / dn, 3) for L in PAPER_LONG_MM for dn in SCALE_DENOMS})
    res = []
    for k in range(4):
        for s in cands:
            r = _score_at(ink_d, integ, polys, allp, k, s, ds, h, w)
            if r:
                res.append((r[0], k, s, r))
    if not res:
        return None
    res.sort(key=lambda x: -x[0])
    best = res[0]
    for _, k, s0, _r in res[:2]:
        for f in np.linspace(0.97, 1.03, 13):
            r = _score_at(ink_d, integ, polys, allp, k, s0 * f, ds, h, w)
            if r and r[0] > best[0]:
                best = (r[0], k, s0 * f, r)
    score, k, s, (sc, ov, ox, oy) = best
    R = [np.array([[1, 0], [0, 1]]), np.array([[0, -1], [1, 0]]), np.array([[-1, 0], [0, -1]]), np.array([[0, 1], [-1, 0]])][k]
    A = np.diag([s, -s]) @ R
    M = [[float(A[0, 0]), float(A[0, 1]), float(ox * ds)], [float(A[1, 0]), float(A[1, 1]), float(oy * ds)]]
    return {"M": M, "score": round(float(score), 3), "overlap": round(float(ov), 3), "rot": int(k),
            "px_per_m": round(float(s), 3), "image_size": [W, H]}


def apply_M(M, pts):
    return [[round(M[0][0] * x + M[0][1] * y + M[0][2], 1), round(M[1][0] * x + M[1][1] * y + M[1][2], 1)] for x, y in pts]


# ---------------------------------------------------------------------------------------------------- ifc svg
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


_TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_NARGS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}


def path_points(d):
    """end points (and control points) of an SVG path, absolute coordinates; arcs contribute their end point and
    a radius-padded box"""
    pts, cx, cy, cmd, args = [], 0.0, 0.0, None, []
    toks = _TOK.findall(d)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                continue
            continue
        if cmd is None:
            i += 1
            continue
        n = _NARGS[cmd.upper()]
        vals = [float(v) for v in toks[i:i + n]]
        i += n
        if len(vals) < n:
            break
        rel = cmd.islower()
        U = cmd.upper()
        if U in "MLT":
            x, y = vals
            cx, cy = (cx + x, cy + y) if rel else (x, y)
            pts.append((cx, cy))
            if U == "M":
                cmd = "l" if rel else "L"
        elif U == "H":
            cx = cx + vals[0] if rel else vals[0]
            pts.append((cx, cy))
        elif U == "V":
            cy = cy + vals[0] if rel else vals[0]
            pts.append((cx, cy))
        elif U in "CSQ":
            for k in range(0, n, 2):
                x, y = vals[k], vals[k + 1]
                pts.append((cx + x, cy + y) if rel else (x, y))
            cx, cy = pts[-1]
        elif U == "A":
            x, y = vals[5], vals[6]
            nx, ny = (cx + x, cy + y) if rel else (x, y)
            r = max(abs(vals[0]), abs(vals[1]))
            if r < 1e4:  # quarter-swing door arcs: include the swing radius around the end points
                mx, my = (cx + nx) / 2, (cy + ny) / 2
                pts += [(mx - r / 2, my - r / 2), (mx + r / 2, my + r / 2)]
            cx, cy = nx, ny
            pts.append((cx, cy))
    return pts


def svg_guid_boxes(svg_path):
    """-> (viewBox [x,y,w,h], {guid: [x0,y0,x1,y1] in svg user units})"""
    txt = open(svg_path, encoding="utf-8", errors="replace").read()
    vb = re.search(r'viewBox="([^"]+)"', txt)
    vbox = [float(v) for v in vb.group(1).split()] if vb else None
    boxes = {}
    for m in re.finditer(r'<g [^>]*?data-guid="([^"]+)"[^>]*>(.*?)</g>', txt, re.S):
        guid, body = m.group(1), m.group(2)
        pts = []
        for d in re.findall(r'\sd="([^"]+)"', body):
            pts += path_points(d)
        for pm in re.finditer(r'points="([^"]+)"', body):
            nums = [float(v) for v in _NUM.findall(pm.group(1))]
            pts += list(zip(nums[0::2], nums[1::2]))
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            b = [min(xs), min(ys), max(xs), max(ys)]
            if vbox:  # clip to the page
                b = [max(b[0], vbox[0]), max(b[1], vbox[1]), min(b[2], vbox[0] + vbox[2]), min(b[3], vbox[1] + vbox[3])]
                if b[2] <= b[0] or b[3] <= b[1]:
                    continue
            if guid in boxes:
                o = boxes[guid]
                b = [min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])]
            boxes[guid] = b
    return vbox, boxes


def svg_to_px(vbox, size, b):
    W, H = size
    x, y, w, h = vbox
    sx, sy = W / w, H / h
    return [round((b[0] - x) * sx, 1), round((b[1] - y) * sy, 1), round((b[2] - x) * sx, 1), round((b[3] - y) * sy, 1)]
