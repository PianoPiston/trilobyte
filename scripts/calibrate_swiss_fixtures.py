"""Find FIXTURE-layer primitive signatures whose per-floor count matches the gold fixture counts (TRAIN floors only).
usage: python -I scripts/calibrate_swiss_fixtures.py [N_FLOORS]"""
import collections, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions, DATA_ROOT
import ezdxf

KINDS = {"toilet": r"toilets", "washbasin": r"washbasins", "bathtub": r"bathtubs", "shower": r"showers"}


def sigs(dxf):
    c = collections.Counter()
    for e in ezdxf.readfile(dxf).modelspace():
        if e.dxf.layer != "FIXTURE":
            continue
        if e.dxftype() == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            c[f"poly{len(pts)}{'c' if e.closed else 'o'}"] += 1
            c[f"poly{len(pts)}{'c' if e.closed else 'o'}_{max(w,h):.1f}x{min(w,h):.1f}"] += 1
        elif e.dxftype() == "CIRCLE":
            c[f"circle_{e.dxf.radius:.2f}"] += 1
        else:
            c[e.dxftype()] += 1
    return c


if __name__ == "__main__":
    nmax = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    gold = collections.defaultdict(dict)
    for q in load_questions():
        if q.source != "swiss_dwellings" or q.split != "train" or not q.lang_en:
            continue
        for k, pat in KINDS.items():
            if re.search(r"How many " + pat, q.question):
                gold[q.path][k] = int(q.answer)
    paths = sorted(gold)[:nmax]
    S = {p: sigs(os.path.join(DATA_ROOT, os.path.splitext(p)[0] + ".dxf")) for p in paths}
    allsig = collections.Counter(s for p in paths for s in S[p])
    for k in KINDS:
        ps = [p for p in paths if k in gold[p]]
        if not ps:
            continue
        best = []
        for s in allsig:
            for div in (1, 2, 3, 4):
                m = sum(1 for p in ps if S[p][s] == gold[p][k] * div)
                best.append((m / len(ps), s, div))
        best.sort(reverse=True)
        print(k, len(ps), "gold>0:", sum(gold[p][k] > 0 for p in ps), best[:6])
