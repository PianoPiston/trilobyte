"""IFC model -> standardized drawing file (exact, ground-truth eligible), and answering ifc_models questions from it.

One file per IFC model (all rendered plans `<model>_plan-NN-<level>.pdf` share it). Quantities come from IFC base
quantity sets (Qto_*BaseQuantities, scaled to SI) or, for spaces without Qto, from the geometry footprint.
Question parsing is the calibrated keyword logic of stoa.methods.ifc_route (TRAIN models only).
"""
import datetime, functools, os, re
from ..data import DATA_ROOT
from ..methods import ifc_route as R

CONVERTER = "ifc_std@1.1"
TYPES = ["IfcDoor", "IfcWindow", "IfcWall", "IfcColumn", "IfcBeam", "IfcStair", "IfcSlab", "IfcSanitaryTerminal", "IfcLightFixture"]


def _prov(rule, conf=1.0):
    return {"method": f"ifc:{rule}", "confidence": conf}


@functools.lru_cache(maxsize=8)
def convert(ifc_rel):
    f = R.load(os.path.join(DATA_ROOT, ifc_rel))
    R._FILE[0] = f
    levels = []
    for s in f.by_type("IfcBuildingStorey"):
        levels.append({"id": s.GlobalId, "name": (s.Name or "").strip(), "elevation_m": None, "ifc_global_id": s.GlobalId,
                       "provenance": _prov("IfcBuildingStorey")})
    rooms = []
    for s in f.by_type("IfcSpace"):
        st = R.storey_of(s)
        q = R.qto(s, "NetFloorArea", "GrossFloorArea")
        meth = "ifc_qto"
        if q is None or q <= 0:
            q, meth = R.geom_floor_area(s), "ifc_geometry"
        if q is not None and q <= 1e-6:
            q = None  # degenerate geometry: no usable area
        rooms.append({"id": s.GlobalId, "name": (s.LongName or "").strip() or None, "number": (s.Name or "").strip() or None,
                      "type": None, "is_outdoor": False, "is_shaft": False,
                      "area_m2": round(q, 4) if q is not None else None, "area_method": meth if q is not None else None,
                      "printed_area_m2": None, "polygon_area_m2": None, "unit_id": None,
                      "level_id": st.GlobalId if st is not None else None, "ifc_global_id": s.GlobalId,
                      "provenance": _prov(f"IfcSpace/{meth}", 1.0 if meth == "ifc_qto" else 0.97)})
    elements = []
    import ifcopenshell.util.element as U
    for t in TYPES:
        for e in R.by_type(f, t):
            agg = U.get_aggregate(e)
            if t == "IfcStair" and agg is not None and agg.is_a(t):
                continue  # parts of an aggregated element (e.g. stair flights modelled as IfcStair inside an IfcStair)
            st = R.storey_of(e)
            qs = {}
            if t == "IfcWall":
                qs = {"length_m": R.qto(e, "Length"), "net_side_area_m2": R.qto(e, "NetSideArea", "GrossSideArea"),
                      "net_volume_m3": R.qto(e, "NetVolume", "GrossVolume")}
            elif t == "IfcSlab":
                qs = {"net_volume_m3": R.qto(e, "NetVolume", "GrossVolume")}
            elements.append({"id": e.GlobalId, "kind": t[3:].lower(), "ifc_type": t, "ifc_global_id": e.GlobalId,
                             "name": getattr(e, "Name", None), "level_id": st.GlobalId if st is not None else None,
                             "quantities": qs, "provenance": _prov(t)})
    stem = os.path.splitext(ifc_rel)[0]
    return {
        "schema_version": "stoa-drawing/1.0", "drawing_id": "ifc_models/" + os.path.basename(stem),
        "source": {"dataset_source": "ifc_models", "files": {"ifc": ifc_rel}, "page": 0, "licence": "per file",
                   "credit": "see data/ifc_models/LICENSE.md"},
        "producer": {"kind": "exact", "converter": CONVERTER, "created": datetime.date.today().isoformat()},
        "ground_truth_eligible": True,
        "frame": {"world_units": "m", "image_size_px": None, "world_bounds": None,
                  "scale": {"m_per_px": None, "method": "ifc_units", "confidence": 1.0}},
        "levels": levels, "units": [], "rooms": rooms,
        "doors": [e for e in elements if e["kind"] == "door"], "windows": [e for e in elements if e["kind"] == "window"],
        "symbols": [e for e in elements if e["kind"] in ("sanitaryterminal", "lightfixture")],
        "elements": [e for e in elements if e["kind"] not in ("door", "window", "sanitaryterminal", "lightfixture")],
        "facts": {}, "quality": {"warnings": []},
    }


