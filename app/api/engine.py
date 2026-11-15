"""The product's question-answering pipeline (shared by the HTTP API and the MCP server).

ask(drawing_id, question) tries, in order:
  1. historic context   (habs/finna/europeana/wikimedia metadata questions -> archive record field + source URL)
  2. standardized file  (swiss DXF / IFC -> exact, deterministic; stoa.answer.answer_std)
  3. legacy exact route (stoa.methods.swiss_dxf / ifc_route, if the standardized file abstained)
  4. detector file      (model-derived standardized file in STOA_STD_DIR, e.g. cubicasa detector output)
  5. live VLM           (fine-tuned Qwen3.5-4B LoRA + base-model grounding boxes), if the endpoint is up
  6. answer cache       (precomputed answers from the eval runs / earlier live calls) -> method "cache"
  7. otherwise abstain with needs_check (never a hard failure)
Every answer is mapped to the pixel frame of the image the UI shows (see geometry.py).
"""
import asyncio, json, os, re, time, threading
from . import config as C
from . import catalog as CAT
from . import geometry as G
from .vlm_client import VLM

METHOD_LABEL = {"dxf-exact": "Exact from CAD (DXF)", "ifc-exact": "Exact from IFC model", "detector": "Symbol detector",
                "vlm": "AI model (fine-tuned VLM)", "cache": "Cached AI answer", "context": "Archive record", "text": "Printed text on the drawing", "none": "No answer"}
_lock = threading.Lock()


def norm_q(q):
    return re.sub(r"\s+", " ", (q or "").strip().lower())


