"""Deterministic answers for swiss_dwellings floors from the DXF that ships next to each PNG/PDF.

DXF layers (metres): ROOM_OUTLINE (room polygons), ROOM_TEXT (name / number / "12.34 m²" inside each room),
UNIT_OUTLINE (apartments, labelled "Whg. A"), WINDOW, DOOR, FIXTURE, WALL.
Rules were calibrated on TRAIN drawings only (see scripts/calibrate_swiss_dxf.py).
Evidence = room / unit polygons or element bboxes in DXF coordinates (and page-normalized 0-1 coords).
Unsupported question kinds return value None so a router can fall back to the VLM.
"""
import os, re, functools
from ..data import DATA_ROOT

OUTDOOR = re.compile(r"balkon|balcon|balcony|loggia|terrass|sitzplatz|veranda|dachterrasse|patio|terrazz|garten|jardin|giardino", re.I)
SHAFT_VOID = re.compile(r"schacht|gaine|cavedio|shaft|luftraum|vide|void|vuoto", re.I)
AREA_TXT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*m(?:²|2)\s*$")
NUM_TXT = re.compile(r"^\s*\d+\.\d+\s*$")
FLOOR_REQUIRE_NAME = False  # A/B on 400 train floors: True 0.860, False 0.963
UNIT_TXT = re.compile(r"^\s*(?:Whg\.?|Wohnung|App\.?|Apt\.?|Unit|Appartement|Appartamento)\s*([A-Z0-9]+)\s*$", re.I)


@functools.lru_cache(maxsize=256)
def parse(dxf_path):
    import ezdxf
    from shapely.geometry import Polygon, Point, box
    from shapely.ops import unary_union
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    rooms, units, texts, windows, door_geoms = [], [], [], [], []
    for e in msp:
        t, layer = e.dxftype(), e.dxf.layer
        if t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            if layer in ("ROOM_OUTLINE", "UNIT_OUTLINE") and len(pts) >= 3:
                poly = Polygon(pts).buffer(0)
                (rooms if layer == "ROOM_OUTLINE" else units).append({"poly": poly})
            elif layer == "WINDOW" and pts:
                windows.append(pts)
            elif layer == "DOOR" and len(pts) == 5:
                # each door has exactly one 5-vertex frame polyline (leaf lines are 2-vertex, swings are ARCs;
                # double doors have 2 arcs but 1 frame) - calibrated on train: matches gold door counts
                door_geoms.append(box(*Polygon(pts).bounds))
        elif t in ("TEXT", "MTEXT") and layer == "ROOM_TEXT":
            txt = e.plain_text() if t == "MTEXT" else e.dxf.text
            ins = e.dxf.insert
            texts.append((txt.strip(), Point(ins[0], ins[1])))
    # assign texts to rooms (smallest containing room), unit labels to units
    for tx, pt in texts:
        um = UNIT_TXT.match(tx)
        if um:
            for u in units:
                if u["poly"].contains(pt):
                    u["label"] = um.group(1)
            continue
        cands = [r for r in rooms if r["poly"].contains(pt)]
        if not cands:
            cands = sorted(rooms, key=lambda r: r["poly"].distance(pt))[:1]
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
    for r in rooms:
        r["name"] = " ".join(r.get("names", [])) or None
        r["area"] = r.get("printed_area", round(r["poly"].area, 2))
        r["unit"] = None
        c = r["poly"].representative_point()
        for u in units:
            if u["poly"].contains(c):
                r["unit"] = u.get("label")
    doors = door_geoms
    allgeom = unary_union([r["poly"] for r in rooms] + [u["poly"] for u in units]) if rooms else None
    return {"rooms": rooms, "units": units, "windows": windows, "doors": doors,
            "bounds": allgeom.bounds if allgeom is not None else None}


def _q_label(q):
    for pat in (r"«\s*(.+?)\s*»", r"„\s*(.+?)\s*[“”]", r"“\s*(.+?)\s*”", r"‘(.+?)’", r'"(.+?)"', r"(?<!\w)'(.+?)'(?!\w)"):
        m = re.search(pat, q)
        if m:
            return m.group(1).strip()
    return None


