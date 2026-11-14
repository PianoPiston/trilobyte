"""Answer questions from a standardized drawing file (schema/drawing.schema.json), deterministically.

  intent = parse_intent(question)            # language-agnostic regexes (EN/DE/FR/IT/FI templates of the dataset)
  result = query(doc, intent)                # value + evidence items + confidence + flags

Confidence = min(provenance confidence of the items used) x rule reliability, and rules with known ambiguity
(calibrated on TRAIN/VAL only, see scripts/route_errors.py) return lower confidence or abstain ("needs check").
"""
import os, re
from .data import DATA_ROOT

QUOTE_PATS = (r"«\s*(.+?)\s*»", r"„\s*(.+?)\s*[“”]", r"“\s*(.+?)\s*”", r"‘(.+?)’", r'"(.+?)"', r"(?<!\w)'(.+?)'(?!\w)")


def quoted(q):
    for pat in QUOTE_PATS:
        m = re.search(pat, q)
        if m:
            return m.group(1).strip()
    return None


SYMBOL_KW = [  # order matters: more specific first
    ("showers_baths", r"showers and bathtubs|suihku\w* ja kylpyamme"),
    ("toilet", r"toilet bowl|wc seat|wc-istuim|toilets \(wc\)|\bwcs\b|wie viele wcs|combien de wc|quanti wc|\bwc\b(?! room)(?!-huone)"),
    ("sink", r"sinks and wash basins|pesu- ja tiskial"),
    ("washbasin", r"washbasin|lavabo|lavabi"),
    ("bathtub", r"bathtub|badewann|baignoire|vasche da bagno|vasca da bagno"),
    ("shower", r"shower|dusche|douche|docce|doccia"),
    ("sauna_stove", r"sauna"),
]
ROOM_TYPE_FIRST = [  # checked before symbols (their wording mentions toilets / WC)
    ("bath", r"bathrooms or washrooms|kylpy- tai pesuhuone"),
    ("wc", r"separate wc rooms|erillis\w* wc-tila"),
]
ROOM_TYPE_KW = [
    ("bedroom", r"bedroom|makuuhuone"),
    ("kitchen", r"kitchen|keittiö"),
    ("balcony", r"balcon(y|ies)|parveke"),
]


def parse_intent(question):
    t = question.lower()
    label = quoted(question)
    is_area = bool(re.search(r"m²|m2\b|fläche|area|surface|superficie|pinta-ala", t))
    if is_area:
        numm = re.search(r"(?:room|raum|pièce|piece|locale|huone)\s+(U?\d+\.\d+)", question, re.I) or re.search(r"\b(U?\d+\.\d+)\b", question)
        if numm:
            return {"kind": "area_room_number", "number": numm.group(1)}
        aptm = re.search(r"(?:apartment|wohnung|appartement|appartamento|l'appartement|dell'appartamento|asunno[nt]?)\s+([A-Z0-9]+)\b", question, re.I)
        if aptm:
            return {"kind": "area_unit", "label": aptm.group(1).upper()}
        if label:
            return {"kind": "area_label", "label": label}
        if re.search(r"numbered|nummeriert|numérot|numerat", t):
            return {"kind": "area_floor_numbered"}
        return {"kind": "unknown"}
    if label:
        return {"kind": "count_rooms_labelled", "label": label}
    if re.search(r"floors \(storeys\)|kerrosta|storeys", t):
        return {"kind": "count_floors"}
    for rt, kw in ROOM_TYPE_FIRST:
        if re.search(kw, t):
            return {"kind": "count_room_type", "type": rt}
    for kind, kw in SYMBOL_KW:
        if re.search(kw, t):
            if kind == "sauna_stove":
                return {"kind": "count_saunas"}
            return {"kind": "count_symbol", "symbol": kind}
    for rt, kw in ROOM_TYPE_KW:
        if re.search(kw, t):
            return {"kind": "count_room_type", "type": rt}
    if re.search(r"window|fenster|fenêtre|finestr|ikkun", t):
        return {"kind": "count_windows"}
    if re.search(r"door|tür|porte|port[ae]|\bov(i|ea|et)\b|ovia", t):
        return {"kind": "count_doors"}
    if re.search(r"apartment|wohnung|appartement|appartament|residential unit|asun", t):
        return {"kind": "count_units"}
    return {"kind": "unknown"}


def _ev(items, role="counted"):
    out = []
    for it in items:
        g = it.get("geometry") or {}
        e = {"id": it["id"], "kind": it.get("kind") or it.get("type") or ("room" if "area_m2" in it else None), "role": role}
        for k in ("polygon", "polygon_norm", "bbox_px", "bbox_norm"):
            if k in g:
                e[k] = g[k]
        if it.get("ifc_global_id"):
            e["ifc_global_id"] = it["ifc_global_id"]
        if it.get("name"):
            e["name"] = it["name"]
        if "area_m2" in it:
            e["area_m2"] = it["area_m2"]
        out.append(e)
    return out


def _conf(items, base=1.0):
    cs = [it.get("provenance", {}).get("confidence", 1.0) for it in items]
    return round(base * (min(cs) if cs else 1.0), 4)


def _res(value, unit, items, rule, base=1.0, flags=None, conf=None):
    return {"value": value, "unit": unit, "evidence": _ev(items), "rule": rule,
            "confidence": conf if conf is not None else _conf(items, base), "flags": flags or []}


def _has_symbols(doc, room):
    return any(s.get("room_id") == room["id"] for s in doc.get("symbols", []))


