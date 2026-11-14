"""Backend smoke test (no server needed): ~/venvs/stoa-app/bin/python -I app/tests/smoke.py"""
import sys, asyncio, json, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app.api import engine as E, catalog as CAT, search as S, benchmark as B


async def main():
    for did in ["swiss_dwellings~site3634_bldg5596_floor24203", "cubicasa5k~high_quality-12130",
                "ifc_models~kit-fzk-haus_ac20-fzk-haus_plan-01-erdgeschoss", "finna~hka.139879309684900_166878548098200",
                "opening_design~A-801 - Door and Finish Schedules & Wall Types"]:
        d = CAT.describe_full(did)
        print("==", did, d["split"], d["licence"], d["image_size"], len(d["examples"]))
        for ex in d["examples"][:4]:
            t = time.time()
            r = await E.ask(did, ex["question"])
            ref = r.get("reference") or {}
            print(f"  {ex['question'][:70]!r} -> {r['answer']} {r['unit']} [{r['method']}] conf={r['confidence']} "
                  f"nc={r['needs_check']} ev={len(r['evidence'])} ref={ref.get('answer')} match={ref.get('match')} {time.time() - t:.2f}s")
            if r["evidence"]:
                print("     ev0", json.dumps(r["evidence"][0])[:200])
        layer, s = E.std_layer(d)
        print("  layer", None if layer is None else len(layer), s and s["counts"])
    print(S.search("3 bedrooms and a sauna")["total"], S.search("kolme makuuhuonetta ja sauna")["parsed"])
    print([(r["id"], r["score"]) for r in S.search("Helsinki 1909")["results"][:3]])
    b = B.benchmark()
    print(b["headline"]["header"], b["per_source"]["hybrid router (DXF + IFC + fine-tuned VLM)"]["all"])

asyncio.run(main())
