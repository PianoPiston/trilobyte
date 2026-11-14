"""Deterministic reading of printed text: room labels, areas, totals, scale, and text-based answers.

Inputs are only the words of the drawing (PDF vector text or OCR) and, optionally, detector room boxes.
Scope rules (never relaxed):
  * a room's printed area answers only questions about that room (type or label)
  * a whole-apartment / floor total comes only from an explicit total text ("yht.", "huoneisto", "total",
    "h+k+s ... m²", "as.", "kerrosala", "Wohnfläche") or, with scope "sum_of_rooms", from an explicitly labelled
    sum of all printed room areas (lower confidence, needs check)
  * a single room's number is never returned as the total
  * several rooms with the same label -> per-room list + ambiguity flag (sum only when the question asks for all)
"""
import math, re

# label token (upper, letters only) -> room type
LEXICON = {
    # Finnish (abbreviations as printed on Finnish apartment plans)
    "MH": "bedroom", "MAKUUHUONE": "bedroom", "MAKUUH": "bedroom", "MAK": "bedroom",
    "OH": "living", "OLOHUONE": "living", "OLOH": "living", "TUPA": "living",
    "K": "kitchen", "KK": "kitchen", "KT": "kitchen", "AK": "kitchen", "KEITTIÖ": "kitchen", "KEITTIO": "kitchen",
    "KEITTOKOMERO": "kitchen", "TUPAKEITTIÖ": "kitchen",
    "KPH": "bath", "PH": "bath", "KH": "bath", "PESUH": "bath", "PSH": "bath", "SH": "bath", "PESUHUONE": "bath", "KYLPYHUONE": "bath",
    "WC": "wc", "S": "sauna", "SAUNA": "sauna", "LH": "sauna",
    "ET": "hall", "ETEINEN": "hall", "E": "hall", "AULA": "hall", "KÄYTÄVÄ": "hall", "TK": "vestibule", "TUULIKAAPPI": "vestibule",
    "VH": "closet", "VAATEHUONE": "closet", "VAR": "storage", "VARASTO": "storage", "IV": "technical", "TEKN": "technical",
    "PUKU": "dressing", "PUKUH": "dressing", "PUKUHUONE": "dressing",
    "PARV": "balcony", "PARVEKE": "balcony", "LASITETTU": "balcony", "TERASSI": "terrace", "TER": "terrace",
    "KHH": "utility", "KODINHOITOHUONE": "utility", "TH": "study", "TYÖHUONE": "study", "TYOHUONE": "study",
    "RT": "dining", "RH": "dining", "RUOKAILU": "dining", "RUOKAILUTILA": "dining", "ULLAKKO": "attic",
    "AUTOTALLI": "garage", "AT": "garage", "KATOS": "carport", "AUTOKATOS": "carport",
    # English
    "BEDROOM": "bedroom", "BED": "bedroom", "BR": "bedroom", "LIVING": "living", "LOUNGE": "living", "KITCHEN": "kitchen",
    "KITCHENETTE": "kitchen", "BATH": "bath", "BATHROOM": "bath", "SHOWER": "bath", "TOILET": "wc", "LAV": "wc",
    "HALL": "hall", "HALLWAY": "hall", "CORRIDOR": "hall", "ENTRY": "hall", "BALCONY": "balcony", "TERRACE": "terrace",
    "STORAGE": "storage", "CLOSET": "closet", "DINING": "dining", "UTILITY": "utility", "LAUNDRY": "utility", "STUDY": "study",
    "OFFICE": "study", "GARAGE": "garage", "BUERO": "study", "BÜRO": "study",
    # German / French / Italian (Swiss plans)
    "SCHLAFZIMMER": "bedroom", "ZIMMER": "room", "WOHNEN": "living", "WOHNZIMMER": "living", "KÜCHE": "kitchen",
    "KUCHE": "kitchen", "BAD": "bath", "DUSCHE": "bath", "BALKON": "balcony", "LOGGIA": "balcony", "KORRIDOR": "hall",
    "FLUR": "hall", "ENTREE": "hall", "ENTRÉE": "hall", "REDUIT": "storage", "ABSTELLRAUM": "storage", "ESSEN": "dining",
    "TERRASSE": "terrace", "CHAMBRE": "bedroom", "SÉJOUR": "living", "SEJOUR": "living", "SALON": "living", "CUISINE": "kitchen",
    "SDB": "bath", "BALCON": "balcony", "CAMERA": "bedroom", "SOGGIORNO": "living", "CUCINA": "kitchen", "BAGNO": "bath",
}
SHORT_RISKY = {"K", "S", "E", "AT", "LH", "TER", "BED", "BR", "LAV", "MAK", "KT", "AK", "RH", "TH"}  # need a clean OCR read
# question words -> room type (EN/FI/DE/FR/IT), checked on the lower-cased question
Q_ROOM = [
    ("bedroom", r"bedroom|makuuhuone|schlafzimmer|chambre|camera da letto|\bmh\b"),
    ("living", r"living room|olohuone|wohnzimmer|wohnen|séjour|salon|soggiorno|\boh\b"),
    ("kitchen", r"kitchen|keittiö|keittokomero|küche|cuisine|cucina"),
    ("bath", r"bathroom|washroom|kylpyhuone|pesuhuone|\bkph\b|badezimmer|\bbad\b|salle de bain|bagno"),
    ("wc", r"\bwc\b|toilet room"),
    ("sauna", r"sauna"),
    ("balcony", r"balcon|parveke|balkon|loggia"),
    ("terrace", r"terrace|terassi|terrasse"),
    ("hall", r"\bhall\b|hallway|corridor|eteinen|korridor|flur|entrée|entree"),
    ("storage", r"storage|varasto|reduit|abstellraum"),
    ("closet", r"walk-in closet|vaatehuone|closet"),
    ("utility", r"utility|laundry|kodinhoitohuone|\bkhh\b"),
    ("dining", r"dining|ruokailu"),
    ("study", r"study|office|työhuone"),
    ("garage", r"garage|autotalli"),
]
TOTAL_TXT = re.compile(r"\b(yht\.?|yhteensä|huoneisto(ala)?|asuinpinta-?ala|as\.|kerrosala|kokonaisala|total|wohnfläche|"
                       r"surface habitable|superficie)\b|(\d\s*(h|mh|r)\s*\+\s*(k|kk|kt|ak|tk)\b)", re.I)