def for_question_path(q_path):
    ip = R.ifc_for(q_path)
    if not os.path.exists(ip):
        return None
    return convert(os.path.relpath(ip, DATA_ROOT))


def _ev(items):
    return [{"id": it["id"], "ifc_global_id": it["ifc_global_id"], "ifc_type": it.get("ifc_type") or "IfcSpace",
             "name": it.get("name"), **({"area_m2": it["area_m2"]} if "area_m2" in it else {})} for it in items[:500]]


def answer_ifc_std(doc, q_path, question):
    qs = R.quoted(question)
    t = question
    for x in qs:
        t = t.replace(x, " ")
    t = t.lower()
    model_scope = re.search(R.MODEL_SCOPE, t) is not None
    is_vol = bool(re.search(r"m³|m3\b|volum", t))
    is_area = bool(re.search(r"m²|m2\b", t)) and not is_vol
    is_len = (not is_area and not is_vol) and bool(re.search(r"length|läng|lang\b|længde|lengte|meter|metr|longitud|lungh", t))
    allel = doc["doors"] + doc["windows"] + doc["symbols"] + doc["elements"]

    def out(v, items, rule, unit, conf=0.99, flags=None):
        return {"value": round(v, 3) if isinstance(v, float) else v, "unit": unit, "confidence": conf, "evidence": _ev(items),
                "method": f"std:exact:ifc:{rule}", "flags": flags or [], "drawing_id": doc["drawing_id"], "ground_truth_eligible": True}

    lvl = None
    if not model_scope and qs:
        name = qs[-1].strip()
        lv = [l for l in doc["levels"] if l["name"] == name] or [l for l in doc["levels"] if l["name"].lower() == name.lower()]
        if not lv:
            return {"value": None, "abstain_reason": f"storey not found: {name}"}
        lvl = lv[0]["id"]
    on = lambda items: [x for x in items if lvl is None or x["level_id"] == lvl]
    of = lambda typ: on([e for e in allel if e["ifc_type"] == typ])

    if is_area and len(qs) >= 2:
        room = qs[0].strip()
        def labels(s):
            ln, n = s["name"] or "", s["number"] or ""
            return {f"{ln} ({n})", f"{n} ({ln})", ln, n}
        hit = [s for s in on(doc["rooms"]) if room in labels(s)]
        if not hit or hit[0]["area_m2"] is None:
            return {"value": None, "abstain_reason": "room not found / no area"}
        flags = ["ambiguous_room_label"] if len(hit) > 1 and len({h["area_m2"] for h in hit}) > 1 else []
        conf = 0.99 if hit[0]["area_method"] == "ifc_qto" else 0.97  # geometry footprint: train 446/448, val 284/284
        return out(hit[0]["area_m2"], hit[:1], "space_area_" + hit[0]["area_method"], "m2", conf=0.5 if flags else conf, flags=flags)
    if is_area and re.search(R.KW["IfcWall"], t):
        ws = of("IfcWall")
        return out(sum(w["quantities"].get("net_side_area_m2") or 0 for w in ws), ws, "wall_net_side_area", "m2")
    if is_area:
        ss = on(doc["rooms"])
        flags = ["space_without_area"] if any(s["area_m2"] is None for s in ss) else []
        return out(sum(s["area_m2"] or 0 for s in ss), ss, "spaces_total_area", "m2", conf=0.5 if flags else 0.99, flags=flags)
    if is_vol:
        typ = "IfcWall" if re.search(R.KW["IfcWall"], t) else "IfcSlab"
        es = of(typ)
        return out(sum(e["quantities"].get("net_volume_m3") or 0 for e in es), es, f"{typ}_net_volume", "m3")
    if is_len:
        ws = of("IfcWall")
        return out(sum(w["quantities"].get("length_m") or 0 for w in ws), ws, "wall_length", "m")
    for typ, kw in R.KW.items():
        if typ == "IfcSpace":
            continue
        if re.search(kw, t):
            es = of(typ)
            return out(len(es), es, f"count_{typ}", "count")
    if re.search(R.KW["IfcSpace"], t):
        ss = on(doc["rooms"])
        return out(len(ss), ss, "count_IfcSpace", "count")
    return {"value": None, "abstain_reason": "question kind not recognised"}
