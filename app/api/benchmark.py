"""Benchmark page data: tables from results/leaderboard.md plus per-source numbers recomputed from the TEST run files
(accuracy, answered share and accuracy-on-answered at the auto-answer threshold)."""
import functools, json, os, re
from collections import defaultdict
from . import config as C

SYSTEMS = [("zero-shot Qwen3.5-4B", "TEST-zs-qwen3.5-4b", 0.038), ("fine-tuned Qwen3.5-4B (LoRA)", "TEST-ft-run1-step1050", 0.013),
           ("hybrid router (DXF + IFC + fine-tuned VLM)", "TEST-hybrid-run1-step1050", 0.021)]


def md_tables(text):
    """-> [{"section": heading, "header": [...], "rows": [[...]]}]"""
    out, section, cur = [], None, None
    for line in text.splitlines():
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            cur = None
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cur is None:
                cur = {"section": section, "header": cells, "rows": []}
                out.append(cur)
            elif all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            else:
                cur["rows"].append(cells)
        else:
            cur = None
    return out


def _cell(r):
    src = r.get("source") or r["path"].split("/")[1]
    return src, r.get("type", "")


@functools.lru_cache(maxsize=1)
def per_source():
    from stoa.scoring import is_correct
    res = {}
    for name, run, eur in SYSTEMS:
        fn = os.path.join(C.ROOT, "results/runs", run + ".jsonl")
        if not os.path.exists(fn):
            continue
        agg = defaultdict(lambda: [0, 0, 0, 0])  # n, correct, answered@thr, correct@thr
        for line in open(fn):
            r = json.loads(line)
            p = r.get("pred") or {}
            v, conf = p.get("value"), p.get("confidence")
            ok = is_correct(r["type"], v, r["answer"]) if v is not None else False
            for key in (r["source"], "all"):
                a = agg[key]
                a[0] += 1
                a[1] += ok
                if v is not None and conf is not None and conf >= C.CONF_AUTO:
                    a[2] += 1
                    a[3] += ok
        res[name] = {k: {"n": a[0], "accuracy": round(a[1] / a[0], 3), "answered_share": round(a[2] / a[0], 3),
                         "accuracy_on_answered": round(a[3] / a[2], 3) if a[2] else None} for k, a in agg.items()}
        res[name]["_eur_per_1k"] = eur
    return res


def benchmark():
    fn = os.path.join(C.ROOT, "results/leaderboard.md")
    text = open(fn, encoding="utf-8").read() if os.path.exists(fn) else ""
    tables = md_tables(text)
    pick = lambda pred: next((t for t in tables if pred(t)), None)
    headline = pick(lambda t: (t["section"] or "").startswith("Phase 3") and t["header"][0].startswith("system"))
    calib = pick(lambda t: t["header"][:2] == ["threshold", "coverage"])
    historic = [t for t in tables if "istoric" in (t["section"] or "")]
    runs = pick(lambda t: (t["section"] or "") == "Runs")
    return {
        "threshold": C.CONF_AUTO,
        "headline": headline, "calibration": calib, "historic": historic, "runs": runs,
        "per_source": per_source(),
        "notes": [
            "Held-out TEST split = drawings never seen in training (split by drawing group: building / IFC model / file).",
            "Scoring follows the challenge: counts exact, areas/lengths/volumes within 2%.",
            "Cost = GPU €/h x wall-clock / questions at batch serving (A100 €1.65/h reference); CPU routes ~€0.",
            f"'Answered' = confidence >= {C.CONF_AUTO}; below that the product shows 'Needs check' with the evidence.",
        ],
        "source": "results/leaderboard.md + results/runs/TEST-*.jsonl",
    }