Q_TOTAL = re.compile(r"total|whole|entire|overall|apartment area|floor area|living area|net area|yhteens|koko|huoneisto|"
                     r"asuinpinta|kerrosala|gesamt|wohnfläche|surface totale|superficie totale|in total", re.I)
NUM = r"(\d{1,4}(?:[  ]?\d{3})*(?:[.,]\d{1,2})?)"
AREA_RE = re.compile(NUM + r"\s*(m²|m2|m\^2|m 2|qm|sqm|sq\.? ?m|neliö|ft²|ft2|sq\.? ?ft)(?![a-z])", re.I)
VOL_RE = re.compile(NUM + r"\s*(m³|m3|m\^3)(?![a-z])", re.I)
LEN_RE = re.compile(NUM + r"\s*(mm|cm|m)(?![a-z²³23])", re.I)
SCALE_RE = re.compile(r"(?<![\d.,])1\s*:\s*(\d{1,4})(?![\d.,])")


def _num(s):
    s = s.replace(" ", "").replace(" ", "")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _h(b):
    return max(4.0, min(b[3] - b[1], b[2] - b[0]) if (b[3] - b[1]) > 2.5 * (b[2] - b[0]) else b[3] - b[1])


def lines_of(words):
    """merge words into text lines (PDF words carry a line id; OCR boxes already are lines)"""
    if not any("line" in w for w in words):
        return [dict(w) for w in words]
    by = {}
    for w in words:
        by.setdefault(w.get("line", id(w)), []).append(w)
    out = []
    for ws in by.values():
        ws.sort(key=lambda w: w["bbox"][0])
        out.append({"text": " ".join(w["text"] for w in ws), "conf": min(w["conf"] for w in ws),
                    "bbox": [min(w["bbox"][0] for w in ws), min(w["bbox"][1] for w in ws),
                             max(w["bbox"][2] for w in ws), max(w["bbox"][3] for w in ws)]})
    return out


def _label_tokens(text):
    toks = re.findall(r"[A-Za-zÄÖÅäöåÉéÜü]+", text)
    out = []
    for t in toks:
        u = t.upper()
        if u in LEXICON:
            out.append(u)
    return out


