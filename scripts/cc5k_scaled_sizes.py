"""Read only the PNG header (width, height) of every CubiCasa5k F1_scaled.png inside the remote Zenodo zip
(HTTP range requests, ~64 KB per member). SVG coordinates are F1_scaled pixels; our dataset PNG is F1_original,
so svg->png scale = W_original / W_scaled.  usage: python -I scripts/cc5k_scaled_sizes.py OUT.json"""
import io, json, struct, sys, zipfile, os, threading
from concurrent.futures import ThreadPoolExecutor
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "remote_zip.py")).read().replace("\nmain()", "\n")
ns = {}; exec(src, ns)
URL = "https://zenodo.org/api/records/2613548/files/cubicasa5k.zip/content"
z0 = zipfile.ZipFile(io.BufferedReader(ns["HttpFile"](URL), buffer_size=8 << 20))
prev = json.load(open(sys.argv[1])) if os.path.exists(sys.argv[1]) else {}
members = [i for i in z0.infolist() if i.filename.endswith("_scaled.png") and not prev.get(i.filename)]
print(len(members), flush=True)
local = threading.local()

def zf():
    if not hasattr(local, "z"):
        local.z = zipfile.ZipFile(io.BufferedReader(ns["HttpFile"](URL), buffer_size=1 << 16))
    return local.z

def head(i):
    for a in range(4):
        try:
            with zf().open(i) as f:
                b = f.read(24)
            w, h = struct.unpack(">II", b[16:24])
            return i.filename, (w, h)
        except Exception as e:
            err = repr(e); import time; time.sleep(2 + 3 * a); local.__dict__.pop("z", None)
    return i.filename, None

out = dict(prev)
with ThreadPoolExecutor(int(os.environ.get('THREADS', 4))) as ex:
    for k, (fn, wh) in enumerate(ex.map(head, members)):
        out[fn] = wh
        if k % 500 == 0: print(k, fn, wh, flush=True)
json.dump(out, open(sys.argv[1], "w"))
print("done", sum(v is None for v in out.values()), "failed")
