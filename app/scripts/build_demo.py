"""Build the demo data for the product (idempotent, CPU only):

  app/data/catalog.json          curated demo drawings (~50, mostly held-out TEST split; never train unless needed)
  app/data/answer_cache.jsonl    precomputed answers from the eval runs of the selected system (served as method "cache"
                                 when no model endpoint is reachable)
  app/data/search_index.json     facts per drawing for /api/search (our system's answers on TEST + standardized files
                                 + historic context fields)
  app/data/transforms.json       swiss DXF -> PNG registrations for the demo floors
  app/.cache/thumbs, render      thumbnails, PDF/SVG renders

usage: ~/venvs/stoa-app/bin/python app/scripts/build_demo.py [--skip-transforms]
"""
import argparse, json, os, random, re, sys, time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app.api import config as C  # noqa: E402  (sets sys.path for src/)
from app.api import catalog as CAT  # noqa: E402

RUNS = [  # selected system only (fine-tuned step1050 + hybrid router); TEST first so it wins on duplicates
    ("TEST-hybrid-run1-step1050", "hybrid router, held-out TEST"),
    ("sel-r1s1050-cubi400", "fine-tuned VLM, val"),
    ("ft-run1-step1050", "fine-tuned VLM, val300"),
]


def pick(seq, n, seed):
    seq = sorted(seq)
    random.Random(seed).shuffle(seq)
    return seq[:n]


def curate():
    by = CAT.questions_by_path()
    out = []
    # cubicasa: TEST plans, 10 random + 4 with a sauna (Finnish story)
    cubi = [p for p, qs in by.items() if qs[0].source == "cubicasa5k" and qs[0].split == "test"
            and os.path.exists(os.path.join(C.DATA_MAIN, p))]
    sauna = [p for p in cubi if any(q.question.startswith("How many saunas") and q.answer and q.answer > 0 for q in by[p])]
    sel = pick(sauna, 5, 1) + [p for p in pick(cubi, 30, 2) if p not in sauna][:9]
    out += [("cubicasa5k", os.path.splitext(os.path.basename(p))[0]) for p in sel]
    # swiss: TEST floors with PNG + DXF
    sw = [p for p, qs in by.items() if qs[0].source == "swiss_dwellings" and qs[0].split == "test"
          and os.path.exists(os.path.join(C.DATA_MAIN, os.path.splitext(p)[0] + ".dxf"))
          and os.path.exists(os.path.join(C.DATA_MAIN, os.path.splitext(p)[0] + ".png"))]
    out += [("swiss_dwellings", os.path.splitext(os.path.basename(p))[0]) for p in pick(sw, 10, 3)]
    # ifc_models: plan sheets of TEST/VAL models with a local SVG (evidence) and IFC (exact route); small models first
    ifc = defaultdict(list)
    for p, qs in by.items():
        if qs[0].source != "ifc_models" or "_plan-" not in p or qs[0].split == "train":
            continue
        stem = os.path.splitext(p)[0]
        model = stem.split("_plan-")[0] + ".ifc"
        if os.path.exists(os.path.join(C.DATA_MAIN, stem + ".svg")) and os.path.exists(os.path.join(C.DATA_MAIN, model)):
            size = os.path.getsize(os.path.join(C.DATA_MAIN, model))
            if size < 40e6:
                ifc[(qs[0].split != "test", size, model)].append(p)
    n = 0
    for key in sorted(ifc):
        plans = sorted(ifc[key], key=lambda p: -len(by[p]))[:2]
        for p in plans:
            out.append(("ifc_models", os.path.splitext(os.path.basename(p))[0]))
            n += 1
        if n >= 9:
            break
    # opening_design: the 3 question sheets (val/test only)
    for root in (C.DATA_DEMO,):
        base = os.path.join(root, "data/opening_design")
        for dp, _, fns in os.walk(base):
            for fn in sorted(fns):
                if fn.endswith(".pdf"):
                    out.append(("opening_design", os.path.splitext(fn)[0]))
    # historic: eval drawings with a context file and a local image, 4 per source (test split first)
    hist = defaultdict(list)
    for p, rows in CAT.historic_eval().items():
        src = p.split("/")[1]
        stem = os.path.splitext(os.path.basename(p))[0]
        if CAT.load_context(src, stem) and os.path.exists(os.path.join(C.DATA_HISTORIC, p)):
            hist[src].append((rows[0]["split"] != "test", -len(rows), stem))
    for src in CAT.HISTORIC:
        for _, _, stem in sorted(hist[src])[:4]:
            out.append((src, stem))
    return out


