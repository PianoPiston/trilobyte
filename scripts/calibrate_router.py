"""Choose the StdRouter policy on a VAL "collect" run (router run with policy=None, which records all signals).
Per intent key, pick the accept-rule set with maximal coverage whose precision on answered questions is >= TARGET
and whose Wilson 95% lower bound is >= MIN_LB. Never run this on test.
usage: python -I scripts/calibrate_router.py results/runs/VAL-collect.jsonl results/policy.json"""
import collections, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.scoring import is_correct

TARGET, MIN_LB = 0.99, 0.95


def wilson_lb(k, n, z=1.96):
    if n == 0:
        return 0
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


rows = [json.loads(l) for l in open(sys.argv[1])]
assert all(r["split"] != "test" for r in rows), "calibrate on VAL only"
policy = {"det_rules": {}, "vlm_threshold": {}, "report": {}}
det = collections.defaultdict(list); vlm = collections.defaultdict(list)
for r in rows:
    p = r["pred"]
    gold = r["answer"]
    if "det_value" in p:
        det[p["intent_key"]].append((p, gold, r["type"]))
    elif str(p.get("method", "")).startswith("vlm-ft") and not p.get("vlm_missing") and (p.get("value") is not None or p.get("vlm_value") is not None):
        key = f"{r['source']}|{p.get('intent_key')}"
        v = p.get("value") if p.get("value") is not None else p.get("vlm_value")
        vlm[key].append((p.get("confidence"), is_correct(r["type"], v, gold) if v is not None else False))

CANDS = [[], ["agree_clean"], ["agree"], ["det_clean"], ["agree", "det_clean"], ["tta"], ["agree_tta"], ["agree_tta", "tta"]]
for th in (0.99, 0.95, 0.9, 0.8):
    CANDS += [["agree_tta", f"vlm>={th}"], ["tta", f"vlm>={th}"], ["agree_tta", "tta", f"vlm>={th}"], ["agree", f"vlm>={th}"], ["agree", "det_clean", f"vlm>={th}"], [f"vlm>={th}"], ["agree_clean", f"vlm>={th}"]]


def apply(rules, p):
    for r in rules:
        if r == "agree" and p["agree"]:
            return p["det_value"]
        if r == "agree_clean" and p["agree"] and p["det_uncertain"] == 0:
            return p["det_value"]
        if r == "det_clean" and p["det_uncertain"] == 0 and p["det_value"] is not None:
            return p["det_value"]
        if r.startswith("vlm>=") and p.get("vlm_conf") is not None and p["vlm_conf"] >= float(r[5:]):
            return p["vlm_value"]
        if r == "tta" and p.get("tta_stable"):
            return p["det_value"]
        if r == "agree_tta" and p["agree"] and p.get("tta_stable"):
            return p["det_value"]
    return None


for key, items in sorted(det.items()):
    best = ([], 0, 0, 1.0, 1.0, 0)
    for rules in CANDS:
        uses_vlm = any(r not in ("det_clean", "tta") for r in rules)
        sub = [x for x in items if x[0].get("vlm_value") is not None] if uses_vlm else items
        if not sub:
            continue
        ans = [(apply(rules, p), g, t) for p, g, t in sub]
        ans = [(v, g, t) for v, g, t in ans if v is not None]
        k = sum(is_correct(t, v, g) for v, g, t in ans)
        n = len(ans)
        prec = k / n if n else 1.0
        cov = n / len(sub)
        if n and prec >= TARGET and wilson_lb(k, n) >= MIN_LB and cov > best[1]:
            best = (rules, cov, k, prec, wilson_lb(k, n), len(sub))
    if len(best) == 5:
        best = best + (0,)
    policy["det_rules"][key] = best[0]
    policy["report"][f"cubicasa5k|{key}"] = {"n": len(items), "n_eval": best[5], "coverage": round(best[1], 3), "precision": round(best[3], 4),
                                            "wilson_lb": round(best[4], 4), "rules": best[0]}
# suggestion shown with "needs check": the more accurate of detector / VLM on VAL, per detector key
policy["suggest"] = {}
for key, items in sorted(det.items()):
    d_ok = sum(is_correct(t, p["det_value"], g) for p, g, t in items if p.get("det_value") is not None)
    v_ok = sum(is_correct(t, p["vlm_value"], g) for p, g, t in items if p.get("vlm_value") is not None)
    policy["suggest"][key] = "detector" if d_ok >= v_ok else "vlm"
    policy["report"][f"cubicasa5k|{key}"]["suggest"] = {"detector_acc": round(d_ok / len(items), 3), "vlm_acc": round(v_ok / len(items), 3)}
for key, items in sorted(vlm.items()):
    best_t, best_n, best = 1.01, 0, (1.0, 1.0)
    for th in sorted({round(c, 3) for c, _ in items if c is not None}, reverse=True):
        sel = [ok for c, ok in items if c is not None and c >= th]
        k, n = sum(sel), len(sel)
        if n and k / n >= TARGET and wilson_lb(k, n) >= MIN_LB and n > best_n:
            best_t, best_n, best = th, n, (k / n, wilson_lb(k, n))
    policy["vlm_threshold"][key] = best_t
    policy["report"][key] = {"n": len(items), "coverage": round(best_n / len(items), 3), "precision": round(best[0], 4),
                             "wilson_lb": round(best[1], 4), "threshold": best_t}
json.dump(policy, open(sys.argv[2], "w"), indent=1)
for k, v in policy["report"].items():
    print(f"{k:45s} {v}")
