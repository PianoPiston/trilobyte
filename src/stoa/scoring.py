"""Official-tolerance scoring.

count            : exact integer match
area/length/volume: |pred-gold| <= 2% of |gold|
text             : free-form. We use a deterministic normalized match (documented, no LLM judge):
                   correct if normalized strings are equal, OR every number in the gold answer appears
                   in the prediction AND token-recall of gold content words >= 0.6.
Abstain          : prediction value is None -> not correct, counted in abstain rate.
False-confident  : answered, wrong, and confidence >= FC_THRESHOLD.
"""
import re

TOL = 0.02
FC_THRESHOLD = 0.8
_NUM = re.compile(r"-?\d+(?:[.,]\d+)?")


def to_number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("−", "-").replace(" ", "").replace(" ", "")
    m = _NUM.search(s)
    if not m:
        return None
    t = m.group(0)
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _norm(s):
    return re.sub(r"[^\w.]+", " ", str(s).lower()).strip()


def text_match(pred, gold) -> bool:
    if pred is None:
        return False
    p, g = _norm(pred), _norm(gold)
    if p == g:
        return True
    gnums = {n.replace(",", ".") for n in _NUM.findall(str(gold))}
    pnums = {n.replace(",", ".") for n in _NUM.findall(str(pred))}
    if gnums and not gnums <= pnums:
        return False
    gw = {w for w in g.split() if len(w) > 2}
    if not gw:
        return bool(gnums)
    return len(gw & set(p.split())) / len(gw) >= 0.6


def is_correct(qtype: str, pred, gold) -> bool:
    if pred is None:
        return False
    if qtype == "text":
        return text_match(pred, gold)
    pv, gv = to_number(pred), to_number(gold)
    if pv is None or gv is None:
        return False
    if qtype == "count":
        return abs(pv - round(pv)) < 1e-6 and int(round(pv)) == int(round(gv))
    if gv == 0:
        return abs(pv) < 1e-9
    return abs(pv - gv) <= TOL * abs(gv)


def rel_error(pred, gold):
    pv, gv = to_number(pred), to_number(gold)
    if pv is None or gv is None or gv == 0:
        return None
    return abs(pv - gv) / abs(gv)
