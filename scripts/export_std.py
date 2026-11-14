"""Write one standardized drawing file per drawing (schema/drawing.schema.json) for the demo / search index.
  swiss_dwellings: exact files from the DXF; ifc_models: exact files from the IFC model;
  cubicasa5k: MODEL files from cached detector output (ground_truth_eligible=false).
usage: python -I scripts/export_std.py OUTDIR [--sources swiss_dwellings,ifc_models,cubicasa5k] [--dets dets.jsonl]
                                       [--det-policy policy.json] [--validate]"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from stoa.data import DATA_ROOT, load_questions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--sources", default="swiss_dwellings,ifc_models,cubicasa5k")
    ap.add_argument("--dets"); ap.add_argument("--det-policy"); ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    srcs = a.sources.split(",")
    paths = sorted({q.path for q in load_questions() if q.source in srcs})
    val = None
    if a.validate:
        import jsonschema
        schema = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schema", "drawing.schema.json")))
        val = jsonschema.Draft202012Validator(schema)
    dets = {}
    if a.dets:
        for l in open(a.dets):
            r = json.loads(l); dets[r["path"]] = r
    done, n = set(), 0
    for p in paths:
        src = p.split("/")[1]
        doc = None
        if src == "swiss_dwellings":
            from stoa.convert.swiss_dxf import for_question_path
            doc = for_question_path(p)
        elif src == "ifc_models":
            from stoa.convert.ifc_std import for_question_path
            doc = for_question_path(p)
        elif src == "cubicasa5k" and p in dets:
            from stoa.convert.raster_model import from_detections, load_policy
            d = dets[p]
            doc = from_detections(p, d["size"], d["dets"], load_policy(a.det_policy))
        if doc is None or doc["drawing_id"] in done:
            continue
        done.add(doc["drawing_id"])
        if val is not None:
            errs = list(val.iter_errors(doc))
            if errs:
                print("SCHEMA ERROR", doc["drawing_id"], errs[0].message[:200]); continue
        fn = os.path.join(a.out, doc["drawing_id"] + ".json")
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        json.dump(doc, open(fn, "w"), ensure_ascii=False)
        n += 1
    print("wrote", n, "files to", a.out)


if __name__ == "__main__":
    main()
