"""Old app routing vs. new candidates + decision (deterministic ranking / LLM judge), on a fixed drawing sample.

  python scripts/eval_judge.py --split val --n 150 --out results/runs/judge_val.jsonl
  python scripts/eval_judge.py --split val --rescore results/runs/judge_val.jsonl     # re-decide with the current policy
Gold answers are read ONLY here, for scoring, after every pipeline has produced its prediction. TEST: only with
STOA_ALLOW_TEST=1, once, after the policy is fixed on VAL.
old   = previous app behaviour: detector file answer if it answers, else the fine-tuned VLM (guess < 0.3 -> no answer)
det   = new pipeline, deterministic ranking (VAL-calibrated policy)
judge = new pipeline, LLM judge (Qwen3.5-4B base, text-only) over the same candidates
"""
import argparse, asyncio, collections, json, os, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("STOA_VLM_BASE_URL", "http://127.0.0.1:8000/v1")
os.environ["STOA_OCR_ON_ASK"] = "0"
from app.api import config as C  # noqa: E402
C.LIVE_CACHE = os.path.join(ROOT, "app", ".cache", "eval_live_cache.jsonl")  # keep eval calls out of the app cache
from app.api import engine as E, catalog as CAT  # noqa: E402
from app.api.vlm_client import VLM  # noqa: E402
from stoa.answer import parse_intent  # noqa: E402
from stoa.decide import decide, final_confidence, load_policy, scope_key_for  # noqa: E402
from stoa.scoring import is_correct  # noqa: E402
from scripts.build_words import sample_paths  # noqa: E402


JUDGE_ALL = True


def kind_of(question):
    i = parse_intent(question)
    return i["kind"] + (":" + i["type"] if i.get("type") else "") + (":" + i["symbol"] if i.get("symbol") else "")


def old_pick(cands):
    det = [c for c in cands if c["source"] == "detector"]
    if det:
        return det[0]["value"], det[0]["confidence"]
    v = [c for c in cands if c["source"] == "vlm"]
    if v:
        conf = v[0]["confidence"]
        return (v[0]["value"] if conf is not None and conf >= C.CONF_SUGGEST else None), conf
    return None, None


async def redecide(question, scope, cands, judge, policy):
    sk = scope_key_for(question, scope)
    raw = [{k: c[k] for k in ("value", "unit", "scope", "source", "confidence", "reason", "flags") if k in c} for c in cands]
    if judge and JUDGE_ALL:
        policy = {**policy, "judge_scopes": None}  # calibration: let the judge rank every kind
    dec = await decide(question, scope, raw, chat=(E._judge_chat if judge else None), use_judge=judge, scope_key=sk, policy=policy)
    if not dec["ranked"]:
        return None, None, dec
    top = dec["ranked"][0]
    return top["value"], final_confidence(top, dec["ranked"], policy=policy, scope_key=sk), dec


async def run(a):
    if a.split == "test" and os.environ.get("STOA_ALLOW_TEST") != "1":
        sys.exit("TEST needs STOA_ALLOW_TEST=1")
    from stoa.data import load_questions
    paths = set(sample_paths("cubicasa5k", a.split, a.n))
    qs = [q for q in load_questions() if q.path in paths and q.lang_en]
    if a.kinds:
        ks = a.kinds.split(",")
        qs = [q for q in qs if any(kind_of(q.question).startswith(k) for k in ks)]
    print(len(paths), "drawings", len(qs), "questions", flush=True)
    sem = asyncio.Semaphore(a.conc)
    out = open(a.out, "w")

    async def one(q):
        async with sem:
            did = "cubicasa5k~" + os.path.splitext(os.path.basename(q.path))[0]
            t0 = time.time()
            r = await E.ask(did, q.question, use_judge=False, use_cache=False)
            rec = {"path": q.path, "question": q.question, "kind": kind_of(q.question), "scope": r.get("question_scope"),
                   "cands": [{k: c[k] for k in ("value", "unit", "scope", "source", "confidence", "reason", "flags")} for c in r["ranked_candidates"]],
                   "latency_s": round(time.time() - t0, 2)}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()

    await asyncio.gather(*[one(q) for q in qs])
    out.close()