def parse(words, room_boxes=None):
    """-> {labels, areas, totals, scales, lengths, volumes}; every item has bbox, text, conf (in image px)"""
    L = lines_of(words or [])
    labels, areas, totals, scales, lengths, volumes = [], [], [], [], [], []
    for i, ln in enumerate(L):
        t, b, c = ln["text"], ln["bbox"], float(ln.get("conf", 1.0))
        is_total = bool(TOTAL_TXT.search(t))
        for m in AREA_RE.finditer(t):
            v = _num(m.group(1))
            if v is None or v <= 0 or v > 100000:
                continue
            unit = "ft2" if "ft" in m.group(2).lower() else "m2"
            it = {"value": v, "unit": unit, "text": t, "bbox": b, "conf": c, "line": i}
            (totals if is_total else areas).append(it)
        for m in VOL_RE.finditer(t):
            v = _num(m.group(1))
            if v:
                volumes.append({"value": v, "unit": "m3", "text": t, "bbox": b, "conf": c})
        for m in SCALE_RE.finditer(t):
            n = int(m.group(1))
            if n in (1, 2, 5, 10, 20, 25, 50, 75, 100, 150, 200, 250, 500, 1000, 2000, 2500, 5000):
                scales.append({"value": f"1:{n}", "denominator": n, "text": t, "bbox": b, "conf": c})
        if not AREA_RE.search(t):
            for m in LEN_RE.finditer(t):
                v = _num(m.group(1))
                if v:
                    lengths.append({"value": v, "unit": m.group(2).lower(), "text": t, "bbox": b, "conf": c})
        toks = _label_tokens(t)
        for u in toks:
            if u in SHORT_RISKY and (c < 0.75 or len(re.sub(r"[^A-Za-zÄÖÅäöå]", "", t)) != len(u)):
                continue  # single letters / short codes only when they are the whole word and read cleanly
            labels.append({"label": u, "type": LEXICON[u], "text": t, "bbox": b, "conf": c, "line": i})
    # an area printed on the same line as a label belongs to it; otherwise nearest label below/above/right
    _assign(labels, areas, room_boxes)
    return {"labels": labels, "areas": areas, "totals": totals, "scales": scales, "lengths": lengths, "volumes": volumes}


def _room_of(pt, room_boxes):
    best = None
    for rb in room_boxes or []:
        x0, y0, x1, y1 = rb["bbox"]
        if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
            a = (x1 - x0) * (y1 - y0)
            if best is None or a < best[0]:
                best = (a, rb["id"])
    return best[1] if best else None


def _assign(labels, areas, room_boxes):
    pairs = []
    for ai, a in enumerate(areas):
        ac = _center(a["bbox"])
        ar = _room_of(ac, room_boxes)
        for li, l in enumerate(labels):
            if l["line"] == a["line"]:
                pairs.append((0.0, ai, li))
                continue
            lc = _center(l["bbox"])
            h = max(_h(l["bbox"]), _h(a["bbox"]))
            d = math.hypot((ac[0] - lc[0]) / 1.5, ac[1] - lc[1])  # areas usually sit under the label
            if d > 4.5 * h:
                continue
            if room_boxes and ar is not None and _room_of(lc, room_boxes) not in (ar, None):
                continue  # different detected room
            pairs.append((d / h, ai, li))
    pairs.sort()
    used_a, used_l = set(), set()
    for _, ai, li in pairs:
        if ai in used_a or li in used_l:
            continue
        used_a.add(ai); used_l.add(li)
        areas[ai]["label_idx"] = li
        labels[li]["area"] = areas[ai]["value"]
        labels[li]["area_unit"] = areas[ai]["unit"]
        labels[li]["area_bbox"] = areas[ai]["bbox"]


def label_score(words):
    """orientation check: how much of the text reads as plan vocabulary (labels, areas, scale)"""
    s = 0.0
    for ln in lines_of(words):
        t = ln["text"]
        n = len(_label_tokens(t)) + len(AREA_RE.findall(t)) + len(SCALE_RE.findall(t))
        s += n * float(ln.get("conf", 1.0))
    return s


# ------------------------------------------------------------------------------------------------ question -> text answer
def q_room_type(question):
    t = question.lower()
    for typ, pat in Q_ROOM:
        if re.search(pat, t):
            return typ
    return None


