"""Build the words layer (PDF vector text / OCR) for drawings, in parallel, cached next to the standardized files.

  python scripts/build_words.py --catalog                         # featured demo drawings
  python scripts/build_words.py --source cubicasa5k --split val --n 150
Reads only drawing paths and the split assignment (never answers).
"""
import argparse, hashlib, os, sys, time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def sample_paths(source, split, n):
    from app.api import config  # noqa: F401  (sets STOA_DATA)
    from stoa.data import load_questions
    paths = sorted({q.path for q in load_questions() if q.source == source and q.split == split})
    paths.sort(key=lambda p: hashlib.sha256(("words-sample:" + p).encode()).hexdigest())
    return paths[:n]


def work(did):
    os.environ.setdefault("OMP_NUM_THREADS", "3")
    from app.api import catalog as CAT, engine as E
    d = CAT.describe(did)
    if d is None:
        return did, None, 0
    t = time.time()
    w = E.words_for(d, compute=True)
    return did, (len(w["words"]) if w else None), round(time.time() - t, 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", action="store_true")
    ap.add_argument("--source"); ap.add_argument("--split"); ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.catalog:
        from app.api import catalog as CAT
        ids = [d["id"] for d in CAT.featured() if d["track"] == "modern"]
    else:
        ids = [f"{a.source}~{os.path.splitext(os.path.basename(p))[0]}" for p in sample_paths(a.source, a.split, a.n)]
    print(len(ids), "drawings", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        for i, (did, n, s) in enumerate(ex.map(work, ids)):
            print(i, did, n, s, flush=True)
    print("done", round(time.time() - t0), "s", flush=True)
