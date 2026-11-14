"""swiss_dwellings DXF -> standardized drawing file (exact, ground-truth eligible).

DXF layers (metres): ROOM_OUTLINE, ROOM_TEXT (name / number / "12.34 m²"), UNIT_OUTLINE ("Whg. A"), WINDOW, DOOR,
FIXTURE, WALL. Symbol rules were calibrated on TRAIN floors only (scripts/calibrate_swiss_dxf.py,
scripts/calibrate_swiss_fixtures.py):
  door      = one 5-vertex frame polyline on DOOR (leaves are 2-vertex, swings are arcs)      train 1.000
  window    = 3 WINDOW polylines per window, grouped spatially                                 train 1.000
  bathtub   = 69-vertex FIXTURE polyline                                                       train 1.000
  shower    = 5-vertex open FIXTURE polyline                                                   train 1.000
  toilet    = 48-vertex ellipse with a 2-vertex seat line touching it (tank side)
  washbasin = 48-vertex ellipse without one
"""
import datetime, functools, os, re
from ..data import DATA_ROOT

CONVERTER = "swiss_dxf@1.2"
OUTDOOR = re.compile(r"balkon|balcon|balcony|loggia|terrass|sitzplatz|veranda|dachterrasse|patio|terrazz|garten|jardin|giardino", re.I)
SHAFT_VOID = re.compile(r"schacht|gaine|cavedio|shaft|luftraum|vide|void|vuoto", re.I)
STAIR = re.compile(r"treppe|escalier|scala|stair", re.I)
AREA_TXT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*m(?:²|2)\s*$")
NUM_TXT = re.compile(r"^\s*[A-Z]?\d+\.\d+\s*$")
UNIT_TXT = re.compile(r"^\s*(?:Whg\.?|Wohnung|App\.?|Apt\.?|Unit|Appartement|Appartamento)\s*([A-Z0-9]+)\s*$", re.I)


def _poly_item(poly, b, **kw):
    xs, ys = poly.exterior.xy
    g = {"polygon": [[round(x, 3), round(y, 3)] for x, y in zip(xs, ys)]}
    if b:
        x0, y0, x1, y1 = b
        g["polygon_norm"] = [[round((x - x0) / (x1 - x0), 4), round(1 - (y - y0) / (y1 - y0), 4)] for x, y in zip(xs, ys)]
        bx0, by0, bx1, by1 = poly.bounds
        g["bbox_norm"] = [round((bx0 - x0) / (x1 - x0), 4), round(1 - (by1 - y0) / (y1 - y0), 4),
                          round((bx1 - x0) / (x1 - x0), 4), round(1 - (by0 - y0) / (y1 - y0), 4)]
    return g


def _prov(rule, conf=1.0):
    return {"method": f"dxf:{rule}", "confidence": conf}


def _cluster(geoms, tol):
    """union-find clusters of geometries closer than tol"""
    n = len(geoms)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    from shapely.strtree import STRtree
    tree = STRtree(geoms)
    for i, g in enumerate(geoms):
        for j in tree.query(g.buffer(tol)):
            j = int(j)
            if j > i and geoms[j].distance(g) <= tol:
                parent[find(j)] = find(i)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


