#!/usr/bin/env python3
"""Evaluate a VLM on the historic eval set WITH vs WITHOUT the per-drawing context block.

  # no model needed: context coverage / bucket statistics
  python scripts/context_eval.py --dry-run
  # base model zero-shot and fine-tuned LoRA (vLLM, OpenAI-compatible endpoint)
  python scripts/context_eval.py --model Qwen/Qwen3.5-4B --style zs --run-name hist-qwen35-4b-zs --hourly-eur 1.65
  python scripts/context_eval.py --model stoa-ft --style ft --run-name hist-ft --hourly-eur 1.65

Modes (--modes): noctx (image + question), ctx (image + context block + question), ctx-noweb (record fields only).
Writes results/runs/<run>.{jsonl,md}; appends one row per mode to the historic table in results/leaderboard.md.
"""
import argparse, asyncio, collections, datetime, json, os, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from stoa.context.build import load_context  # noqa: E402
from stoa.context.prompt import render  # noqa: E402
from stoa.context.score import is_correct, bucket  # noqa: E402

LB_HEADER = ("\n## Historic drawings: with vs without archive/web context\n\n"
             "Auto-appended by `scripts/context_eval.py` on `results/samples/historic_eval.jsonl` (hand-labelled, 4 historic sources). "
             "lookup = answer appears verbatim in the context block; derived = needs translation/reasoning from the record; "
             "visual = judged from the image only. Per-run details in `results/runs/<run>.md`.\n\n"
             "| date | run | model | mode | n | acc | lookup | derived | visual | habs | finna | europeana | wikimedia | ctx tok/q | €/1k q | notes |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def load_rows(split):
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "results/samples/historic_eval.jsonl"))]
    return [r for r in rows if split == "all" or r["split"] == split]


def ctx_text(path, web=True):
    return render(load_context(path), 1400, web=web)


def acc(rs):
    return (sum(r["correct"] for r in rs) / len(rs)) if rs else None


