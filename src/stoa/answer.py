"""Answer questions from a standardized drawing file (schema/drawing.schema.json), deterministically.

  intent = parse_intent(question)            # language-agnostic regexes (EN/DE/FR/IT/FI templates of the dataset)
  result = query(doc, intent)                # value + evidence items + confidence + flags

Confidence = min(provenance confidence of the items used). Area rules (scripts/area_errors.py, TRAIN/VAL only):
room 1.000/1.000, label 1.000/1.000, apartment 0.9993/1.000, floor 1.000/1.000 (train/val).
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


def _conf(items):
    cs = [it.get("provenance", {}).get("confidence", 1.0) for it in items]
    return round(min(cs) if cs else 1.0, 4)


def _res(value, unit, items, rule):
    return {"value": value, "unit": unit, "evidence": _ev(items), "rule": rule, "confidence": _conf(items), "flags": []}


def query(doc, intent):
    k = intent["kind"]
    rooms, units = doc.get("rooms", []), doc.get("units", [])
    if k == "area_room_number":
        rs = [r for r in rooms if (r.get("number") or "") == intent["number"]]
        if len(rs) != 1:
            return None
        return _res(round(rs[0]["area_m2"], 2), "m2", rs, "room_area")
    if k == "area_unit":
        us = [u for u in units if (u.get("label") or "").upper() == intent["label"]]
        if not us:
            return None
        ids = set(sum((u["room_ids"] for u in us), []))
        rs = [r for r in rooms if r["id"] in ids]
        # numbered indoor rooms; the indoor/outdoor category comes from the render fill (swiss_render.py)
        inc = [r for r in rs if r.get("number") and not r.get("is_outdoor")]
        if not inc:
            return None
        return _res(round(sum(r["area_m2"] for r in inc), 2), "m2", inc, "apartment_area")
    if k == "area_label":
        rs = [r for r in rooms if (r.get("name") or "").lower() == intent["label"].lower()]
        if not rs:
            return None
        return _res(round(sum(r["area_m2"] for r in rs), 2), "m2", rs, "label_area")
    if k == "area_floor_numbered":
        rs = [r for r in rooms if r.get("number") and not r.get("is_outdoor") and not r.get("is_shaft")]
        return _res(round(sum(r["area_m2"] for r in rs), 2), "m2", rs, "floor_area")
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
        if any(r.get("name") for r in rooms):
            # exact files (swiss DXF) type only some rooms: classify the printed room NAMES from the file too
            from .text.measure import LEXICON
            def typ(r):
                toks = [LEXICON.get(t.upper()) for t in re.findall(r"[A-Za-zÄÖÅäöåÉéÜü]+", r.get("name") or "")]
                return r.get("type") or next((t for t in toks if t), None)
            rs = [r for r in rooms if typ(r) == intent["type"]]
            return _res(len(rs), "count", rs, f"rooms_by_name:{intent['type']}")
        rs = [r for r in rooms if r.get("type") == intent["type"]]
        return _res(len(rs), "count", rs, f"rooms:{intent['type']}")
    if k == "count_floors":
        f = (doc.get("facts") or {}).get("floor_count")
        if not f:
            return None
        return {"value": f["value"], "unit": "count", "evidence": [], "rule": "floors",
                "confidence": f.get("provenance", {}).get("confidence", 1.0), "flags": []}
    return None


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
    return {"value": r["value"], "unit": r["unit"], "evidence": r["evidence"], "confidence": r["confidence"],
            "flags": r["flags"], "method": f"std:{doc['producer']['kind']}:{r['rule']}", "intent": intent,
            "drawing_id": doc["drawing_id"], "ground_truth_eligible": doc["ground_truth_eligible"]}