def text_intent(question):
    """intent for the text route (independent of the dataset templates): area / count / scale + scope"""
    t = question.lower()
    from ..answer import parse_intent, quoted
    base = parse_intent(question)
    if re.search(r"\bscale\b|mittakaava|maßstab|massstab|échelle|scala", t):
        return {"kind": "scale", "scope": "drawing"}
    if re.search(r"baseboard|skirting|jalkalist|sockelleist|plinthe|linear met|juoksumet|perimeter", t):
        return {"kind": "length", "scope": "unsupported"}
    is_area = bool(re.search(r"m²|m2\b|area|fläche|surface|superficie|pinta-ala|neliö|square met|how (big|large)|kuinka (iso|suuri)", t))
    if is_area:
        lab = quoted(question)
        rt = q_room_type(question)
        if base.get("kind") in ("area_room_number", "area_unit", "area_floor_numbered"):
            return {"kind": "area", "scope": "other:" + base["kind"], "base": base}
        if lab:
            return {"kind": "area", "scope": f"room:label:{lab.upper()}", "label": lab, "type": LEXICON.get(lab.upper())}
        if rt and not re.search(r"all (the )?" + r"|every|each|kaikki", t) and not Q_TOTAL.search(t.replace(rt, "")):
            return {"kind": "area", "scope": f"room:{rt}", "type": rt}
        if rt:
            return {"kind": "area", "scope": f"rooms_sum:{rt}", "type": rt}
        if Q_TOTAL.search(t) or re.search(r"apartment|asunno|dwelling|flat|unit|floor", t):
            return {"kind": "area", "scope": "total"}
        return {"kind": "area", "scope": "unknown"}
    if base["kind"] == "count_room_type":
        return {"kind": "count_rooms", "scope": f"count:{base['type']}", "type": base["type"]}
    if base["kind"] == "count_saunas":
        return {"kind": "count_rooms", "scope": "count:sauna", "type": "sauna"}
    if re.search(r"how many|kuinka monta|montako|wie viele|combien|quant", t):
        rt = q_room_type(question)
        if rt and re.search(r"room|huone|zimmer|pièce|stanz|\b" + rt, t) and base["kind"] in ("unknown", "count_rooms_labelled"):
            return {"kind": "count_rooms", "scope": f"count:{rt}", "type": rt}
    return {"kind": base["kind"], "scope": "count:" + base["kind"], "base": base}


TYPE_MATCH = {"bath": {"bath"}, "wc": {"wc"}, "kitchen": {"kitchen"}, "bedroom": {"bedroom"}, "balcony": {"balcony"},
              "sauna": {"sauna"}}


def _ev(items, kind="text"):
    out = []
    for i, it in enumerate(items):
        e = {"id": f"T{i}", "kind": kind, "label": f"printed “{it['text'][:60]}”", "bbox": [round(v, 1) for v in it["bbox"]]}
        out.append(e)
    return out


