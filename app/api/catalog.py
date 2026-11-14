"""Drawing registry: describes any locally available drawing (curated demo set + everything searchable).

Drawing id = "<source>~<file stem>" (url-safe enough; the UI url-encodes it). `q_path` is the dataset-relative path
that questions.jsonl and the routes use (e.g. data/swiss_dwellings/<stem>.pdf even though only .png/.dxf are local).
"""
import functools, json, math, os, re, threading
from collections import defaultdict
from PIL import Image

from . import config as C

Image.MAX_IMAGE_PIXELS = None

HISTORIC = ("habs", "finna", "europeana", "wikimedia")
SOURCE_LABEL = {
    "cubicasa5k": "CubiCasa5K (FI apartments)", "swiss_dwellings": "Swiss Dwellings", "ifc_models": "IFC models",
    "ifc_bench": "IFC-Bench", "opening_design": "OpeningDesign (US CAD sheets)", "habs": "HABS (Library of Congress)",
    "finna": "Finna (Helsinki archives)", "europeana": "Europeana", "wikimedia": "Wikimedia Commons",
}
_lock = threading.Lock()


def make_id(source, stem):
    return f"{source}~{stem}"


def split_id(did):
    src, _, stem = did.partition("~")
    return src, stem


# ------------------------------------------------------------------------------------------------ licences
@functools.lru_cache(maxsize=16)
def licence_table(source):
    """file (relative to data/<source>/) -> {title, licence, credit, source_url}; plus '*' for 'All files:' lines."""
    out = {}
    for root in C.DATA_ROOTS:
        fn = os.path.join(root, "data", source, "LICENSE.md")
        if not os.path.exists(fn):
            continue
        for line in open(fn, encoding="utf-8", errors="replace"):
            if line.startswith("All files:"):
                m = re.match(r"All files:\s*([^.]+(?:\.\d)?[^.]*)\.\s*Credit:\s*(.*)$", line.strip())
                if m:
                    out["*"] = {"title": None, "licence": m.group(1).strip(), "credit": m.group(2).strip(), "source_url": None}
            if not line.startswith("| ") or line.startswith("| file |"):
                continue
            parts = [p.strip() for p in line.strip().strip("|").split(" | ")]
            if len(parts) != 5:
                continue
            f, title, lic, credit, src = parts
            out[f] = {"title": title, "licence": lic, "credit": credit, "source_url": src}
        break
    return out


def licence_for(source, rel_files):
    t = licence_table(source)
    for f in rel_files:
        if f in t:
            return t[f]
    return t.get("*") or {"title": None, "licence": "see LICENSE.md", "credit": f"data/{source}/LICENSE.md", "source_url": None}


# ------------------------------------------------------------------------------------------------ questions
@functools.lru_cache(maxsize=1)
def questions_by_path():
    from stoa.data import load_questions
    by = defaultdict(list)
    for q in load_questions():
        by[q.path].append(q)
    return by


@functools.lru_cache(maxsize=1)
def historic_eval():
    fn = os.path.join(C.ROOT, "results/samples/historic_eval.jsonl")
    by = defaultdict(list)
    if os.path.exists(fn):
        for line in open(fn):
            r = json.loads(line)
            by[r["path"]].append(r)
    return by


@functools.lru_cache(maxsize=1)
def split_by_group():
    from stoa.data import group_of
    return {q.group: q.split for qs in questions_by_path().values() for q in qs}


def _find_root(rel):
    for root in C.DATA_ROOTS:
        if os.path.exists(os.path.join(root, rel)):
            return root
    return None


# ------------------------------------------------------------------------------------------------ resolution
def _files_for(source, stem):
    """dataset-relative files of one drawing, across all data roots"""
    files = {}
    if source == "opening_design":
        for root in C.DATA_ROOTS:
            base = os.path.join(root, "data", source)
            if os.path.isdir(base):
                for dp, _, fns in os.walk(base):
                    for fn in fns:
                        if os.path.splitext(fn)[0] == stem:
                            rel = os.path.relpath(os.path.join(dp, fn), root)
                            files[os.path.splitext(fn)[1].lstrip(".").lower()] = rel
        return files
    for root in C.DATA_ROOTS:
        d = os.path.join(root, "data", source)
        for ext in ("png", "jpg", "pdf", "svg", "dxf", "ifc"):
            rel = f"data/{source}/{stem}.{ext}"
            if ext not in files and os.path.exists(os.path.join(root, rel)):
                files[ext] = rel
    if source == "ifc_models" and "_plan-" in stem:
        rel = f"data/{source}/{stem.split('_plan-')[0]}.ifc"
        if _find_root(rel):
            files["ifc"] = rel
    return files


def _q_path(source, stem, files):
    """path used by questions.jsonl for this drawing"""
    if source in ("swiss_dwellings", "ifc_models", "opening_design"):
        cand = files.get("pdf") or f"data/{source}/{stem}.pdf"
        return cand
    if source == "cubicasa5k":
        return files.get("png") or f"data/{source}/{stem}.png"
    return files.get("jpg") or files.get("png") or files.get("svg") or next(iter(files.values()), f"data/{source}/{stem}")


def _title(source, stem, lic, ctx):
    if source == "cubicasa5k":
        return f"Apartment floor plan {stem}", "Finnish real-estate plan (raster)"
    if source == "swiss_dwellings":
        m = re.match(r"site(\d+)_bldg(\d+)_floor(\d+)", stem)
        return (f"Site {m.group(1)} · Building {m.group(2)} · Floor {m.group(3)}" if m else stem), "Swiss apartment floor (PNG + DXF)"
    if source == "ifc_models":
        t = (lic or {}).get("title") or stem
        return t, "Floor plan rendered from an IFC model"
    if source == "opening_design":
        return stem, "US architecture practice sheet (PDF)"
    if ctx:
        b = ((ctx.get("fields") or {}).get("building") or {}).get("value")
        if b:
            return str(b)[:120], SOURCE_LABEL.get(source, source)
    return ((lic or {}).get("title") or stem)[:120], SOURCE_LABEL.get(source, source)


