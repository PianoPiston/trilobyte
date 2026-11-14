"""Question loading, drawing groups, EN/translation pair ids and the train/val/test split.

Split is by *drawing group*, never by question:
  cubicasa5k      group = file stem (one plan per file)
  swiss_dwellings group = site+building (floors of one building stay together)
  ifc_models      group = IFC model (all rendered plans of a model + model-level questions)
  ifc_bench       group = IFC file
  opening_design  group = sheet PDF (only 3 sheets: never used for training, val/test only)
Assignment: groups of each source ranked by a deterministic hash, cut at exact fractions, so it is stable across machines/runs.
"""
import hashlib, json, os, re
from dataclasses import dataclass, field

DATA_ROOT = os.environ.get("STOA_DATA", os.path.join(os.path.dirname(__file__), "../../DATA/junction-dataset"))
SPLIT_FRACS = {"train": 0.80, "val": 0.10, "test": 0.10}
NO_TRAIN_SOURCES = {"opening_design"}

_EN_START = re.compile(r"^(how|what|which|where|is|are|does|do|on sheet|list|give|in |for )", re.I)


@dataclass
class Q:
    idx: int
    path: str
    question: str
    answer: object
    unit: str | None
    type: str
    source: str = ""
    group: str = ""
    pair: int = -1      # rows sharing a pair id are the same question in two languages
    lang_en: bool = True
    split: str = ""

    def to_json(self):
        return {k: getattr(self, k) for k in ("idx", "path", "question", "answer", "unit", "type", "source", "group", "pair", "lang_en", "split")}


def group_of(path: str) -> str:
    src = path.split("/")[1]
    stem = os.path.splitext(os.path.basename(path))[0]
    if src == "swiss_dwellings":
        m = re.match(r"(site\d+_bldg\d+)", stem)
        return f"{src}/{m.group(1) if m else stem}"
    if src == "ifc_models":
        return f"{src}/{stem.split('_plan-')[0]}"
    if src == "opening_design":
        return f"{src}/{path}"
    return f"{src}/{stem}"


def _bucket(group: str) -> float:
    h = hashlib.sha256(("stoa-split-v1:" + group).encode()).hexdigest()
    return int(h[:12], 16) / float(16 ** 12)


def assign_splits(groups_by_source: dict) -> dict:
    """Rank groups of each source by hash and cut at exact fractions (stable, balanced even for
    sources with few groups)."""
    out = {}
    for src, groups in groups_by_source.items():
        gs = sorted(groups, key=_bucket)
        n = len(gs)
        if src in NO_TRAIN_SOURCES:
            cuts = (0, max(1, n // 3))                       # train 0, val ~1/3, test rest
        elif n < 100:
            cuts = (round(n * 0.70), round(n * 0.85))        # small sources: 70/15/15
        else:
            cuts = (round(n * SPLIT_FRACS["train"]), round(n * (SPLIT_FRACS["train"] + SPLIT_FRACS["val"])))
        for r, g in enumerate(gs):
            out[g] = "train" if r < cuts[0] else ("val" if r < cuts[1] else "test")
    return out


def load_questions(path: str | None = None) -> list[Q]:
    path = path or os.path.join(DATA_ROOT, "questions.jsonl")
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            q = Q(idx=i, **r)
            q.source = q.path.split("/")[1]
            q.group = group_of(q.path)
            rows.append(q)
    by_src = {}
    for q in rows:
        by_src.setdefault(q.source, set()).add(q.group)
    splits = assign_splits(by_src)
    for q in rows:
        q.split = splits[q.group]
    # pair detection: English row immediately followed by a non-English row with same path+answer
    i = 0
    while i < len(rows):
        a = rows[i]
        a.lang_en = bool(_EN_START.match(a.question))
        if i + 1 < len(rows):
            b = rows[i + 1]
            if (b.path == a.path and b.answer == a.answer and a.lang_en and not _EN_START.match(b.question)):
                a.pair = b.pair = i
                b.lang_en = False
                i += 2
                continue
        a.pair = i
        i += 1
    return rows


def image_path_for(q_path: str) -> str | None:
    """Raster image used by vision models for a question path, or None if not image-answerable.
    swiss/ifc_models ship a PNG next to the PDF; opening_design PDFs are rendered on demand."""
    full = os.path.join(DATA_ROOT, q_path)
    ext = os.path.splitext(q_path)[1].lower()
    if ext == ".png":
        return full
    if ext == ".pdf":
        png = os.path.splitext(full)[0] + ".png"
        return png if os.path.exists(png) else full  # caller renders PDF
    return None  # .ifc etc. -> deterministic route only


def cell(q: Q) -> str:
    fmt = os.path.splitext(q.path)[1].lstrip(".").lower()
    return f"{q.source}/{q.type}" + ("/ifc" if fmt == "ifc" and q.source == "ifc_models" else "")
