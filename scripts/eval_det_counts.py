"""Detector-only exact-count accuracy per cubicasa question kind, thresholds picked on the TRAIN hold-out, reported on VAL.
usage: python scripts/eval_det_counts.py dets.jsonl [labels.jsonl] [val_collect.jsonl]
Also reports the VLM (cached in the VAL collect run), 'either right' (oracle) and detector==VLM agreement."""
import collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.convert.raster_model import dedupe_openings

KIND = {"doors": ["door"], "windows": ["window"], "toilet": ["toilet"], "sink": ["sink"], "showers_baths": ["shower", "bathtub"],
        "saunas": ["sauna_stove"], **{f"count_room_type:{r}": [f"room_{r}"] for r in ("bedroom", "kitchen", "bath", "wc", "balcony")}}
RULES = {"window": {"overlap": 0.3, "gap": -1}, "door": {"overlap": 0.3, "gap": 3}}


def count(d, classes, thr):
    ds = [x for x in d["dets"] if x["cls"] in classes and x["score"] >= thr]
    return len(dedupe_openings(ds, RULES))


def main():
    dets = {}
    for l in open(sys.argv[1]):
        d = json.loads(l); dets[d["path"]] = d
    labels = sys.argv[2] if len(sys.argv) > 2 else "artifacts/det2/det_train_v2.jsonl"
    val = sys.argv[3] if len(sys.argv) > 3 else "results/runs/VAL-collect-det2.jsonl"
    hold = [json.loads(l) for l in open(labels)]
    hold = [r for r in hold if r["holdout"] and r["path"] in dets]
    rows = [json.loads(l) for l in open(val)]
    rows = [r for r in rows if r["source"] == "cubicasa5k" and r["split"] == "val" and r["path"] in dets]
    grid = [x / 100 for x in range(20, 96, 2)]
    tot = collections.Counter()
    print(f"hold-out drawings {len(hold)}; val questions {len(rows)}")
    print("kind                      n    thr  hold   det    vlm    either agree_cov agree_prec within1")
    for kind, classes in KIND.items():
        def gold(r):
            return sum(r["counts"].get(c, 0) for c in classes)
        thr = max(grid, key=lambda t: sum(count(dets[r["path"]], classes, t) == gold(r) for r in hold))
        hacc = sum(count(dets[r["path"]], classes, thr) == gold(r) for r in hold) / max(1, len(hold))
        c = collections.Counter()
        for r in rows:
            if r["pred"].get("intent_key") != kind:
                continue
            n, v, g = count(dets[r["path"]], classes, thr), r["pred"].get("vlm_value"), r["answer"]
            c["n"] += 1; c["det"] += n == g; c["vlm"] += v == g; c["either"] += n == g or v == g
            c["agree"] += n == v; c["agree_ok"] += n == v == g; c["w1"] += abs(n - g) <= 1
        n = max(1, c["n"]); tot.update(c)
        print(f"{kind:25s} {c['n']:4d} {thr:.2f} {hacc:.3f}  {c['det']/n:.3f}  {c['vlm']/n:.3f}  {c['either']/n:.3f}  {c['agree']/n:.2f}      {c['agree_ok']/max(1,c['agree']):.3f}     {c['w1']/n:.3f}")
    n = tot["n"]
    print(f"{'ALL (no floors)':25s} {n:4d}             {tot['det']/n:.3f}  {tot['vlm']/n:.3f}  {tot['either']/n:.3f}")


main()
