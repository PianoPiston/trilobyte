"""Deterministic answers for ifc_models questions (rendered plan PDFs and model-level .ifc questions) by querying
the source IFC with ifcopenshell. Plan `<model>_plan-NN-<level>.pdf` was rendered from `<model>.ifc`.

Supported (multilingual keywords from the dataset's own translations): element counts per storey or per model
(doors, windows, walls, columns, beams, stairs, spaces, sanitary terminals, light fixtures), room net floor area,
total net floor area of spaces on a storey, wall total length / net side area / net volume, slab net volume.
Quantities come from IFC base quantity sets (Qto_*BaseQuantities); calibrated on TRAIN models only.
Evidence = IFC GlobalIds of the elements used. Anything not recognised returns value None (router falls back).
"""
import functools, os, re
from ..data import DATA_ROOT

KW = {
    "IfcDoor": r"\bdoor|tür|türen|døre|deur|drzwi|\bust\b|puert|porte?\b|\buși",
    "IfcWindow": r"window|fenster|vindue|\bram(en)?\b|okien|okn|akent|aken|ventan|finestr|ferestr",
    "IfcWall": r"\bwall|wänd|wand|vægge|væg|ścian|sein|muros?\b|muri\b|pereț",
    "IfcColumn": r"column|stütz|søjl|kolom|stâlp|post|pilar|colonn|słup",
    "IfcBeam": r"\bbeam|träger|bjælk|balk|grinz|belek|tala\b|viga|trav",
    "IfcStair": r"stair|trepp|trapp|\btrap|scăr|scari|schod|escaler|scal",
    "IfcSpace": r"room|space|räum|raum|\brum\b|ruimte|pomieszcz|ruum|local|stanz|încăper",
    "IfcSanitaryTerminal": r"sanit",
    "IfcLightFixture": r"light fixture|leucht|iluminat|lysarmatur|armatur|lamp",
}
MODEL_SCOPE = r"\bmodel|modell|modelu|mudel|modelo|modello|modelul"
QUOTES = [r"'([^']+?)'(?=\s|,|\?|$|\))", r"„(.+?)[“”]", r"«\s*(.+?)\s*»", r"“(.+?)”", r'"(.+?)"', r"‘(.+?)’"]


def quoted(q):
    out = []
    for p in QUOTES:
        out += [(m.start(), m.group(1)) for m in re.finditer(p, q)]
    return [s for _, s in sorted(out)]


def ifc_for(q_path):
    full = os.path.join(DATA_ROOT, q_path)
    if full.endswith(".ifc"):
        return full
    stem = os.path.splitext(full)[0]
    return stem.split("_plan-")[0] + ".ifc"


@functools.lru_cache(maxsize=16)
def load(ifc_path):
    import ifcopenshell
    return ifcopenshell.open(ifc_path)


def storey_of(e):
    import ifcopenshell.util.element as U
    c = U.get_container(e)
    seen = 0
    while c is None or not c.is_a("IfcBuildingStorey"):
        nxt = U.get_aggregate(e if c is None else c) if seen == 0 or c is not None else None
        if c is not None and c.is_a("IfcBuildingStorey"):
            break
        if nxt is None:
            if c is None:
                return None
            nxt = U.get_container(c) or U.get_aggregate(c)
            if nxt is None:
                return None
        c, e, seen = nxt, nxt, seen + 1
        if seen > 8:
            return None
    return c


_PREFIX = {"MILLI": 1e-3, "CENTI": 1e-2, "DECI": 1e-1, "KILO": 1e3, None: 1.0}


@functools.lru_cache(maxsize=64)
def unit_scale(f, unit_type):
    """factor converting project quantities of unit_type (LENGTHUNIT/AREAUNIT/VOLUMEUNIT) to SI m/m2/m3"""
    import ifcopenshell.util.unit as UU
    try:
        u = UU.get_project_unit(f, unit_type)
    except Exception:
        u = None
    if u is None:
        return 1.0
    if u.is_a("IfcSIUnit"):
        exp = {"LENGTHUNIT": 1, "AREAUNIT": 2, "VOLUMEUNIT": 3}[unit_type]
        return _PREFIX.get(u.Prefix, 1.0) ** exp
    try:
        return float(UU.calculate_unit_scale(f)) ** {"LENGTHUNIT": 1, "AREAUNIT": 2, "VOLUMEUNIT": 3}[unit_type]
    except Exception:
        return 1.0


_UT = {"NetFloorArea": "AREAUNIT", "GrossFloorArea": "AREAUNIT", "NetSideArea": "AREAUNIT", "GrossSideArea": "AREAUNIT",
       "NetVolume": "VOLUMEUNIT", "GrossVolume": "VOLUMEUNIT", "Length": "LENGTHUNIT"}


def qto(e, *keys):
    import ifcopenshell.util.element as U
    ps = U.get_psets(e, qtos_only=True)
    for k in keys:
        for name, d in ps.items():
            if k in d and isinstance(d[k], (int, float)):
                return float(d[k]) * unit_scale(_FILE[0], _UT[k])
    return None


_FILE = [None]


