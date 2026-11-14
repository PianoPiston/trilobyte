#!/usr/bin/env python3
"""Stoa evaluation harness.

  # build the fixed balanced val sample (one language per EN/translation pair, image-answerable cells)
  python eval.py make-sample --split val --name val300
  # evaluate a method on a sample (or a whole split) and log to results/leaderboard.md
  python eval.py run --sample val300 --method vlm --model Qwen/Qwen3-VL-4B-Instruct \
      --base-url http://localhost:8000/v1 --run-name qwen3vl4b-zs --hourly-eur 1.5

Any method exposing `async answer(path, question) -> {value, evidence, confidence, ...}` can be plugged in
(see src/stoa/methods/). Scoring rules: src/stoa/scoring.py (official tolerance).
Cost per 1k questions for self-hosted runs = GPU €/h x wall-clock / n x 1000 (at the run's concurrency);
for token-priced APIs = tokens x price.
"""
import argparse, asyncio, collections, datetime, json, os, random, statistics, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
from stoa.data import load_questions, cell, image_path_for  # noqa: E402
from stoa.scoring import is_correct, rel_error, FC_THRESHOLD  # noqa: E402

RES = os.path.join(ROOT, "results")
SAMPLE_ALLOC = {  # balanced val sample, ~300 image-answerable questions
    "cubicasa5k/count": 90, "swiss_dwellings/count": 60, "swiss_dwellings/area": 60,
    "ifc_models/area": 30, "ifc_models/count": 25, "ifc_models/volume": 10, "ifc_models/length": 10,
    "opening_design/count": 999, "opening_design/text": 999, "opening_design/area": 999,
}


def make_sample(args):
    qs = [q for q in load_questions() if q.split == args.split]
    rng = random.Random(args.seed)
    by_pair = collections.defaultdict(list)
    for q in qs:
        by_pair[q.pair].append(q)
    one_per_pair = [rng.choice(v) for _, v in sorted(by_pair.items())]  # EN/FI dedupe
    by_cell = collections.defaultdict(list)
    for q in one_per_pair:
        if image_path_for(q.path) is not None:
            by_cell[cell(q)].append(q)
    alloc = SAMPLE_ALLOC if args.per_cell is None else collections.defaultdict(lambda: args.per_cell)
    out = []
    for c in sorted(by_cell):
        n = alloc.get(c, 0) if args.per_cell is None else args.per_cell
        pool = by_cell[c]
        rng.shuffle(pool)
        # spread across drawings: round-robin over groups
        per_group = collections.defaultdict(list)
        for q in pool:
            per_group[q.path].append(q)
        rr, keys = [], list(per_group)
        while any(per_group.values()) and len(rr) < n:
            for k in keys:
                if per_group[k] and len(rr) < n:
                    rr.append(per_group[k].pop())
        out += rr
    os.makedirs(os.path.join(RES, "samples"), exist_ok=True)
    fn = os.path.join(RES, "samples", f"{args.name}.jsonl")
    with open(fn, "w") as f:
        for q in out:
            f.write(json.dumps(q.to_json(), ensure_ascii=False) + "\n")
    print(fn, len(out), collections.Counter(cell(q) for q in out))


def load_items(args):
    if args.sample:
        fn = os.path.join(RES, "samples", f"{args.sample}.jsonl")
        return [json.loads(l) for l in open(fn)]
    qs = [q for q in load_questions() if q.split == args.split]
    seen, items = set(), []
    for q in qs:  # dedupe pairs: keep first (English) row
        if q.pair in seen:
            continue
        seen.add(q.pair)
        items.append(q.to_json())
    if args.source:
        items = [it for it in items if it["source"] in args.source.split(",")]
    if args.limit:
        random.Random(0).shuffle(items)
        items = items[: args.limit]
    return items