async def run_mode(method, rows, conc):
    sem = asyncio.Semaphore(conc)

    async def one(r):
        async with sem:
            t0 = time.time()
            try:
                p = await method.answer(r["path"], r["question"])
            except Exception as e:
                p = {"value": None, "error": repr(e)[:300]}
            p.setdefault("latency_s", time.time() - t0)
            return p
    return await asyncio.gather(*[one(r) for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--base-url", default="http://localhost:8000/v1"); ap.add_argument("--api-key-env")
    ap.add_argument("--style", default="zs", choices=["zs", "ft"]); ap.add_argument("--modes", default="noctx,ctx,ctx-noweb")
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"]); ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--max-pixels", type=int, default=2_000_000); ap.add_argument("--run-name")
    ap.add_argument("--hourly-eur", type=float); ap.add_argument("--notes", default=""); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = load_rows(a.split)
    for r in rows:
        r["bucket"] = bucket(r, ctx_text(r["path"]))
        r["bucket_noweb"] = bucket(r, ctx_text(r["path"], web=False))
        r["has_context"] = load_context(r["path"]) is not None
    bc = collections.Counter(r["bucket"] for r in rows)
    print(f"{len(rows)} questions, {len({r['path'] for r in rows})} drawings, context files present for "
          f"{sum(r['has_context'] for r in rows)}; buckets (with web): {dict(bc)}; "
          f"record-only: {dict(collections.Counter(r['bucket_noweb'] for r in rows))}")
    if a.dry_run:
        return
    from stoa.context.method import HistoricVLM
    key = os.environ.get(a.api_key_env, "EMPTY") if a.api_key_env else "EMPTY"
    out_rows, summary = [], {}
    for mode in a.modes.split(","):
        m = HistoricVLM(a.model, a.base_url, use_context=mode != "noctx", style=a.style, api_key=key,
                        max_pixels=a.max_pixels, web=mode == "ctx")
        t0 = time.time()
        preds = asyncio.run(run_mode(m, rows, a.concurrency))
        wall = time.time() - t0
        rs = []
        for r, p in zip(rows, preds):
            rr = {**r, "mode": mode, "pred": p, "correct": is_correct(r, p.get("value"))}
            rs.append(rr)
        out_rows += rs
        ctok = [len(ctx_text(r["path"], web=mode == "ctx")) / 3.5 if mode != "noctx" else 0 for r in rows]
        summary[mode] = {
            "n": len(rs), "acc": acc(rs), "wall": wall, "errors": sum(1 for r in rs if r["pred"].get("error")),
            "by_bucket": {b: acc([r for r in rs if r["bucket"] == b]) for b in ("lookup", "derived", "visual")},
            "n_bucket": {b: sum(1 for r in rs if r["bucket"] == b) for b in ("lookup", "derived", "visual")},
            "by_source": {s: acc([r for r in rs if r["source"] == s]) for s in ("habs", "finna", "europeana", "wikimedia")},
            "by_origin": {o: acc([r for r in rs if r["origin"] == o]) for o in ("record", "record+reasoning", "image")},
            "by_split": {s: acc([r for r in rs if r["split"] == s]) for s in ("dev", "test")},
            "by_qtype": {q: acc([r for r in rs if r["qtype"] == q]) for q in sorted({r["qtype"] for r in rs})},
            "tok_in": sum((r["pred"].get("tokens_in") or 0) for r in rs) / len(rs), "ctx_tok_est": sum(ctok) / len(ctok),
            "cost_1k": (a.hourly_eur * wall / 3600 / len(rs) * 1000) if a.hourly_eur else None,
        }
        print(mode, json.dumps(summary[mode], indent=None, default=str)[:600], flush=True)
    os.makedirs(os.path.join(ROOT, "results/runs"), exist_ok=True)
    with open(os.path.join(ROOT, f"results/runs/{a.run_name}.jsonl"), "w") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f2 = lambda x: "-" if x is None else f"{x:.3f}"
    md = [f"# Historic context run {a.run_name}", "", f"- date: {datetime.datetime.now().isoformat(timespec='minutes')}",
          f"- model: {a.model} style: {a.style} split: {a.split} endpoint: vLLM OpenAI-compatible", f"- questions: {len(rows)}; buckets {dict(bc)}", "",
          "| mode | n | acc | lookup | derived | visual | dev | test | record | record+reasoning | image | in tok/q | €/1k q |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for mode, s in summary.items():
        md.append(f"| {mode} | {s['n']} | {f2(s['acc'])} | {f2(s['by_bucket']['lookup'])} | {f2(s['by_bucket']['derived'])} | "
                  f"{f2(s['by_bucket']['visual'])} | {f2(s['by_split']['dev'])} | {f2(s['by_split']['test'])} | "
                  f"{f2(s['by_origin']['record'])} | {f2(s['by_origin']['record+reasoning'])} | {f2(s['by_origin']['image'])} | "
                  f"{s['tok_in']:.0f} | {f2(s['cost_1k'])} |")
    md += ["", "| mode | " + " | ".join(next(iter(summary.values()))["by_qtype"]) + " |",
           "|---|" + "---|" * len(next(iter(summary.values()))["by_qtype"])]
    for mode, s in summary.items():
        md.append(f"| {mode} | " + " | ".join(f2(v) for v in s["by_qtype"].values()) + " |")
    # paired comparison: questions that flipped
    if "noctx" in summary and "ctx" in summary:
        by = collections.defaultdict(dict)
        for r in out_rows:
            by[r["id"]][r["mode"]] = r["correct"]
        gain = sum(1 for v in by.values() if v.get("ctx") and not v.get("noctx"))
        loss = sum(1 for v in by.values() if v.get("noctx") and not v.get("ctx"))
        md += ["", f"Paired: context fixed {gain} questions and broke {loss} (of {len(by)})."]
    rep = "\n".join(md)
    open(os.path.join(ROOT, f"results/runs/{a.run_name}.md"), "w").write(rep + "\n")
    print(rep)
    lb = os.path.join(ROOT, "results/leaderboard.md")
    txt = open(lb).read() if os.path.exists(lb) else "# Leaderboard\n"
    with open(lb, "a") as f:
        if "## Historic drawings: with vs without" not in txt:
            f.write(LB_HEADER)
        for mode, s in summary.items():
            f.write(f"| {datetime.date.today()} | {a.run_name} | {a.model} ({a.style}) | {mode} | {s['n']} | {f2(s['acc'])} | "
                    f"{f2(s['by_bucket']['lookup'])} | {f2(s['by_bucket']['derived'])} | {f2(s['by_bucket']['visual'])} | "
                    + " | ".join(f2(s["by_source"][x]) for x in ("habs", "finna", "europeana", "wikimedia"))
                    + f" | {s['ctx_tok_est']:.0f} | {f2(s['cost_1k'])} | {a.notes} |\n")


if __name__ == "__main__":
    main()