async def score(a):
    from stoa.data import load_questions
    recs = [json.loads(l) for l in open(a.rescore)]
    gold = {(q.path, q.question): q for q in load_questions()}
    policy = load_policy() if not a.no_policy else {}
    rows = collections.defaultdict(lambda: collections.Counter())
    src_acc = collections.defaultdict(lambda: collections.Counter())
    agree_acc = collections.defaultdict(lambda: collections.Counter())
    judge_lat, judge_tok = [], []
    sem = asyncio.Semaphore(a.conc)
    detail = []

    async def one(r):
        g = gold[(r["path"], r["question"])]
        ok = lambda v: v is not None and bool(is_correct(g.type, v, g.answer))  # noqa: E731
        k = r["kind"]
        ov, oc = old_pick(r["cands"])
        async with sem:
            dv, dc, _ = await redecide(r["question"], r["scope"], r["cands"], False, policy)
            jv, jc, jd = await redecide(r["question"], r["scope"], r["cands"], True, policy) if a.judge else (dv, dc, None)
        if jd and jd.get("judge") and "latency_s" in jd["judge"]:
            judge_lat.append(jd["judge"]["latency_s"]); judge_tok.append(jd["judge"].get("tokens_in", 0) + jd["judge"].get("tokens_out", 0))
        for name, v, c in (("old", ov, oc), ("det", dv, dc), ("judge", jv, jc)):
            rows[k][name + "_n"] += 1
            rows[k][name + "_best"] += ok(v)
            auto = v is not None and c is not None and c >= C.CONF_AUTO
            rows[k][name + "_auto"] += auto
            rows[k][name + "_auto_ok"] += auto and ok(v)
        for c in r["cands"]:
            src = c["source"] + (":" + (c.get("reason") or "").split(" ")[0] if False else "")
            src_acc[(k, c["source"])]["n"] += 1
            src_acc[(k, c["source"])]["ok"] += ok(c["value"])
        # agreement patterns among sources (for the confidence policy)
        vals = {c["source"]: c["value"] for c in r["cands"]}
        for combo in (("text", "detector"), ("text", "vlm"), ("detector", "vlm"), ("text", "detector", "vlm")):
            if all(s in vals for s in combo) and len({json.dumps(vals[s]) for s in combo}) == 1:
                agree_acc[(k, "+".join(combo))]["n"] += 1
                agree_acc[(k, "+".join(combo))]["ok"] += ok(vals[combo[0]])
        detail.append({"path": r["path"], "kind": k, "old": ov, "det": dv, "judge": jv, "ok_old": ok(ov), "ok_det": ok(dv), "ok_judge": ok(jv)})

    await asyncio.gather(*[one(r) for r in recs])
    print(f"\n{'kind':34s} {'n':>4s} | {'old best':>8s} {'det best':>8s} {'jdg best':>8s} | auto cov/prec old, det, judge")
    tot = collections.Counter()
    for k in sorted(rows):
        R = rows[k]; n = R["old_n"]
        for key in R:
            tot[key] += R[key]
        f = lambda nm: f"{R[nm + '_auto'] / n:.2f}/{(R[nm + '_auto_ok'] / R[nm + '_auto']) if R[nm + '_auto'] else float('nan'):.3f}"  # noqa: E731
        print(f"{k:34s} {n:4d} | {R['old_best'] / n:8.3f} {R['det_best'] / n:8.3f} {R['judge_best'] / n:8.3f} | {f('old')}  {f('det')}  {f('judge')}")
    n = tot["old_n"]
    f = lambda nm: f"{tot[nm + '_auto'] / n:.2f}/{(tot[nm + '_auto_ok'] / tot[nm + '_auto']) if tot[nm + '_auto'] else float('nan'):.3f}"  # noqa: E731
    print(f"{'ALL':34s} {n:4d} | {tot['old_best'] / n:8.3f} {tot['det_best'] / n:8.3f} {tot['judge_best'] / n:8.3f} | {f('old')}  {f('det')}  {f('judge')}")
    print("\nper-source accuracy (when the source produced a candidate):")
    for (k, s), c in sorted(src_acc.items()):
        print(f"  {k:34s} {s:9s} n={c['n']:4d} acc={c['ok'] / c['n']:.3f}")
    print("\nagreement patterns:")
    for (k, s), c in sorted(agree_acc.items()):
        print(f"  {k:34s} {s:22s} n={c['n']:4d} acc={c['ok'] / c['n']:.3f}")
    if judge_lat:
        print(f"\njudge calls {len(judge_lat)}: mean latency {sum(judge_lat) / len(judge_lat):.2f} s (concurrent), mean tokens {sum(judge_tok) / len(judge_tok):.0f}")
    if a.write_policy:
        old_pol = load_policy()
        pol = {"note": f"calibrated on {a.split.upper()} only by scripts/eval_judge.py ({len(recs)} questions)", "source_order": {},
               "agreement_conf": {}, "veto_sources": {}, "judge_scopes": sorted(json.load(open(a.judge_from)).get("judge_scopes", [])) if a.judge_from else []}
        keys = sorted({k for k, _ in src_acc})
        for k in keys:
            sk = "count:" + k
            accs = {s: c["ok"] / c["n"] for (kk, s), c in src_acc.items() if kk == k and c["n"] >= 8}
            pol["source_order"][sk] = sorted(accs, key=lambda s: -accs[s])
            pol["veto_sources"][sk] = [s for s, v in accs.items() if v >= 0.85]
            if accs and max(accs.values()) < 0.9:
                pol.setdefault("conf_cap", {})[sk] = 0.65
            ag = {combo: c for (kk, combo), c in agree_acc.items() if kk == k and c["n"] >= 10 and c["ok"] / c["n"] >= 0.97}
            if ag:
                pol["agreement_conf"][sk] = {combo: 0.97 for combo in ag}
        if a.judge:
            pol["judge_scopes"] = sorted("count:" + k for k in rows if rows[k]["judge_best"] > rows[k]["det_best"])
            pol["deterministic_scopes"] = sorted("count:" + k for k in rows if rows[k]["judge_best"] <= rows[k]["det_best"])
        json.dump(pol, open(a.write_policy, "w"), indent=1)
        print("wrote", a.write_policy)
    if a.detail:
        with open(a.detail, "w") as f:
            for d in detail:
                f.write(json.dumps(d) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val"); ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--kinds", default=""); ap.add_argument("--out", default="results/runs/judge_val.jsonl")
    ap.add_argument("--rescore"); ap.add_argument("--judge", action="store_true"); ap.add_argument("--no-policy", action="store_true")
    ap.add_argument("--detail"); ap.add_argument("--write-policy"); ap.add_argument("--judge-from"); ap.add_argument("--conc", type=int, default=12)
    ap.add_argument("--judge-mode", default="all", choices=["all", "policy"])
    a = ap.parse_args()
    JUDGE_ALL = a.judge_mode == "all"
    asyncio.run(score(a) if a.rescore else run(a))