def build_method(args):
    if args.method == "vlm":
        from stoa.methods.vlm import VLMMethod
        extra = json.loads(args.extra_body) if args.extra_body else {}
        key = os.environ.get(args.api_key_env, "EMPTY") if args.api_key_env else "EMPTY"
        return VLMMethod(args.model, args.base_url, api_key=key, max_pixels=args.max_pixels,
                         prompt=args.prompt, max_tokens=args.max_tokens, extra_body=extra,
                         logprobs=not args.no_logprobs, min_pixels=args.min_pixels)
    if args.method == "vlm-ft-ground":  # --model = LoRA name, --base-model = base name on same server
        from stoa.methods.vlm import FTWithEvidence
        extra = json.loads(args.extra_body) if args.extra_body else {}
        return FTWithEvidence(args.model, args.base_model, args.base_url, max_pixels=args.max_pixels, extra_body=extra)
    if args.method == "swiss-dxf":
        from stoa.methods.swiss_dxf import SwissDXFMethod
        return SwissDXFMethod()
    if args.method == "ifc":
        from stoa.methods.ifc_route import IFCMethod
        return IFCMethod()
    if args.method == "router":  # deterministic routes, then VLM (--model, --prompt) fallback
        from stoa.methods.swiss_dxf import SwissDXFMethod
        from stoa.methods.router import Router
        from stoa.methods.vlm import VLMMethod
        extra = json.loads(args.extra_body) if args.extra_body else {}
        fb = VLMMethod(args.model, args.base_url, max_pixels=args.max_pixels, prompt=args.prompt,
                       max_tokens=args.max_tokens, extra_body=extra, min_pixels=args.min_pixels) if args.model else None
        from stoa.methods.ifc_route import IFCMethod
        return Router([SwissDXFMethod(), IFCMethod()], fb)
    if args.method == "std-router":  # standardized files + detector + fine-tuned VLM (--model = LoRA name)
        from stoa.methods.std_router import StdRouter
        from stoa.methods.vlm import VLMMethod, FTWithEvidence
        extra = json.loads(args.extra_body) if args.extra_body else {}
        vlm = None
        if args.vlm_cache:
            from stoa.methods.vlm import CachedVLM
            vlm = CachedVLM(args.vlm_cache.split(","))
        elif args.model:
            vlm = (FTWithEvidence(args.model, args.base_model, args.base_url, max_pixels=args.max_pixels, extra_body=extra)
                   if args.base_model else
                   VLMMethod(args.model, args.base_url, max_pixels=args.max_pixels, prompt="ft", max_tokens=64, extra_body=extra))
        return StdRouter(vlm, det_cache=args.det_cache, det_policy=args.det_policy, policy=args.policy)
    if args.method == "oracle-null":
        class Null:
            async def answer(self, p, q): return {"value": None}
        return Null()
    raise SystemExit(f"unknown method {args.method}")


async def run_all(method, items, conc):
    sem = asyncio.Semaphore(conc)
    done = [0]

    async def one(it):
        async with sem:
            t0 = time.time()
            try:
                r = await method.answer(it["path"], it["question"])
            except Exception as e:
                r = {"value": None, "error": repr(e)[:300]}
            r.setdefault("latency_s", time.time() - t0)
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]}/{len(items)}", flush=True)
            return {**it, "pred": r}
    return await asyncio.gather(*[one(it) for it in items])


def summarize(rows):
    cells = collections.defaultdict(list)
    for r in rows:
        cells[cell_of(r)].append(r)
    table = {}
    for c, rs in sorted(cells.items()):
        table[c] = stats(rs)
    allst = stats(rows)
    macro = statistics.mean(v["acc"] for v in table.values()) if table else 0
    return table, allst, macro


def cell_of(r):
    fmt = os.path.splitext(r["path"])[1].lstrip(".").lower()
    return f"{r['source']}/{r['type']}" + ("/ifc" if fmt == "ifc" and r["source"] == "ifc_models" else "")


def stats(rs):
    n = len(rs)
    corr = [is_correct(r["type"], r["pred"].get("value"), r["answer"]) for r in rs]
    abst = [r["pred"].get("value") is None for r in rs]
    conf = [r["pred"].get("confidence") for r in rs]
    fc = [(not c) and (not a) and (cf is not None and cf >= FC_THRESHOLD) for c, a, cf in zip(corr, abst, conf)]
    answered = n - sum(abst)
    rels = [rel_error(r["pred"].get("value"), r["answer"]) for r in rs if r["type"] in ("area", "length", "volume")]
    rels = [x for x in rels if x is not None]
    errs = sum(1 for r in rs if r["pred"].get("error"))
    return {"n": n, "acc": sum(corr) / n if n else 0, "abstain": sum(abst) / n if n else 0,
            "prec": (sum(corr) / answered) if answered else 0, "false_conf": sum(fc) / n if n else 0,
            "med_rel_err": statistics.median(rels) if rels else None, "errors": errs}