def load_context(source, stem):
    fn = os.path.join(C.ROOT, "context", source, stem + ".json")
    if os.path.exists(fn):
        try:
            return json.load(open(fn, encoding="utf-8"))
        except Exception:
            return None
    return None


def image_rel(d):
    f = d["files"]
    return f.get("png") or f.get("jpg") or f.get("pdf") or f.get("svg")


def image_file(d):
    """absolute path of a raster image of the drawing (renders PDF/SVG once into the cache)"""
    rel = image_rel(d)
    if rel is None:
        return None
    src = os.path.join(_find_root(rel) or C.DATA_MAIN, rel)
    ext = os.path.splitext(rel)[1].lower()
    if ext in (".png", ".jpg", ".jpeg"):
        return src
    out = os.path.join(C.APP_CACHE, "render", d["id"].replace("/", "_") + ".png")
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        import fitz
        with _lock:
            doc = fitz.open(src)
            page = doc[0]
            target = 9_000_000 if d["source"] == "opening_design" else 5_000_000
            z = math.sqrt(target / (page.rect.width * page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            pix.save(out)
    return out


@functools.lru_cache(maxsize=4096)
def image_size(path):
    with Image.open(path) as im:
        return list(im.size)


def thumb_file(d, max_side=480):
    out = os.path.join(C.APP_CACHE, "thumbs", d["id"].replace("/", "_") + ".jpg")
    if not os.path.exists(out):
        src = image_file(d)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.LANCZOS)
            im.save(out, quality=82)
    return out


def _lang_of(text):
    t = text.lower()
    if re.search(r"\b(kuinka|mikä|montako|missä|milloin|kuka|pohjapiirustu)", t):
        return "fi"
    if re.search(r"\b(wie viele|welche|wo |grundriss|geschoss)", t):
        return "de"
    if re.search(r"\b(combien|quelle|plan d|étage)", t):
        return "fr"
    if re.search(r"\b(quant[ie]|qual[ei]|pianta)", t):
        return "it"
    return "en"


def example_questions(d, limit=14):
    out, seen = [], set()
    src = d["source"]
    if src in HISTORIC:
        for r in historic_eval().get(d["q_path"], []):
            out.append({"question": r["question"], "answer": r["answer"], "unit": None, "type": r.get("qtype"),
                        "lang": "en", "origin": r.get("origin"), "needs_human_check": r.get("needs_human_check"),
                        "accept": r.get("accept")})
        return out[:limit]
    qs = list(questions_by_path().get(d["q_path"], []))
    if src == "ifc_models" and d["files"].get("ifc"):
        model_qs = questions_by_path().get(d["files"]["ifc"], [])
        qs += [q for q in model_qs if q.lang_en][:4]
    for q in qs:
        key = (q.question.split("?")[0][:60])
        if key in seen:
            continue
        seen.add(key)
        out.append({"question": q.question, "answer": q.answer, "unit": q.unit, "type": q.type, "lang": _lang_of(q.question)})
    # EN first, then FI translations, then other languages; keep pairs close
    order = {"en": 0, "fi": 1}
    out.sort(key=lambda r: order.get(r["lang"], 2))
    return out[:limit]


@functools.lru_cache(maxsize=1)
def _catalog_file():
    if os.path.exists(C.CATALOG):
        return json.load(open(C.CATALOG))
    return {"drawings": []}


def featured():
    return _catalog_file()["drawings"]


@functools.lru_cache(maxsize=8192)
def describe(did):
    """full description of any local drawing, or None"""
    source, stem = split_id(did)
    if not source or not stem or "/" in stem or ".." in stem:
        return None
    files = _files_for(source, stem)
    if not files:
        return None
    q_path = _q_path(source, stem, files)
    from stoa.data import group_of
    split = None
    if source in HISTORIC:
        rows = historic_eval().get(q_path, [])
        split = rows[0]["split"] if rows else None
    else:
        split = split_by_group().get(group_of(q_path))
    lic = licence_for(source, [os.path.relpath(f, f"data/{source}") for f in files.values()])
    ctx = load_context(source, stem) if source in HISTORIC else None
    if ctx and ctx.get("licence"):
        lic = {**lic, **{k: v for k, v in ctx["licence"].items() if k in ("licence", "credit", "source_url") and v}}
    title, subtitle = _title(source, stem, lic, ctx)
    d = {
        "id": did, "source": source, "source_label": SOURCE_LABEL.get(source, source), "stem": stem,
        "title": title, "subtitle": subtitle, "q_path": q_path, "files": files,
        "formats": sorted({k.upper() for k in files}), "split": split,
        "seen_in_training": split == "train" if split else None,
        "track": "historic" if source in HISTORIC else "modern",
        "licence": lic.get("licence"), "credit": lic.get("credit"), "source_url": lic.get("source_url"),
        "has_context": ctx is not None, "has_std": source in ("swiss_dwellings", "ifc_models") and bool(files.get("dxf") or files.get("ifc")),
    }
    d["image_ok"] = image_rel(d) is not None
    return d


def describe_full(did):
    d = describe(did)
    if d is None:
        return None
    d = dict(d)
    img = image_file(d)
    d["image_size"] = image_size(img) if img else None
    d["examples"] = example_questions(d)
    return d