def build_catalog():
    items = []
    for src, stem in curate():
        did = CAT.make_id(src, stem)
        d = CAT.describe(did)
        if d is None or not d["image_ok"]:
            print("skip (no image)", did)
            continue
        try:
            CAT.thumb_file(d)
            img = CAT.image_file(d)
            size = CAT.image_size(img)
        except Exception as e:
            print("skip (render failed)", did, e)
            continue
        ex = CAT.example_questions(d, limit=6)
        items.append({**{k: d[k] for k in ("id", "source", "source_label", "title", "subtitle", "formats", "split",
                                          "seen_in_training", "track", "licence", "credit", "source_url", "has_context", "has_std")},
                      "image_size": size, "n_questions": len(CAT.example_questions(d, limit=500)),
                      "teaser": [e["question"] for e in ex[:2]]})
        print(f"{len(items):3d} {did} {size}")
    json.dump({"generated": time.strftime("%Y-%m-%d %H:%M"), "drawings": items}, open(C.CATALOG, "w"), ensure_ascii=False, indent=1)
    return items


def build_cache():
    n = 0
    seen = set()
    with open(C.ANSWER_CACHE, "w", encoding="utf-8") as f:
        for run, desc in RUNS:
            fn = os.path.join(C.ROOT, "results/runs", run + ".jsonl")
            if not os.path.exists(fn):
                continue
            for line in open(fn):
                r = json.loads(line)
                p = r.get("pred") or {}
                key = (r["path"], r["question"].strip().lower())
                if key in seen or p.get("value") is None:
                    continue
                seen.add(key)
                f.write(json.dumps({"q_path": r["path"], "question": r["question"], "value": p["value"], "unit": p.get("unit"),
                                    "confidence": p.get("confidence"), "method": p.get("method", "vlm"), "run": run,
                                    "origin": desc, "evidence": []}, ensure_ascii=False) + "\n")
                n += 1
    print("answer cache rows", n)


# ------------------------------------------------------------------------------------------------ search index
FACT_OF_TEMPLATE = {"bedrooms": "bedrooms", "saunas": "saunas", "toilets": "toilets", "bathrooms": "bathrooms",
                    "kitchens": "kitchens", "balconies": "balconies", "windows": "windows", "doors": "doors",
                    "floors": "floors", "wc_rooms": "wc_rooms", "sinks": "sinks", "showers_baths": "showers_baths"}
SWISS_LABEL_FACT = {"schlafzimmer": "bedrooms", "chambre": "bedrooms", "camera": "bedrooms", "zimmer": "rooms",
                    "küche": "kitchens", "cuisine": "kitchens", "cucina": "kitchens", "bad": "bathrooms", "balkon": "balconies"}


def fact_key(q):
    from stoa.convert.cubicasa_rules import template_of
    if q.source == "cubicasa5k":
        return FACT_OF_TEMPLATE.get(template_of(q.question) or "")
    if q.source == "swiss_dwellings":
        from stoa.answer import parse_intent
        it = parse_intent(q.question)
        k = it["kind"]
        if k == "count_units":
            return "apartments"
        if k in ("count_doors", "count_windows"):
            return k.split("_")[1]
        if k == "count_symbol":
            return {"toilet": "toilets", "washbasin": "washbasins", "bathtub": "bathtubs", "shower": "showers"}.get(it["symbol"])
        if k == "count_rooms_labelled":
            return SWISS_LABEL_FACT.get(it["label"].lower())
        if k == "area_floor_numbered":
            return "floor_area_m2"
    return None