def _ev_poly(poly, b):
    xs, ys = poly.exterior.xy
    item = {"polygon_dxf": [[round(x, 3), round(y, 3)] for x, y in zip(xs, ys)]}
    if b:
        x0, y0, x1, y1 = b
        item["polygon_norm"] = [[round((x - x0) / (x1 - x0), 4), round(1 - (y - y0) / (y1 - y0), 4)] for x, y in zip(xs, ys)]
    return item


def answer_dxf(q_path, question):
    stem = os.path.splitext(os.path.join(DATA_ROOT, q_path))[0]
    dxf = stem + ".dxf"
    if not os.path.exists(dxf):
        return {"value": None, "abstain_reason": "no dxf"}
    P = parse(dxf)
    rooms, units, b = P["rooms"], P["units"], P["bounds"]
    t = question.lower()
    is_area = bool(re.search(r"m²|m2|fläche|area|surface|superficie", t))
    label = _q_label(question)
    numm = re.search(r"\b(\d+\.\d+)\b", question)
    aptm = re.search(r"(?:apartment|wohnung|appartement|appartamento|l'appartement|dell'appartamento)\s+([A-Z0-9]+)\b", question, re.I)

    def out(v, ev, how, unit):
        return {"value": v, "unit": unit, "evidence": ev, "confidence": 0.99, "method": f"dxf:{how}"}

    if is_area:
        if numm:  # single room by number
            rs = [r for r in rooms if r.get("number") == numm.group(1)]
            if rs:
                return out(round(rs[0]["area"], 2), [_ev_poly(rs[0]["poly"], b)], "room_area", "m2")
        if aptm:
            lab = aptm.group(1).upper()
            # unnamed rooms are shafts / voids (calibrated on train): excluded like outdoor spaces
            rs = [r for r in rooms if (r["unit"] or "").upper() == lab and r["name"] and not OUTDOOR.search(r["name"])]
            if rs:
                return out(round(sum(r["area"] for r in rs), 2), [_ev_poly(r["poly"], b) for r in rs], "apartment_area", "m2")
        if label:
            rs = [r for r in rooms if (r["name"] or "").lower() == label.lower()]
            if rs:
                return out(round(sum(r["area"] for r in rs), 2), [_ev_poly(r["poly"], b) for r in rs], "label_area", "m2")
        if re.search(r"numbered|nummeriert|numérot|numerat", t):
            rs = [r for r in rooms if (r.get("number") or not any(x.get("number") for x in rooms))
                  and (r["name"] or not FLOOR_REQUIRE_NAME)
                  and not OUTDOOR.search(r["name"] or "") and not SHAFT_VOID.search(r["name"] or "")]
            return out(round(sum(r["area"] for r in rs), 2), [_ev_poly(r["poly"], b) for r in rs], "floor_area", "m2")
        return {"value": None, "abstain_reason": "area question kind not recognised"}
    # counts
    if label:
        rs = [r for r in rooms if (r["name"] or "").lower() == label.lower()]
        return out(len(rs), [_ev_poly(r["poly"], b) for r in rs], "rooms_labelled", "count")
    if re.search(r"window|fenster|fenêtre|finestr", t):
        n = len(P["windows"]) // 3
        return out(n, [], "windows/3", "count")
    if re.search(r"door|tür|porte|port[ae]", t):
        return out(len(P["doors"]), [{"bbox_dxf": [round(v, 3) for v in d.bounds]} for d in P["doors"]], "door_frames", "count")
    if re.search(r"apartment|wohnung|appartement|appartament|residential unit", t):
        us = [u for u in units if u.get("label")] or units
        return out(len(us), [_ev_poly(u["poly"], b) for u in us], "units", "count")
    return {"value": None, "abstain_reason": "count kind not supported by DXF route (fixtures)"}


class SwissDXFMethod:
    async def answer(self, q_path, question):
        if "/swiss_dwellings/" not in "/" + q_path:
            return {"value": None, "abstain_reason": "not swiss_dwellings"}
        import asyncio
        return await asyncio.to_thread(answer_dxf, q_path, question)