# ------------------------------------------------------------------------------------------------ caches
class AnswerCache:
    def __init__(self):
        self.d = {}
        for fn in (C.ANSWER_CACHE, C.LIVE_CACHE):
            if os.path.exists(fn):
                for line in open(fn, encoding="utf-8"):
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    self.d[(r["q_path"], norm_q(r["question"]))] = r

    def get(self, q_path, question):
        return self.d.get((q_path, norm_q(question)))

    def put_live(self, q_path, question, resp):
        rec = {"q_path": q_path, "question": question, "value": resp["answer"], "unit": resp.get("unit"),
               "confidence": resp.get("confidence"), "method": resp["method"], "evidence": resp.get("evidence", []),
               "origin": "live", "at": time.strftime("%Y-%m-%d %H:%M")}
        with _lock:
            self.d[(q_path, norm_q(question))] = rec
            with open(C.LIVE_CACHE, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")


CACHE = AnswerCache()


def _load_transforms():
    return json.load(open(C.TRANSFORMS)) if os.path.exists(C.TRANSFORMS) else {}


TRANSFORMS = _load_transforms()


def swiss_transform(d, doc):
    t = TRANSFORMS.get(d["id"])
    if t is None:
        img = CAT.image_file(d)
        t = G.register_swiss(img, doc)
        with _lock:
            TRANSFORMS[d["id"]] = t
            json.dump(TRANSFORMS, open(C.TRANSFORMS, "w"))
    return t


_SVG = {}


def ifc_svg_boxes(d):
    """GlobalId -> bbox in image px, for IFC plan sheets with an SVG next to the PDF"""
    if d["id"] in _SVG:
        return _SVG[d["id"]]
    res = {}
    svg = d["files"].get("svg")
    if svg:
        root = CAT._find_root(svg)
        vbox, boxes = G.svg_guid_boxes(os.path.join(root, svg))
        img = CAT.image_file(d)
        if vbox and img:
            size = CAT.image_size(img)
            res = {g: G.svg_to_px(vbox, size, b) for g, b in boxes.items()}
    _SVG[d["id"]] = res
    return res


# ------------------------------------------------------------------------------------------------ standardized files
def std_doc(d):
    """standardized drawing file (schema/drawing.schema.json) or None"""
    try:
        if d["source"] == "swiss_dwellings" and d["files"].get("dxf"):
            from stoa.convert.swiss_dxf import convert
            return convert(d["files"]["dxf"])
        if d["source"] == "ifc_models" and d["files"].get("ifc"):
            from stoa.convert.ifc_std import convert
            return convert(d["files"]["ifc"])
    except Exception as e:  # never let a converter crash the API
        return {"error": repr(e)[:300]}
    fn = os.path.join(C.STD_DIR, d["source"], d["stem"] + ".json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn))
        except Exception:
            return None
    return None


def _label(it):
    bits = []
    if it.get("label"):
        bits.append(f"Apartment {it['label']}")
    if it.get("name"):
        bits.append(str(it["name"]))
    if it.get("number") and it.get("number") != it.get("name"):
        bits.append(str(it["number"]))
    k = it.get("kind") or it.get("ifc_type")
    if not bits and k:
        bits.append(str(k).replace("Ifc", ""))
    if it.get("area_m2") is not None:
        bits.append(f"{it['area_m2']:.2f} m²")
    return " · ".join(bits) or it.get("id", "item")


def map_evidence(d, items, doc=None):
    """standardized/route evidence -> [{id, label, kind, polygon?|bbox?, element_id, ifc_global_id?}] in image px"""
    out = []
    if d["source"] == "swiss_dwellings":
        t = swiss_transform(d, doc or std_doc(d)) if items else None
        for it in items:
            poly = it.get("polygon") or it.get("polygon_dxf")
            e = {"id": it.get("id") or f"E{len(out)}", "element_id": it.get("id"), "label": _label(it), "kind": it.get("kind") or "room"}
            if poly and t:
                e["polygon"] = G.apply_M(t["M"], poly)
            out.append(e)
    elif d["source"] == "ifc_models":
        boxes = ifc_svg_boxes(d) if items else {}
        for it in items:
            g = it.get("ifc_global_id")
            e = {"id": it.get("id") or g, "element_id": g, "ifc_global_id": g, "label": _label(it),
                 "kind": (it.get("ifc_type") or "IfcSpace").replace("Ifc", "").lower()}
            if g in boxes:
                e["bbox"] = boxes[g]
            else:
                e["off_sheet"] = True  # element is on another storey / not drawn on this sheet
            out.append(e)
    else:
        for it in items:
            e = {"id": it.get("id") or f"E{len(out)}", "element_id": it.get("id"), "label": _label(it), "kind": it.get("kind") or "item"}
            g = it.get("geometry") or it
            if g.get("bbox_px"):
                e["bbox"] = g["bbox_px"]
            out.append(e)
    return out


# ------------------------------------------------------------------------------------------------ historic context route
CTX_INTENTS = [  # (regex over question, context field, answer kind)
    (r"architect|designed|designer|who drew|author|arkkitehti|suunnittel", "architect_or_author"),
    (r"\byear\b|\bwhen\b|vuo(si|nna)|milloin|dated?\b", "year"),
    (r"\bscale\b|mittakaava", "scale"),
    (r"what kind of drawing|type of drawing|drawing type|piirustustyyppi|millainen piirustus", "drawing_type"),
    (r"which (city|town|municipality|place)|where\b|missä|kaupung|paikkakun", "place"),
    (r"country|maa\b|valtio", "country"),
    (r"which (building|farm|house|church|bridge|ship|structure|property)|name of the (building|house)|mikä rakennus|minkä rakennuksen", "building"),
]


def _ctx_value(v):
    if isinstance(v, dict):
        return v.get("text") or v.get("name") or json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return ", ".join(_ctx_value(x) if not isinstance(x, dict) else (x.get("phrase") or x.get("level") or x.get("term") or "") for x in v)
    return str(v)


def context_answer(d, question):
    ctx = CAT.load_context(d["source"], d["stem"])
    if not ctx:
        return None
    t = question.lower()
    for pat, field in CTX_INTENTS:
        if re.search(pat, t):
            f = (ctx.get("fields") or {}).get(field)
            if not f or f.get("value") in (None, "", []):
                continue
            # metadata comes from the archive record, not from the image: correct for "which building" style
            # questions, but granularity (city vs state vs street) may differ -> below the auto-answer threshold
            # for place/drawing type, above it for record-exact fields
            conf = 0.9 if field in ("architect_or_author", "year", "building", "scale") else 0.65
            from urllib.parse import urlparse
            srcs = [{"label": f"{field.replace('_', ' ')} from {f.get('from', 'record')} · {urlparse(u).netloc}", "url": u}
                    for u in (f.get("src") or []) if str(u).startswith("http")]
            return {"value": _ctx_value(f["value"]), "unit": "text", "confidence": conf, "method": "context",
                    "method_detail": f"context:{field}", "evidence": [], "sources": srcs,
                    "note": "Answer read from the archive record of this drawing (cited), not from the image."}
    return None


# ------------------------------------------------------------------------------------------------ main entry
def _method_of(m):
    m = m or ""
    if ":ifc:" in m or m.startswith("ifc:"):
        return "ifc-exact"
    if m.startswith("std:exact") or m.startswith("dxf:"):
        return "dxf-exact"
    if m.startswith("std:model") or m.startswith("detector"):
        return "detector"
    if m.startswith("context"):
        return "context"
    return "vlm"


def reference_for(d, question):
    for ex in CAT.example_questions(d, limit=200):
        if norm_q(ex["question"]) == norm_q(question):
            return ex
    return None


def _check_ref(ref, value):
    """does the answer match the dataset label? (official tolerance; historic accept-lists)"""
    if ref is None or value is None:
        return None
    try:
        if ref.get("accept"):
            from stoa.context.score import is_correct as hist_ok
            return bool(hist_ok({"accept": ref["accept"], "qtype": ref.get("type")}, value))
        from stoa.scoring import is_correct
        return bool(is_correct(ref.get("type") or "count", value, ref["answer"]))
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ words layer (text route)
def words_path(d):
    return os.path.join(C.STD_DIR, d["source"], d["stem"] + ".words.json")


def _pdf_of(d):
    if d["source"] == "upload":
        p = os.path.join(os.path.dirname(d["files"]["png"]), "original.pdf")
        return p if os.path.exists(p) else None
    rel = d["files"].get("pdf")
    if rel:
        root = CAT._find_root(rel)
        return os.path.join(root, rel) if root else None
    return None


def words_for(d, compute=True):
    """words file of a drawing (PDF vector text or OCR), computed once and stored next to its standardized file"""
    if d["track"] == "historic":
        return None
    img = CAT.image_file(d)
    if not img:
        return None
    from stoa.text.words import load_or_extract
    try:
        return load_or_extract(words_path(d), img, _pdf_of(d), compute=compute)
    except Exception:
        return None


def text_candidates(d, question, doc=None):
    """printed-text candidates (deterministic). Reads only the drawing's words + detector room boxes."""
    from stoa.text.measure import parse, text_intent, answer_from_text
    intent = text_intent(question)
    w = words_for(d, compute=C.OCR_ON_ASK)
    if not w or not w.get("words"):
        return intent, [], w
    rooms = [{"id": r["id"], "bbox": r["geometry"]["bbox_px"]} for r in (doc or {}).get("rooms", [])
             if (r.get("geometry") or {}).get("bbox_px")] if doc and (doc.get("producer") or {}).get("kind") == "model" else None
    parsed = parse(w["words"], rooms)
    out = []
    how = "PDF vector text" if w.get("method") == "pdf" else "OCR"
    for c in answer_from_text(parsed, intent):
        out.append({**c, "source": "text", "source_label": f"Printed text ({how})", "method_detail": c.get("rule"),
                    "method": "text"})
    return intent, out, w


def _exact_by_name(d, doc, question, cands):
    """exact file rooms classified by their printed NAME (Schlafzimmer, Küche, MH ...):
    count of a room type, or the area of the single room of that type. Replaces a generic IfcSpace count."""
    from stoa.text.measure import text_intent, room_type_of_name
    ti = text_intent(question)
    rooms = [r for r in doc.get("rooms", []) if r.get("name")]
    if not rooms:
        return cands
    typed = [(r, r.get("type") or room_type_of_name(r.get("name"))) for r in rooms]
    from stoa.answer import _ev
    if ti["kind"] == "count_rooms":
        rs = [r for r, t in typed if t == ti["type"]]
        generic = [c for c in cands if c["source"] == "exact" and "count_IfcSpace" in str(c.get("method_detail"))]
        if generic or not any(c["source"] == "exact" for c in cands):
            cands = [c for c in cands if c not in generic]
            cands.append({"value": len(rs), "unit": "count", "confidence": 0.97, "source": "exact", "method": _method_of(
                "ifc:" if d["source"] == "ifc_models" else "dxf:"), "method_detail": f"std:exact:rooms_by_name:{ti['type']}",
                "evidence": map_evidence(d, _ev(rs), doc), "scope": ti["scope"], "sources": [],
                "reason": f"{len(rs)} room(s) named as {ti['type']} in the exact file ({', '.join(sorted({r['name'] for r in rs})) or 'none'})"})
    elif ti["kind"] == "area" and str(ti.get("scope", "")).startswith("room:") and not any(c["source"] == "exact" for c in cands):
        typ = ti.get("type")
        rs = [r for r, t in typed if typ and t == typ and r.get("area_m2") is not None]
        if len(rs) == 1:
            cands.append({"value": round(rs[0]["area_m2"], 2), "unit": "m2", "confidence": 0.97, "source": "exact",
                          "method": _method_of("ifc:" if d["source"] == "ifc_models" else "dxf:"),
                          "method_detail": f"std:exact:room_area_by_name:{typ}", "evidence": map_evidence(d, _ev(rs), doc),
                          "scope": ti["scope"], "sources": [], "reason": f"area of the room named {rs[0]['name']} in the exact file"})
        elif len(rs) > 1:
            cands.append({"value": [round(r["area_m2"], 2) for r in rs], "unit": "m2", "confidence": 0.6, "source": "exact",
                          "method": _method_of("ifc:" if d["source"] == "ifc_models" else "dxf:"), "flags": ["ambiguous_room_label"],
                          "method_detail": f"std:exact:room_area_by_name:{typ}", "evidence": map_evidence(d, _ev(rs), doc),
                          "scope": ti["scope"], "sources": [], "reason": f"{len(rs)} rooms of type {typ} in the exact file: one area each"})
    return cands


async def _judge_chat(messages, max_tokens):
    return await VLM.chat_text(messages, max_tokens)


SOURCE_METHOD = {"text": "text", "detector": "detector", "vlm": "vlm", "cache": "cache", "context": "context"}


async def ask(drawing_id, question, lang=None, use_vlm=True, use_cache=True, use_judge=None):
    t0 = time.time()
    d = CAT.describe(drawing_id)
    if d is None:
        return {"error": f"unknown drawing {drawing_id}"}
    question = (question or "").strip()[:500]
    use_judge = C.USE_JUDGE if use_judge is None else use_judge
    trace, cands, cost, doc = [], [], 0.0, None
    # NOTE (no leakage): nothing in this candidate-generation block may read reference_for()/example answers,
    # questions.jsonl labels or eval results. The dataset label is looked up only after the decision (bottom).

    # 1. historic context
    if d["track"] == "historic":
        r = await asyncio.to_thread(context_answer, d, question)
        trace.append({"route": "historic context", "result": "answered" if r else "not a metadata question"})
        if r:
            cands.append({**r, "source": "context", "scope": "any", "reason": "field of the archive record (cited)"})
            cost += C.COST_CPU_CALL

    # 2./3. standardized file + exact routes
    if d["source"] in ("swiss_dwellings", "ifc_models"):
        try:
            from stoa.answer import answer_std
            doc = await asyncio.to_thread(std_doc, d)
            r = await asyncio.to_thread(answer_std, d["q_path"], question, doc if doc and "error" not in doc else None)
        except Exception as e:
            r, doc = {"value": None, "abstain_reason": repr(e)[:200]}, None
        name = "standardized DXF file" if d["source"] == "swiss_dwellings" else "standardized IFC file"
        cost += C.COST_CPU_CALL
        if r.get("value") is not None:
            trace.append({"route": name, "result": "answered"})
            ev = await asyncio.to_thread(map_evidence, d, r.get("evidence") or [], doc)
            cands.append({"value": r["value"], "unit": r.get("unit"), "confidence": r.get("confidence", 0.99), "source": "exact",
                          "method": _method_of(r.get("method")), "method_detail": r.get("method"), "evidence": ev, "scope": "any",
                          "flags": r.get("flags", []), "sources": [], "reason": f"deterministic query of the {name} ({r.get('method')})"})
        else:
            trace.append({"route": name, "result": r.get("abstain_reason") or "abstained"})
            try:
                if d["source"] == "swiss_dwellings":
                    from stoa.methods.swiss_dxf import SwissDXFMethod as M
                else:
                    from stoa.methods.ifc_route import IFCMethod as M
                r2 = await M().answer(d["q_path"], question)
            except Exception as e:
                r2 = {"value": None, "abstain_reason": repr(e)[:200]}
            if r2.get("value") is not None:
                trace.append({"route": "exact parser route", "result": "answered"})
                ev = await asyncio.to_thread(map_evidence, d, r2.get("evidence") or [], doc)
                cands.append({"value": r2["value"], "unit": r2.get("unit"), "confidence": r2.get("confidence", 0.99), "source": "exact",
                              "method": _method_of(r2.get("method")), "method_detail": r2.get("method"), "evidence": ev, "scope": "any",
                              "sources": [], "reason": f"deterministic parser of the source file ({r2.get('method')})"})
            else:
                trace.append({"route": "exact parser route", "result": "abstained (question kind not in the CAD/IFC data)"})

    # 3b. room NAMES of an exact file answer room-type counts/areas the template parsers do not cover
    if doc and "error" not in doc and (doc.get("producer") or {}).get("kind") == "exact" and d["source"] in ("swiss_dwellings", "ifc_models"):
        try:
            cands = _exact_by_name(d, doc, question, cands)
        except Exception as e:
            trace.append({"route": "exact room names", "result": f"failed: {type(e).__name__}"})

    # 4. model-derived standardized file (detector)
    if d["source"] not in ("swiss_dwellings", "ifc_models") and d["track"] != "historic":
        doc = await asyncio.to_thread(std_doc, d)
        if doc and doc.get("producer", {}).get("kind") == "model":
            from stoa.answer import parse_intent, query
            r = query(doc, parse_intent(question))
            if r is not None:
                trace.append({"route": "detector file", "result": "answered"})
                cands.append({"value": r["value"], "unit": r["unit"], "confidence": r["confidence"], "source": "detector",
                              "method": "detector", "method_detail": f"std:model:{r['rule']}", "scope": "any",
                              "evidence": map_evidence(d, r["evidence"], doc), "sources": [],
                              "reason": f"{r['value']} detector box(es) above the calibrated threshold ({r['rule']})"})
                cost += C.COST_CPU_CALL
            else:
                trace.append({"route": "detector file", "result": "abstained"})

    # 5. words layer (printed text: PDF vector words or OCR)
    q_scope, scope_key = None, None
    if d["track"] != "historic":
        try:
            intent, tc, w = await asyncio.to_thread(text_candidates, d, question, doc if doc and "error" not in (doc or {}) else None)
            q_scope = intent.get("scope")
            for c in cands:  # route answers of the same question inherit its scope (they answer it as asked)
                if c.get("scope") == "any" and q_scope and not str(q_scope).startswith(("count:", "other:", "drawing", "unknown", "unsupported")):
                    c["scope"] = q_scope
            cands += tc
            trace.append({"route": "printed text", "result": (f"{len(tc)} candidate(s) from {len(w['words'])} words ({w.get('method')})"
                                                             if w else "no words layer yet")})
            cost += C.COST_CPU_CALL
        except Exception as e:
            trace.append({"route": "printed text", "result": f"failed: {type(e).__name__}"})

    strong_exact = any(c["source"] == "exact" and (c.get("confidence") or 0) >= 0.95 and not c.get("flags") for c in cands)
    has_context = any(c["source"] == "context" for c in cands)
    cached = CACHE.get(d["q_path"], question) if use_cache else None
    vlm_meta = None
    # 6. live VLM (skipped when an exact file already answers cleanly)
    if not strong_exact and not has_context and use_vlm and not (C.PREFER_CACHE and cached):
        h = await VLM.health()
        if h.get("online"):
            img = CAT.image_file(d)
            try:
                ctx_block = None
                if d["track"] == "historic":
                    from stoa.context.prompt import render
                    ctx = CAT.load_context(d["source"], d["stem"])
                    ctx_block = render(ctx, max_chars=1400, web=True) if ctx else ""
                r = await VLM.answer(img, question, context_block=ctx_block, style="zs" if d["track"] == "historic" else "ft")
                cost += C.COST_FT_CALL if d["track"] != "historic" else C.COST_GROUND_CALL
                trace.append({"route": f"VLM {r.get('model')}", "result": "answered" if r.get("value") is not None else "no answer"})
                if r.get("value") is not None:
                    vlm_meta = r
                    srcs = []
                    if d["track"] == "historic" and ctx_block:
                        ctx = CAT.load_context(d["source"], d["stem"]) or {}
                        srcs = [{"label": "archive record (given to the model as context)", "url": ctx.get("licence", {}).get("source_url")}]
                    cands.append({"value": r.get("value"), "unit": r.get("unit"), "confidence": r.get("confidence"), "source": "vlm",
                                  "method": "vlm", "method_detail": f"vlm:{r.get('model')}", "evidence": [], "sources": srcs,
                                  "scope": q_scope if q_scope and str(q_scope).startswith(("room:", "rooms_sum:", "total")) else "any",
                                  "model_raw": r.get("raw"), "reason": "fine-tuned model read the image; confidence = answer-token probability"})
                    CACHE.put_live(d["q_path"], question, {"answer": r.get("value"), "unit": r.get("unit"), "confidence": r.get("confidence"),
                                                          "method": "vlm", "evidence": []})
            except Exception as e:
                trace.append({"route": "VLM", "result": f"failed: {type(e).__name__}: {str(e)[:120]}"})
        else:
            trace.append({"route": "VLM", "result": f"offline ({h.get('reason', 'unreachable')})"})

    # 7. cache (earlier MODEL output only; records are whitelisted, never a dataset label)
    if not strong_exact and not has_context and not any(c["source"] == "vlm" for c in cands) and cached:
        trace.append({"route": "answer cache", "result": f"hit ({cached.get('origin', 'eval run')})"})
        ev = cached.get("evidence") or []
        cands.append({"value": cached["value"], "unit": cached.get("unit"), "confidence": cached.get("confidence"), "source": "cache",
                      "method": "cache", "method_detail": f"cache:{cached.get('method') or 'vlm'}:{cached.get('run', cached.get('origin', ''))}",
                      "cached_method": _method_of(cached.get("method")) if cached.get("method") else "vlm",
                      "scope": q_scope if q_scope and str(q_scope).startswith(("room:", "rooms_sum:", "total")) else "any",
                      "evidence": ev if all(("bbox" in e or "polygon" in e or "label" in e) for e in ev) else [], "sources": [],
                      "reason": "model answer cached from an earlier run (model output, not a label)"})

    # 8. decide
    from stoa.decide import decide, final_confidence, scope_key_for
    scope_key = scope_key_for(question, q_scope)
    from stoa.text.measure import text_intent, expected_unit
    dec = await decide(question, q_scope, cands, chat=_judge_chat if (use_judge and (await VLM.health()).get("online")) else None,
                       use_judge=use_judge, scope_key=scope_key, expected_unit=expected_unit(text_intent(question)))
    ranked = dec["ranked"]
    if dec.get("judge") and "error" not in dec["judge"]:
        cost += C.COST_JUDGE_CALL
    if dec["decider"] in ("judge", "judge-fallback"):
        trace.append({"route": "decision (LLM judge)", "result": (f"ranked {len(ranked)} candidates" if dec["decider"] == "judge"
                                                                 else f"fallback to deterministic ranking ({(dec.get('judge') or {}).get('error')})")})
    elif len(ranked) > 1:
        trace.append({"route": "decision", "result": f"{dec['decider']} ranking of {len(ranked)} candidates"})
    for c in dec["dropped"]:
        trace.append({"route": "decision", "result": c["reason"][:160]})

    top = ranked[0] if ranked else None
    # grounding boxes only for a VLM answer that won (saves a call otherwise)
    if top is not None and top["source"] == "vlm" and C.VLM_GROUND and vlm_meta and d["track"] != "historic":
        try:
            boxes, gi = await VLM.ground(vlm_meta["_img_url"], vlm_meta["img_size"], question, f"{top['value']} {top.get('unit') or ''}".strip())
            W, H = CAT.image_size(CAT.image_file(d))
            sx, sy = W / vlm_meta["img_size"][0], H / vlm_meta["img_size"][1]
            top["evidence"] = [{"id": f"B{i}", "label": f"model pointer {i + 1}", "kind": "pointer",
                                "bbox": [b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy], "approximate": True} for i, b in enumerate(boxes)]
            cost += C.COST_GROUND_CALL
        except Exception as e:
            trace.append({"route": "grounding (base model)", "result": f"failed: {type(e).__name__}"})

    if top is None:
        trace.append({"route": "answer", "result": "abstained"})
        res = {"value": None, "unit": None, "confidence": None, "method": "none", "evidence": [], "sources": []}
    else:
        conf = final_confidence(top, ranked, scope_key=scope_key)
        res = {**top, "confidence": conf, "method": top.get("method") if top["source"] == "exact" else SOURCE_METHOD.get(top["source"], top["source"])}

    conf = res.get("confidence")
    reasons = []
    if res["value"] is None:
        reasons.append("No route could answer this question (AI model offline or question outside the supported kinds).")
    elif conf is None or conf < C.CONF_AUTO:
        reasons.append(f"Confidence {conf if conf is None else round(conf, 2)} is below the auto-answer threshold {C.CONF_AUTO}.")
    for f in res.get("flags", []):
        reasons.append({"ambiguous_room_label": "Several rooms share this label: one area per room is listed.",
                        "sum_of_printed_room_areas": "No printed total: this is the sum of the printed room areas.",
                        "several_totals": "Several different totals are printed on the drawing.",
                        "space_without_area": "Some spaces have no area in the model."}.get(f, f))
    if res["value"] is not None and dec.get("decider") == "judge" and (dec.get("judge") or {}).get("unsure"):
        reasons.append("The decision model was unsure between the candidates.")
    # never present a near-zero-confidence guess as an answer: keep it only as a suggestion (no approximate boxes)
    suggested = None
    if res["value"] is not None and res["method"] not in ("dxf-exact", "ifc-exact") and (conf is None or conf < C.CONF_SUGGEST):
        suggested = res["value"]
        res = {**res, "value": None, "evidence": [e for e in res.get("evidence", []) if not e.get("approximate")]}
        reasons = [f"The best candidate ({suggested}{' ' + res['unit'] if res.get('unit') and res['unit'] not in ('count', 'text') else ''}, "
                   f"{res.get('source_label') or res['method']}) has very low confidence ({0 if conf is None else round(conf, 2)}), "
                   "so it is not shown as an answer. The other candidates below are hints."]
    ranked_out = []
    for i, c in enumerate(ranked):
        ranked_out.append({"rank": i + 1, "id": c["id"], "value": c["value"], "unit": c.get("unit"), "scope": c.get("scope"),
                           "source": c["source"], "source_label": c.get("source_label"),
                           "method": c.get("method") if c["source"] == "exact" else SOURCE_METHOD.get(c["source"], c["source"]),
                           "confidence": round(c["confidence"], 4) if isinstance(c.get("confidence"), (int, float)) else None,
                           "evidence": c.get("evidence") or [], "reason": c.get("reason"), "agree_with": c.get("agree_with", []),
                           "flags": c.get("flags", [])})
    out = {
        "drawing_id": d["id"], "question": question, "lang": lang or CAT._lang_of(question),
        "answer": res["value"], "unit": res.get("unit"), "method": res["method"],
        "method_label": METHOD_LABEL.get(res["method"], res["method"]), "method_detail": res.get("method_detail"),
        "cached_method": res.get("cached_method"),
        "confidence": round(conf, 4) if isinstance(conf, (int, float)) else None,
        "needs_check": bool(reasons), "needs_check_reasons": reasons,
        "evidence": res.get("evidence", []), "sources": res.get("sources", []), "note": res.get("note"),
        "suggested_answer": suggested, "cost_eur": round(cost, 7), "latency_ms": int((time.time() - t0) * 1000), "route_trace": trace,
        "ground_truth_eligible": res["method"] in ("dxf-exact", "ifc-exact"),
        "ranked_candidates": ranked_out, "decider": dec["decider"], "question_scope": q_scope,
        "judge": {k: v for k, v in (dec.get("judge") or {}).items() if k != "raw"} or None,
    }
    # dataset label for the UI: looked up only AFTER the decision, never passed to any route or the judge
    ref = reference_for(d, question)
    if ref is not None and ref.get("answer") is not None:
        out["reference"] = {"answer": ref["answer"], "unit": ref.get("unit"), "source": "dataset label (not shown to the model)",
                            "match": _check_ref(ref, res["value"])}
    return out


# ------------------------------------------------------------------------------------------------ standardized layer for the UI
def std_layer(d, max_items=1500):
    """-> (layer items in image px for the viewer, summary of the standardized file) or (None, None)"""
    if d["track"] == "historic":
        return None, None
    doc = std_doc(d)
    if not doc or "error" in doc:
        return None, ({"error": doc["error"]} if doc else None)
    layer = []
    groups = [("units", "unit"), ("rooms", "room"), ("doors", "door"), ("windows", "window"), ("symbols", None), ("elements", None)]
    if d["source"] == "swiss_dwellings":
        t = swiss_transform(d, doc)
        for key, kind in groups:
            for it in doc.get(key, []):
                poly = (it.get("geometry") or {}).get("polygon")
                if poly and t:
                    layer.append({"id": it["id"], "kind": kind or it.get("kind"), "label": _label(it), "polygon": G.apply_M(t["M"], poly),
                                  "type": it.get("type")})
    elif d["source"] == "ifc_models":
        boxes = ifc_svg_boxes(d)
        for key, kind in groups:
            for it in doc.get(key, []):
                g = it.get("ifc_global_id")
                if g in boxes:
                    layer.append({"id": g, "kind": kind or (it.get("ifc_type") or "").replace("Ifc", "").lower(),
                                  "label": _label(it), "bbox": boxes[g], "ifc_global_id": g})
    else:
        for key, kind in groups:
            for it in doc.get(key, []):
                bb = (it.get("geometry") or {}).get("bbox_px")
                if bb:
                    layer.append({"id": it["id"], "kind": kind or it.get("kind"), "label": _label(it), "bbox": bb,
                                  "confidence": (it.get("provenance") or {}).get("confidence")})
    rooms = doc.get("rooms", [])
    summary = {
        "schema_version": doc.get("schema_version"), "drawing_id": doc.get("drawing_id"), "producer": doc.get("producer"),
        "ground_truth_eligible": doc.get("ground_truth_eligible"),
        "counts": {k: len(doc.get(k, [])) for k in ("levels", "units", "rooms", "doors", "windows", "symbols", "elements")},
        "symbol_kinds": _count_kinds(doc.get("symbols", [])), "element_kinds": _count_kinds(doc.get("elements", [])),
        "total_room_area_m2": round(sum(r.get("area_m2") or 0 for r in rooms if not r.get("is_outdoor") and not r.get("is_shaft")), 2),
        "levels": [l.get("name") for l in doc.get("levels", [])][:40],
        "units": [{"id": u["id"], "label": u.get("label"), "rooms": len(u.get("room_ids", []))} for u in doc.get("units", [])],
        "rooms": [{"id": r["id"], "name": r.get("name"), "number": r.get("number"), "area_m2": r.get("area_m2"),
                   "area_method": r.get("area_method"), "unit_id": r.get("unit_id")} for r in rooms[:300]],
        "warnings": (doc.get("quality") or {}).get("warnings", []),
        "registration": TRANSFORMS.get(d["id"]) if d["source"] == "swiss_dwellings" else None,
        "on_this_sheet": len(layer),
    }
    return layer[:max_items], summary


def _count_kinds(items):
    out = {}
    for it in items:
        k = it.get("kind") or it.get("ifc_type") or "item"
        out[k] = out.get(k, 0) + 1
    return out