def geom_floor_area(e):
    """Footprint area (m2) of a space from its 3D body (geometry engine outputs SI metres)."""
    import ifcopenshell.geom, ifcopenshell.util.shape as S
    st = ifcopenshell.geom.settings()
    st.set("use-world-coords", True)
    try:
        sh = ifcopenshell.geom.create_shape(st, e)
        return float(S.get_footprint_area(sh.geometry))
    except Exception:
        return None


def space_area(s):
    v = qto(s, "NetFloorArea", "GrossFloorArea")
    return v if v is not None else geom_floor_area(s)


def find_storey(f, name):
    sts = f.by_type("IfcBuildingStorey")
    for s in sts:
        if (s.Name or "").strip() == name.strip():
            return s
    for s in sts:
        if (s.Name or "").strip().lower() == name.strip().lower():
            return s
    return None


TYPE_2X3 = {"IfcLightFixture": "IfcLightFixtureType", "IfcSanitaryTerminal": "IfcSanitaryTerminalType"}


def by_type(f, ifc_type):
    try:
        return f.by_type(ifc_type)
    except RuntimeError:  # IFC2x3: these are IfcFlowTerminal instances typed by IfcXxxType
        import ifcopenshell.util.element as U
        tt = TYPE_2X3.get(ifc_type)
        return [e for e in f.by_type("IfcFlowTerminal") if tt and (U.get_type(e) is not None and U.get_type(e).is_a(tt))]


def elems_on(f, ifc_type, storey):
    es = by_type(f, ifc_type)
    if storey is None:
        return es
    return [e for e in es if storey_of(e) == storey]


def answer_ifc(q_path, question):
    ip = ifc_for(q_path)
    if not os.path.exists(ip):
        return {"value": None, "abstain_reason": "no ifc"}
    f = load(ip)
    _FILE[0] = f
    qs = quoted(question)
    t = question
    for x in qs:
        t = t.replace(x, " ")
    t = t.lower()
    model_scope = re.search(MODEL_SCOPE, t) is not None
    is_vol = bool(re.search(r"m³|m3\b|volum", t))
    is_area = bool(re.search(r"m²|m2\b", t)) and not is_vol
    is_len = (not is_area and not is_vol) and bool(re.search(r"length|läng|lang\b|længde|lengte|meter|metr|longitud|lungh", t))

    def out(v, els, how, unit, digits=3):
        return {"value": round(v, digits) if isinstance(v, float) else v, "unit": unit, "confidence": 0.99,
                "evidence": [{"ifc_global_id": e.GlobalId, "ifc_type": e.is_a(), "name": getattr(e, "Name", None)} for e in els[:500]],
                "method": f"ifc:{how}"}

    storey = None
    if not model_scope and qs:
        storey = find_storey(f, qs[-1])
        if storey is None:
            return {"value": None, "abstain_reason": f"storey not found: {qs[-1]}"}

    if is_area and len(qs) >= 2:  # single room on a storey
        room = qs[0]
        cands = elems_on(f, "IfcSpace", storey)
        def label(s):
            ln, n = (s.LongName or "").strip(), (s.Name or "").strip()
            return {f"{ln} ({n})", f"{n} ({ln})", ln, n}
        hit = [s for s in cands if room.strip() in label(s)]
        if not hit:
            return {"value": None, "abstain_reason": "room not found"}
        v = qto(hit[0], "NetFloorArea", "GrossFloorArea")
        how = "space_net_area"
        if v is None:
            v, how = geom_floor_area(hit[0]), "space_geom_area"
        return out(v, hit[:1], how, "m2") if v is not None else {"value": None, "abstain_reason": "no area"}
    if is_area and re.search(KW["IfcWall"], t):
        ws = elems_on(f, "IfcWall", storey)
        vals = [qto(w, "NetSideArea", "GrossSideArea") for w in ws]
        return out(sum(v for v in vals if v), ws, "wall_net_side_area", "m2")
    if is_area:
        ss = elems_on(f, "IfcSpace", storey)
        vals = [space_area(s) for s in ss]
        return out(sum(v for v in vals if v), ss, "spaces_total_area", "m2")
    if is_vol:
        typ = "IfcWall" if re.search(KW["IfcWall"], t) else "IfcSlab"
        es = elems_on(f, typ, storey)
        vals = [qto(e, "NetVolume", "GrossVolume") for e in es]
        return out(sum(v for v in vals if v), es, f"{typ}_net_volume", "m3")
    if is_len:
        ws = elems_on(f, "IfcWall", storey)
        vals = [qto(w, "Length") for w in ws]
        return out(sum(v for v in vals if v), ws, "wall_length", "m")
    for typ, kw in KW.items():  # counts; check specific types before generic "room"
        if typ == "IfcSpace":
            continue
        if re.search(kw, t):
            es = elems_on(f, typ, storey)
            return out(len(es), es, f"count_{typ}", "count")
    if re.search(KW["IfcSpace"], t):
        es = elems_on(f, "IfcSpace", storey)
        return out(len(es), es, "count_IfcSpace", "count")
    return {"value": None, "abstain_reason": "question kind not recognised"}


class IFCMethod:
    async def answer(self, q_path, question):
        if "/ifc_models/" not in "/" + q_path:
            return {"value": None, "abstain_reason": "not ifc_models"}
        import asyncio
        return await asyncio.to_thread(answer_ifc, q_path, question)