def query(doc, intent):
    k = intent["kind"]
    rooms, units = doc.get("rooms", []), doc.get("units", [])
    if k == "area_room_number":
        rs = [r for r in rooms if (r.get("number") or "") == intent["number"]]
        if len(rs) != 1:
            return None
        return _res(round(rs[0]["area_m2"], 2), "m2", rs, "room_area")  # train 0.995, val 0.995 incl. polygon areas
    if k == "area_unit":
        us = [u for u in units if (u.get("label") or "").upper() == intent["label"]]
        if not us:
            return None
        ids = set(sum((u["room_ids"] for u in us), []))
        rs = [r for r in rooms if r["id"] in ids]
        # calibrated on train: unnamed rooms WITH a room number are real rooms (bathrooms whose name is not printed);
        # unnamed and unnumbered polygons are shafts. Outdoor spaces are excluded by name.
        inc = [r for r in rs if (r.get("name") or r.get("number")) and not r.get("is_outdoor")]
        flags = []
        # unnamed numbered rooms that contain sanitary symbols are bathrooms (included in gold 110/114 on train);
        # without symbols it is a coin flip (172 in / 101 out) -> needs check
        if any(not r.get("name") and r.get("number") and not _has_symbols(doc, r) for r in inc):
            flags.append("unnamed_numbered_room")
        if not inc:
            return None
        return _res(round(sum(r["area_m2"] for r in inc), 2), "m2", inc, "apartment_area", flags=flags)
    if k == "area_label":
        rs = [r for r in rooms if (r.get("name") or "").lower() == intent["label"].lower()]
        if not rs:
            return None
        return _res(round(sum(r["area_m2"] for r in rs), 2), "m2", rs, "label_area")
    if k == "area_floor_numbered":
        has_num = any(r.get("number") for r in rooms)
        rs = [r for r in rooms if (r.get("number") or not has_num) and not r.get("is_outdoor") and not r.get("is_shaft")]
        flags = []
        if any(not r.get("name") and not _has_symbols(doc, r) for r in rs):
            flags.append("unnamed_numbered_room")
        # common areas (stairs, lifts, corridors outside apartments) without a printed area: gold differs from our
        # polygon area in about 1/4 of floors (train) -> needs check
        # (a separate "unprinted common-area" flag was tested on train: 177/178 correct -> not needed)
        return _res(round(sum(r["area_m2"] for r in rs), 2), "m2", rs, "floor_area", flags=flags)
    if k == "count_rooms_labelled":
        rs = [r for r in rooms if (r.get("name") or "").lower() == intent["label"].lower()]
        return _res(len(rs), "count", rs, "rooms_labelled")
    if k == "count_windows":
        ws = doc.get("windows", [])
        f = (doc.get("facts") or {}).get("window_count")
        n = f["value"] if f else sum(w.get("count", 1) for w in ws)
        return _res(n, "count", ws, "windows")
    if k == "count_doors":
        return _res(len(doc.get("doors", [])), "count", doc.get("doors", []), "doors")
    if k == "count_units":
        us = [u for u in units if u.get("label")] or units
        return _res(len(us), "count", us, "units")
    if k == "count_symbol":
        kinds = {"showers_baths": {"shower", "bathtub"}, "sink": {"sink", "washbasin"}}.get(intent["symbol"], {intent["symbol"]})
        ss = [s for s in doc.get("symbols", []) if s["kind"] in kinds]
        return _res(len(ss), "count", ss, f"symbols:{intent['symbol']}")
    if k == "count_saunas":
        ss = [s for s in doc.get("symbols", []) if s["kind"] == "sauna_stove"]
        rs = [r for r in rooms if r.get("type") == "sauna"]
        use = rs if len(rs) > len(ss) else ss
        return _res(len(use), "count", use, "saunas")
    if k == "count_room_type":
        rs = [r for r in rooms if r.get("type") == intent["type"]]
        return _res(len(rs), "count", rs, f"rooms:{intent['type']}")
    if k == "count_floors":
        f = (doc.get("facts") or {}).get("floor_count")
        if not f:
            return None
        return {"value": f["value"], "unit": "count", "evidence": [], "rule": "floors",
                "confidence": f.get("provenance", {}).get("confidence", 1.0), "flags": []}
    return None


# --------------------------------------------------------------------------------------------------------------
# Rule reliability, measured on TRAIN+VAL with scripts/route_errors.py (never test). Flags that mark an ambiguous
# case lower the confidence below the auto-answer threshold so the router returns "needs check" instead.
FLAG_CONF = {"unnamed_numbered_room": 0.5, "unprinted_area": 0.6}


def doc_for(q_path):
    src = q_path.split("/")[1]
    if src == "swiss_dwellings":
        from .convert.swiss_dxf import for_question_path
        return for_question_path(q_path)
    if src == "ifc_models":
        from .convert.ifc_std import for_question_path
        return for_question_path(q_path)
    return None


def answer_std(q_path, question, doc=None):
    doc = doc or doc_for(q_path)
    if doc is None:
        return {"value": None, "abstain_reason": "no standardized file"}
    if doc["drawing_id"].startswith("ifc_models/"):
        from .convert.ifc_std import answer_ifc_std
        return answer_ifc_std(doc, q_path, question)
    intent = parse_intent(question)
    r = query(doc, intent)
    if r is None:
        return {"value": None, "abstain_reason": f"intent {intent['kind']} not answerable from file", "intent": intent}
    conf = r["confidence"]
    for f in r["flags"]:
        conf = min(conf, FLAG_CONF.get(f, 0.5))
    return {"value": r["value"], "unit": r["unit"], "evidence": r["evidence"], "confidence": conf,
            "flags": r["flags"], "method": f"std:{doc['producer']['kind']}:{r['rule']}", "intent": intent,
            "drawing_id": doc["drawing_id"], "ground_truth_eligible": doc["ground_truth_eligible"]}