def answer_from_text(parsed, intent):
    """-> list of candidates {value, unit, scope, confidence, reason, evidence, rule} (may be empty)"""
    k, scope = intent["kind"], intent.get("scope", "")
    labels, cands = parsed["labels"], []
    if k == "scale":
        ss = sorted(parsed["scales"], key=lambda s: -s["conf"])
        if ss:
            vals = {s["value"] for s in ss}
            conf = 0.9 * ss[0]["conf"] if len(vals) == 1 else 0.5
            cands.append({"value": ss[0]["value"], "unit": "text", "scope": "drawing", "confidence": round(conf, 3), "rule": "text:scale",
                          "reason": f"scale printed on the drawing ({', '.join(sorted(vals))})", "evidence": _ev(ss[:4])})
        return cands
    if k == "count_rooms":
        typ = intent["type"]
        ls = [l for l in labels if l["type"] in TYPE_MATCH.get(typ, {typ})]
        n = len(ls)
        # a label count is a good signal only when labels exist at all on the plan
        if not labels:
            return cands
        conf = (0.75 if n else 0.55) * (min([l["conf"] for l in ls]) if ls else 1.0)
        cands.append({"value": n, "unit": "count", "scope": scope, "confidence": round(conf, 3), "rule": f"text:label_count:{typ}",
                      "reason": f"{n} printed {typ} label{'s' if n != 1 else ''} ({', '.join(sorted({l['label'] for l in ls})) or 'none'})"
                      f" among {len(labels)} room labels",
                      "evidence": _ev(ls, "label")})
        if typ == "bedroom":  # "3h+k+s": 3 rooms = living room + 2 bedrooms
            for t in parsed["totals"] + [{"text": l["text"], "bbox": l["bbox"], "conf": l["conf"]} for l in labels]:
                m = re.search(r"\b(\d)\s*(h|mh|r)\s*\+\s*(k|kk|kt|ak|tk)", t["text"], re.I)
                if m:
                    nb = int(m.group(1)) - 1 if m.group(2).lower() in ("h", "r") else int(m.group(1))
                    cands.append({"value": nb, "unit": "count", "scope": scope, "confidence": 0.6, "rule": "text:room_formula",
                                  "reason": f"room formula “{m.group(0)}” (living room + {nb} bedrooms)", "evidence": _ev([t])})
                    break
        return cands
    if k != "area":
        return cands
    if scope.startswith("room:"):
        if scope.startswith("room:label:"):
            want = intent["label"].upper()
            ls = [l for l in labels if l["label"] == want or l["text"].strip().upper() == want]
        else:
            ls = [l for l in labels if l["type"] == intent["type"]]
        with_area = [l for l in ls if l.get("area") is not None]
        if not with_area:
            return cands
        if len(with_area) == 1:
            l = with_area[0]
            cands.append({"value": round(l["area"], 2), "unit": l["area_unit"], "scope": scope,
                          "confidence": round(0.92 * l["conf"] * (0.9 if len(ls) > 1 else 1.0), 3), "rule": "text:room_area",
                          "reason": f"area printed in the {l['label']} room", "evidence": _ev([l, {"text": f"{l['area']} m²", "bbox": l["area_bbox"]}])})
        else:  # several rooms share the label: list per room, flag ambiguity
            vals = [round(l["area"], 2) for l in with_area]
            cands.append({"value": vals, "unit": with_area[0]["area_unit"], "scope": scope, "confidence": 0.5, "rule": "text:room_area_list",
                          "flags": ["ambiguous_room_label"],
                          "reason": f"{len(vals)} rooms are labelled {with_area[0]['label']}: one area each",
                          "evidence": _ev([{"text": f"{l['label']} {l['area']} m²", "bbox": l["area_bbox"]} for l in with_area])})
        return cands
    if scope.startswith("rooms_sum:"):
        ls = [l for l in labels if l["type"] == intent["type"] and l.get("area") is not None]
        if ls:
            cands.append({"value": round(sum(l["area"] for l in ls), 2), "unit": ls[0]["area_unit"], "scope": scope,
                          "confidence": 0.7 * min(l["conf"] for l in ls), "rule": "text:rooms_sum",
                          "reason": f"sum of the printed areas of {len(ls)} {intent['type']} room(s)",
                          "evidence": _ev([{"text": f"{l['label']} {l['area']} m²", "bbox": l["area_bbox"]} for l in ls])})
        return cands
    if scope == "total":
        tots = sorted(parsed["totals"], key=lambda x: -x["value"])
        if tots:
            vals = sorted({x["value"] for x in tots})
            t = tots[0]
            cands.append({"value": round(t["value"], 2), "unit": t["unit"], "scope": "total",
                          "confidence": round((0.9 if len(vals) == 1 else 0.6) * t["conf"], 3), "rule": "text:total",
                          "flags": [] if len(vals) == 1 else ["several_totals"],
                          "reason": f"explicit total printed on the drawing: “{t['text'][:60]}”", "evidence": _ev(tots[:3])})
        room_areas = [a for a in parsed["areas"] if a.get("label_idx") is not None]
        if len(room_areas) >= 2:
            s = round(sum(a["value"] for a in room_areas), 2)
            cands.append({"value": s, "unit": room_areas[0]["unit"], "scope": "total", "confidence": 0.45, "rule": "text:sum_of_rooms",
                          "flags": ["sum_of_printed_room_areas"],
                          "reason": f"sum of {len(room_areas)} printed room areas (labelled sum, not a printed total)",
                          "evidence": _ev(room_areas)})
        return cands
    return cands


def room_type_of_name(name):
    """room type of a room NAME from an exact file (DXF/IFC), via the same label lexicon"""
    for t in re.findall(r"[A-Za-zÄÖÅäöåÉéÜüß]+", name or ""):
        typ = LEXICON.get(t.upper())
        if typ:
            return typ
    return None


def expected_unit(intent):
    k = intent.get("kind")
    if k == "scale":
        return "text"
    if k == "area":
        return "area"
    if k == "count_rooms":
        return "count"
    return None
