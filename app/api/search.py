"""Drawing search: "which drawings have 3 bedrooms and a sauna", "kolme makuuhuonetta ja sauna", "Helsinki 1909".

Numeric constraints are parsed with a small EN/FI/DE lexicon and matched against per-drawing facts (our system's
answers on the held-out TEST set, exact DXF facts for swiss floors); the remaining words are matched against titles
and the historic context fields.
"""
import functools, json, os, re
from . import config as C

LEX = [  # fact key, regex for the noun (EN / FI / DE)
    ("bedrooms", r"bed ?rooms?|makuuhuone\w*|\bmh\b|schlafzimmer\w*|chambres?"),
    ("saunas", r"saunas?|saunalli\w*|saunaa?\b"),
    ("toilets", r"toilets?|wcs?\b|wc-istui\w*|vessa\w*"),
    ("bathrooms", r"bath ?rooms?|washrooms?|kylpyhuone\w*|pesuhuone\w*"),
    ("kitchens", r"kitchens?|keittiö\w*|küchen?"),
    ("balconies", r"balcon(?:y|ies)|parveke\w*|balkon\w*"),
    ("windows", r"windows?|ikkun\w*|fenster"),
    ("doors", r"doors?|ov(?:ea|ia|et|i)\b|türen?"),
    ("apartments", r"apartments?|flats?|asun\w*|wohnung\w*|units?"),
    ("floors", r"floors?|storeys?|kerro\w*"),
    ("showers_baths", r"showers?|bathtubs?|suihku\w*|amme\w*"),
]
NUMW = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "yksi": 1, "kaksi": 2, "kolme": 3,
        "neljä": 4, "viisi": 5, "kuusi": 6, "ein": 1, "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "single": 1}
STOP = set("which what drawings drawing plans plan floor show shows me with and or the of in a an has have having that is "
           "are find all any on for from ja jossa joissa on kanssa piirustukset mitkä näytä und mit die der".split())
SRC_WORDS = {"historic": ("habs", "finna", "europeana", "wikimedia"), "swiss": ("swiss_dwellings",), "cubicasa": ("cubicasa5k",),
             "ifc": ("ifc_models",), "bim": ("ifc_models",), "finnish": ("cubicasa5k", "finna")}


@functools.lru_cache(maxsize=1)
def index():
    if not os.path.exists(C.SEARCH_INDEX):
        return []
    return json.load(open(C.SEARCH_INDEX, encoding="utf-8"))["docs"]


def parse(q):
    t = " " + q.lower() + " "
    cons, used = [], []
    for key, noun in LEX:
        num = r"(\d+|" + "|".join(NUMW) + r")"
        m = re.search(r"(at least|min(?:imum)?|vähintään|mindestens|>=?)?\s*\b" + num + r"\s*(\+)?\s*(?:or more\s+)?(?:\w+\s+)?(" + noun + r")", t)
        neg = re.search(r"(no|without|ilman|ohne|zero|0)\s+(" + noun + r")", t)
        if neg:
            cons.append({"key": key, "op": "=", "value": 0, "text": neg.group(0).strip()})
            used.append(neg.group(0))
        elif m and (m.group(2).isdigit() or m.group(2) in NUMW):
            v = int(m.group(2)) if m.group(2).isdigit() else NUMW[m.group(2)]
            op = ">=" if (m.group(1) or m.group(3) or "or more" in m.group(0)) else "="
            if m.group(2) in ("a", "an") or key == "saunas" and v == 1 and not m.group(2).isdigit():
                op = ">="
            cons.append({"key": key, "op": op, "value": v, "text": m.group(0).strip()})
            used.append(m.group(0))
        else:
            m2 = re.search(r"(" + noun + r")", t)
            if m2:
                cons.append({"key": key, "op": ">=", "value": 1, "text": m2.group(0).strip()})
                used.append(m2.group(0))
    rest = t
    for u in used:
        rest = rest.replace(u, " ")
    words = [w for w in re.findall(r"[\wäöåüéè-]+", rest) if w not in STOP and len(w) > 1 and w not in NUMW]
    srcs = set()
    for w in list(words):
        if w in SRC_WORDS:
            srcs.update(SRC_WORDS[w])
            words.remove(w)
    years = [int(w) for w in words if re.fullmatch(r"1[5-9]\d\d|20[0-2]\d", w)]
    return {"constraints": cons, "words": words, "sources": sorted(srcs), "years": years}


def _ok(f, c):
    if f is None:
        return False
    v = f["value"]
    return v == c["value"] if c["op"] == "=" else v >= c["value"]


def search(q, limit=40, source=None):
    p = parse(q or "")
    res = []
    for d in index():
        if source and d["source"] != source:
            continue
        if p["sources"] and d["source"] not in p["sources"]:
            continue
        score, matched = 0.0, []
        if p["constraints"]:
            facts = d.get("facts") or {}
            if not all(_ok(facts.get(c["key"]), c) for c in p["constraints"]):
                continue
            conf = min((facts[c["key"]].get("confidence") or 0) for c in p["constraints"])
            score += 10 + conf
            matched = [{"key": c["key"], "value": facts[c["key"]]["value"], "confidence": facts[c["key"]].get("confidence"),
                        "method": facts[c["key"]].get("method"), "uncertain": (facts[c["key"]].get("confidence") or 0) < C.CONF_AUTO}
                       for c in p["constraints"]]
        text = (d.get("text") or "").lower()
        if p["words"]:
            hits = sum(1 for w in p["words"] if w in text)
            if hits == 0 and not p["constraints"]:
                continue
            score += 3 * hits / len(p["words"])
        if p["years"]:
            ys = d.get("years") or []
            if any(y in ys for y in p["years"]):
                score += 2
            elif not p["constraints"] and not any(str(y) in text for y in p["years"]):
                continue
        if not p["constraints"] and not p["words"] and not p["years"] and not p["sources"]:
            continue
        score += 0.5 if d.get("featured") else 0
        res.append({"id": d["id"], "source": d["source"], "title": d.get("title"), "split": d.get("split"),
                    "featured": bool(d.get("featured")), "score": round(score, 3), "matched": matched,
                    "facts": d.get("facts") or {}})
    res.sort(key=lambda r: -r["score"])
    return {"query": q, "parsed": p, "total": len(res), "results": res[:limit],
            "index_note": "Facts = our system's answers on held-out TEST drawings (exact DXF facts for swiss floors); "
                          "historic = archive-record context fields. Facts below confidence 0.7 are marked uncertain."}