def run(args):
    items = load_items(args)
    for it in items:
        assert it["split"] != "train", "refusing to evaluate on train drawings"
    method = build_method(args)
    print(f"evaluating {len(items)} questions with {args.method} {args.model or ''}")
    t0 = time.time()
    rows = asyncio.run(run_all(method, items, args.concurrency))
    wall = time.time() - t0
    os.makedirs(os.path.join(RES, "runs"), exist_ok=True)
    with open(os.path.join(RES, "runs", f"{args.run_name}.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    table, allst, macro = summarize(rows)
    n = len(rows)
    tin = [r["pred"].get("tokens_in") or 0 for r in rows]
    tout = [r["pred"].get("tokens_out") or 0 for r in rows]
    lat = sorted(r["pred"].get("latency_s", 0) for r in rows)
    cost_1k = None
    if args.hourly_eur:
        cost_1k = args.hourly_eur * wall / 3600 / n * 1000
    elif args.eur_per_mtok_in is not None:
        cost_1k = (sum(tin) * args.eur_per_mtok_in + sum(tout) * args.eur_per_mtok_out) / 1e6 / n * 1000
    lines = [f"# Run {args.run_name}", "", f"- date: {datetime.datetime.now().isoformat(timespec='minutes')}",
             f"- method: {args.method} model: {args.model} prompt: {args.prompt} max_pixels: {args.max_pixels} min_pixels: {args.min_pixels}",
             f"- items: {n} ({args.sample or args.split}) wall: {wall:.0f}s concurrency: {args.concurrency}",
             f"- tokens/q in {statistics.mean(tin):.0f} out {statistics.mean(tout):.0f}; latency p50 {lat[n//2]:.1f}s p90 {lat[int(n*0.9)]:.1f}s",
             f"- cost per 1k questions: {'€%.3f' % cost_1k if cost_1k is not None else 'n/a'}",
             f"- ALL: acc {allst['acc']:.3f} | macro-by-cell {macro:.3f} | abstain {allst['abstain']:.3f} | precision {allst['prec']:.3f} | false-confident(>= {FC_THRESHOLD}) {allst['false_conf']:.3f} | errors {allst['errors']}",
             "", "| cell | n | acc | abstain | precision | false-conf | median rel err |", "|---|---|---|---|---|---|---|"]
    for c, s in table.items():
        mre = f"{s['med_rel_err']:.3f}" if s["med_rel_err"] is not None else ""
        lines.append(f"| {c} | {s['n']} | {s['acc']:.3f} | {s['abstain']:.2f} | {s['prec']:.3f} | {s['false_conf']:.3f} | {mre} |")
    meth = collections.defaultdict(list)
    for r in rows:
        meth[r["pred"].get("method") or args.method].append(r)
    if len(meth) > 1:
        lines += ["", "| route | n | acc | abstain |", "|---|---|---|---|"]
        for m, rs in sorted(meth.items()):
            st = stats(rs)
            lines.append(f"| {m} | {st['n']} | {st['acc']:.3f} | {st['abstain']:.2f} |")
    rep = "\n".join(lines)
    open(os.path.join(RES, "runs", f"{args.run_name}.md"), "w").write(rep + "\n")
    print(rep)
    lb = os.path.join(RES, "leaderboard.md")
    if not os.path.exists(lb):
        open(lb, "w").write("# Leaderboard\n\nAuto-appended by `eval.py run`. Per-cell details in `results/runs/<run>.md`.\n\n"
                            "| date | run | model | eval set | n | acc | macro | cubicasa cnt | swiss cnt | swiss area | ifc area | ifc cnt | abstain | false-conf | €/1k q | p50 s | notes |\n"
                            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    g = lambda c: f"{table[c]['acc']:.2f}" if c in table else "-"
    with open(lb, "a") as f:
        f.write(f"| {datetime.date.today()} | {args.run_name} | {args.model or args.method} | {args.sample or args.split} | {n} | "
                f"{allst['acc']:.3f} | {macro:.3f} | {g('cubicasa5k/count')} | {g('swiss_dwellings/count')} | {g('swiss_dwellings/area')} | "
                f"{g('ifc_models/area')} | {g('ifc_models/count')} | {allst['abstain']:.2f} | {allst['false_conf']:.3f} | "
                f"{'%.3f' % cost_1k if cost_1k is not None else 'n/a'} | {lat[n//2]:.1f} | {args.notes} |\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("make-sample"); s.add_argument("--split", default="val"); s.add_argument("--name", required=True)
    s.add_argument("--seed", type=int, default=0); s.add_argument("--per-cell", type=int)
    r = sub.add_parser("run")
    r.add_argument("--sample"); r.add_argument("--split", default="val"); r.add_argument("--limit", type=int)
    r.add_argument("--method", default="vlm"); r.add_argument("--model"); r.add_argument("--base-url", default="http://localhost:8000/v1")
    r.add_argument("--api-key-env"); r.add_argument("--base-model"); r.add_argument("--prompt", default="zs"); r.add_argument("--max-pixels", type=int, default=2_000_000); r.add_argument("--min-pixels", type=int, default=0)
    r.add_argument("--max-tokens", type=int, default=768); r.add_argument("--extra-body"); r.add_argument("--no-logprobs", action="store_true")
    r.add_argument("--concurrency", type=int, default=32); r.add_argument("--run-name", required=True)
    r.add_argument("--hourly-eur", type=float); r.add_argument("--eur-per-mtok-in", type=float); r.add_argument("--eur-per-mtok-out", type=float, default=0)
    r.add_argument("--notes", default="")
    r.add_argument("--source", help="comma-separated sources to keep");
    r.add_argument("--vlm-cache", help="comma-separated eval run JSONL files to replay VLM answers from");
    r.add_argument("--det-cache"); r.add_argument("--det-policy"); r.add_argument("--policy")
    a = ap.parse_args()
    if a.cmd == "run" and a.split == "test" and not os.environ.get("STOA_ALLOW_TEST"):
        raise SystemExit("test split is held out: set STOA_ALLOW_TEST=1 only for final reporting")
    {"make-sample": make_sample, "run": run}[a.cmd](a)


if __name__ == "__main__":
    main()
