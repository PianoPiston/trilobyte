"""Run the trained detector over drawings and cache raw detections (score >= 0.05) as JSONL.
usage: python -I scripts/run_detector.py --ckpt /w/ckpt/det1/last.pt --data /w/data/junction-dataset \
          --paths paths.txt --out dets.jsonl
paths.txt: one dataset-relative path per line (cubicasa PNGs of any split - inference uses only the image)."""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import torch
from PIL import Image
from stoa.detector import build_model, detect

Image.MAX_IMAGE_PIXELS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True); ap.add_argument("--data", required=True)
    ap.add_argument("--paths", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--tta", action="store_true", help="also run on the horizontally flipped image")
    a = ap.parse_args()
    m = build_model()
    m.load_state_dict(torch.load(a.ckpt, map_location="cpu"))
    m = m.cuda().eval()
    paths = [l.strip() for l in open(a.paths) if l.strip()]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["path"] for l in open(a.out)}
    t0 = time.time()
    with open(a.out, "a") as f:
        for i, p in enumerate(paths):
            if p in done:
                continue
            img = Image.open(os.path.join(a.data, p)).convert("RGB")
            t1 = time.time()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                d = detect(m, img)
                tta = []
                if a.tta:  # counts only: class + score on flipped / transposed views
                    for op in (Image.FLIP_LEFT_RIGHT, Image.FLIP_TOP_BOTTOM, Image.TRANSPOSE):
                        tta.append([[x["cls"], x["score"]] for x in detect(m, img.transpose(op))])
            f.write(json.dumps({"path": p, "size": list(img.size), "dets": d, "tta": tta, "sec": round(time.time() - t1, 3)}) + "\n")
            if i % 100 == 0:
                print(i, len(paths), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