def build_index(catalog):
    from stoa.data import load_questions  # noqa
    by = CAT.questions_by_path()
    preds = {}
    fn = os.path.join(C.ROOT, "results/runs/TEST-hybrid-run1-step1050.jsonl")
    for line in open(fn):
        r = json.loads(line)
        preds[(r["path"], r["question"])] = r["pred"]
    docs = {}
    for (path, question), p in preds.items():
        qs = by.get(path) or []
        q = next((x for x in qs if x.question == question), None)
        if q is None or not q.lang_en or p.get("value") is None:
            continue
        k = fact_key(q)
        if not k:
            continue
        src = q.source
        stem = os.path.splitext(os.path.basename(path))[0]
        did = CAT.make_id(src, stem)
        if src == "cubicasa5k" and not os.path.exists(os.path.join(C.DATA_MAIN, path)):
            continue
        if src == "swiss_dwellings" and not os.path.exists(os.path.join(C.DATA_MAIN, os.path.splitext(path)[0] + ".png")):
            continue
        dd = docs.setdefault(did, {"id": did, "source": src, "facts": {}, "text": ""})
        try:
            v = float(p["value"])
        except Exception:
            continue
        old = dd["facts"].get(k)
        if k == "bedrooms" and src == "swiss_dwellings" and old:  # several labels map to bedrooms
            v += old["value"]
        dd["facts"][k] = {"value": v, "confidence": round(p.get("confidence") or 0, 3),
                          "method": "dxf-exact" if str(p.get("method", "")).startswith("dxf") else "vlm"}
    # historic: text index from context fields (only drawings whose image is local)
    for src in CAT.HISTORIC:
        d = os.path.join(C.DATA_HISTORIC, "data", src)
        if not os.path.isdir(d):
            continue
        for fn_ in os.listdir(d):
            stem, ext = os.path.splitext(fn_)
            if ext.lower() not in (".jpg", ".png"):
                continue
            ctx = CAT.load_context(src, stem)
            if not ctx:
                continue
            f = ctx.get("fields") or {}
            parts = []
            for k in ("building", "title", "place", "country", "year", "architect_or_author", "drawing_type", "subjects"):
                v = (f.get(k) or {}).get("value")
                if v:
                    parts.append(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
            summ = (ctx.get("summary") or {}).get("value") or ""
            did = CAT.make_id(src, stem)
            yr = (f.get("year") or {}).get("value") or {}
            docs[did] = {"id": did, "source": src, "facts": {}, "text": (" ".join(parts) + " " + summ)[:2000],
                         "years": yr.get("years") if isinstance(yr, dict) else None}
    for it in catalog:
        dd = docs.setdefault(it["id"], {"id": it["id"], "source": it["source"], "facts": {}, "text": ""})
        dd["featured"] = True
    for dd in docs.values():
        d = CAT.describe(dd["id"])
        if d:
            dd["title"] = d["title"]
            dd["text"] = (d["title"] + " " + d["subtitle"] + " " + dd["text"]).strip()
            dd["split"] = d["split"]
    json.dump({"generated": time.strftime("%Y-%m-%d %H:%M"), "n": len(docs), "docs": list(docs.values())},
              open(C.SEARCH_INDEX, "w"), ensure_ascii=False)
    print("search index docs", len(docs))


def build_transforms(catalog):
    from app.api import engine as E
    for it in catalog:
        if it["source"] == "swiss_dwellings":
            d = CAT.describe(it["id"])
            t0 = time.time()
            t = E.swiss_transform(d, E.std_doc(d))
            print("transform", it["id"], t and t["score"], t and t["px_per_m"], round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-transforms", action="store_true")
    a = ap.parse_args()
    cat = build_catalog()
    CAT._catalog_file.cache_clear()
    build_cache()
    build_index(cat)
    if not a.skip_transforms:
        build_transforms(cat)