@functools.lru_cache(maxsize=256)
def convert(dxf_rel):
    """dxf_rel: dataset-relative path of the .dxf -> standardized dict"""
    import ezdxf
    from shapely.geometry import Polygon, Point, LineString, box
    from shapely.ops import unary_union
    doc = ezdxf.readfile(os.path.join(DATA_ROOT, dxf_rel))
    rooms, units, texts, win_lines, doors, fix = [], [], [], [], [], []
    for e in doc.modelspace():
        t, layer = e.dxftype(), e.dxf.layer
        if t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            if layer in ("ROOM_OUTLINE", "UNIT_OUTLINE") and len(pts) >= 3:
                (rooms if layer == "ROOM_OUTLINE" else units).append({"poly": Polygon(pts).buffer(0)})
            elif layer == "WINDOW" and pts:
                win_lines.append(LineString(pts) if len(pts) > 1 else Point(pts[0]))
            elif layer == "DOOR" and len(pts) == 5:
                doors.append(box(*Polygon(pts).bounds))
            elif layer == "FIXTURE" and pts:
                fix.append((len(pts), bool(e.closed), LineString(pts) if len(pts) > 1 else Point(pts[0])))
        elif t in ("TEXT", "MTEXT") and layer == "ROOM_TEXT":
            txt = e.plain_text() if t == "MTEXT" else e.dxf.text
            ins = e.dxf.insert
            texts.append((txt.strip(), Point(ins[0], ins[1])))
    for tx, pt in texts:
        um = UNIT_TXT.match(tx)
        if um:
            for u in units:
                if u["poly"].contains(pt):
                    u["label"] = um.group(1)
            continue
        cands = [r for r in rooms if r["poly"].contains(pt)] or sorted(rooms, key=lambda r: r["poly"].distance(pt))[:1]
        if not cands:
            continue
        r = min(cands, key=lambda r: r["poly"].area)
        am = AREA_TXT.match(tx)
        if am:
            r["printed_area"] = float(am.group(1).replace(",", "."))
        elif NUM_TXT.match(tx):
            r["number"] = tx.strip()
        else:
            r.setdefault("names", []).append(tx)
    allgeom = unary_union([r["poly"] for r in rooms] + [u["poly"] for u in units] + doors + win_lines) if (rooms or units) else None
    b = allgeom.bounds if allgeom is not None else None

    out_units = []
    for i, u in enumerate(units):
        out_units.append({"id": f"U{i}", "label": u.get("label"), "level_id": None, "room_ids": [],
                          "geometry": _poly_item(u["poly"], b), "provenance": _prov("UNIT_OUTLINE")})
    # net polygon area: other (smaller) room polygons lying inside a room are shafts/voids cut out of it
    for r in rooms:
        holes = [o["poly"] for o in rooms if o is not r and o["poly"].area < r["poly"].area
                 and r["poly"].intersection(o["poly"]).area > 0.9 * o["poly"].area]
        r["net_poly_area"] = r["poly"].area - sum(h.area for h in holes)
    out_rooms = []
    for i, r in enumerate(rooms):
        name = " ".join(r.get("names", [])) or None
        c = r["poly"].representative_point()
        uid = next((out_units[k]["id"] for k, u in enumerate(units) if u["poly"].contains(c)), None)
        rid = f"R{i}"
        if uid:
            out_units[int(uid[1:])]["room_ids"].append(rid)
        pa = r.get("printed_area")
        rtype = ("balcony" if name and OUTDOOR.search(name) else "shaft" if name and SHAFT_VOID.search(name)
                 else "stair" if name and STAIR.search(name) else None)
        out_rooms.append({
            "id": rid, "name": name, "number": r.get("number"), "type": rtype,
            "is_outdoor": bool(name and OUTDOOR.search(name)), "is_shaft": bool(name and SHAFT_VOID.search(name)),
            "area_m2": round(pa if pa is not None else r["net_poly_area"], 2), "area_method": "printed" if pa is not None else "polygon",
            "printed_area_m2": pa, "polygon_area_m2": round(r["poly"].area, 3), "unit_id": uid, "level_id": None,
            "geometry": _poly_item(r["poly"], b), "provenance": _prov("ROOM_OUTLINE+ROOM_TEXT")})
    out_doors = [{"id": f"D{i}", "kind": "door", "geometry": _poly_item(d, b), "provenance": _prov("DOOR:5-vertex-frame")}
                 for i, d in enumerate(doors)]
    # windows: 3 polylines each -> spatial groups
    wins = []
    for k, grp in enumerate(_cluster(win_lines, 0.01) if win_lines else []):
        g = unary_union([win_lines[i] for i in grp])
        n3 = len(grp)
        wins.append({"id": f"W{k}", "kind": "window", "geometry": _poly_item(box(*g.bounds), b),
                     "n_lines": n3, "count": max(1, round(n3 / 3)),  # touching windows merge into one group
                     "provenance": _prov("WINDOW:3-polyline-group", 1.0 if n3 % 3 == 0 else 0.6)})
    # fixtures
    ells = [g for n, cl, g in fix if n == 48]
    seats = [g for n, cl, g in fix if n == 2]
    syms = []
    for g in ells:
        is_toilet = any(s.distance(g) < 0.05 for s in seats)
        syms.append(("toilet" if is_toilet else "washbasin", g, "FIXTURE:48-ellipse+seat" if is_toilet else "FIXTURE:48-ellipse"))
    syms += [("bathtub", g, "FIXTURE:69-vertex") for n, cl, g in fix if n == 69]
    syms += [("shower", g, "FIXTURE:5-vertex-open") for n, cl, g in fix if n == 5 and not cl]
    out_syms = []
    for i, (kind, g, rule) in enumerate(syms):
        c = g.centroid
        rid = next((rr["id"] for rr, r in zip(out_rooms, rooms) if r["poly"].contains(c)), None)
        out_syms.append({"id": f"S{i}", "kind": kind, "room_id": rid, "geometry": _poly_item(box(*g.bounds), b),
                         "provenance": _prov(rule)})
    stem = os.path.splitext(dxf_rel)[0]
    files = {ext: stem + "." + ext for ext in ("png", "pdf", "dxf") if os.path.exists(os.path.join(DATA_ROOT, stem + "." + ext))}
    warnings = []
    if len(win_lines) % 3:
        warnings.append(f"WINDOW polyline count {len(win_lines)} not divisible by 3")
    return {
        "schema_version": "stoa-drawing/1.0", "drawing_id": "swiss_dwellings/" + os.path.basename(stem),
        "source": {"dataset_source": "swiss_dwellings", "files": files, "page": 0, "licence": "CC BY 4.0",
                   "credit": "Swiss Dwellings dataset (Standfest et al.), see data/swiss_dwellings/LICENSE.md"},
        "producer": {"kind": "exact", "converter": CONVERTER, "created": datetime.date.today().isoformat()},
        "ground_truth_eligible": True,
        "frame": {"world_units": "m", "image_size_px": None, "world_bounds": list(b) if b else None,
                  "scale": {"m_per_px": None, "method": "dxf_native", "confidence": 1.0}},
        "levels": [], "units": out_units, "rooms": out_rooms, "doors": out_doors, "windows": wins,
        "symbols": out_syms, "elements": [], "quality": {"warnings": warnings},
        "facts": {"window_count": {"value": len(win_lines) // 3, "provenance": _prov("WINDOW:polylines/3")}},
    }


def for_question_path(q_path):
    stem = os.path.splitext(q_path)[0]
    if not os.path.exists(os.path.join(DATA_ROOT, stem + ".dxf")):
        return None
    return convert(stem + ".dxf")
