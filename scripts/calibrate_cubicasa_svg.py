"""Check how the cubicasa gold counts relate to the original CubiCasa5k SVG annotations, on TRAIN drawings only.
Prints, for each question template, the accuracy of candidate counting rules, plus PNG-vs-SVG size alignment.
usage: python -I scripts/calibrate_cubicasa_svg.py [N]"""
import collections, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import load_questions, DATA_ROOT
from stoa.convert.cubicasa_svg import load_annotation
from stoa.convert.cubicasa_rules import TEMPLATES, RULES, template_of
from PIL import Image

N = int(sys.argv[1]) if len(sys.argv) > 1 else 800
gold = collections.defaultdict(dict)
for q in load_questions():
    if q.source == "cubicasa5k" and q.split == "train" and q.lang_en:
        t = template_of(q.question)
        if t:
            gold[q.path][t] = int(q.answer)
from stoa.convert.cubicasa_svg import svg_for
paths = [p for p in sorted(gold) if os.path.exists(svg_for(p))][:N]
acc = collections.defaultdict(lambda: [0, 0]); size = collections.Counter(); misses = collections.defaultdict(list)
for p in paths:
    A = load_annotation(p, "train")
    W, H = Image.open(os.path.join(DATA_ROOT, p)).size
    size[(round(W / A["width"], 2), round(H / A["height"], 2))] += 1
    for t, g in gold[p].items():
        for rn, fn in RULES.get(t, {}).items():
            v = fn(A)
            acc[(t, rn)][0] += 1; acc[(t, rn)][1] += (v == g)
            if v != g and len(misses[(t, rn)]) < 4:
                misses[(t, rn)].append((p.split("/")[-1], g, v))
print("png/svg size ratio:", size.most_common(5))
for (t, rn), (n, k) in sorted(acc.items()):
    print(f"{t:12s} {rn:28s} n={n:4d} acc={k/n:.3f}  e.g. {misses[(t, rn)][:3]}")
