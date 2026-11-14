"""User uploads: drop in any drawing (PNG/JPG/WEBP/TIFF or PDF), then ask questions about it like any catalog drawing.

An upload gets the id `upload~<hex>` and lives in app/uploads/<hex>/ (git-ignored, untrusted user data):
  original.<ext>   the file as uploaded (never executed; images are re-encoded, PDFs only rasterised by PyMuPDF)
  image.png        the raster the viewer, the detector and the VLM see (PDF -> page 1)
  meta.json        catalog entry
The symbol detector (det2, CPU) runs once on upload and its standardized file is written to
STD_DIR/upload/<hex>.json (producer.kind = "model", never ground truth), so engine.ask() answers counts from it,
then falls back to the live VLM exactly as for catalog drawings.
"""
import datetime, io, json, os, re, threading, time, uuid

os.environ.setdefault("STOA_DET_CLASSES", "v2")  # det2 = symbols + room-type boxes; must be set before importing stoa.detector

from PIL import Image

from . import config as C
from . import catalog as CAT

UPLOAD_DIR = os.environ.get("STOA_UPLOAD_DIR", os.path.join(C.ROOT, "app", "uploads"))
DET_CKPT = os.environ.get("STOA_DET_CKPT", os.path.join(C.ROOT, "artifacts", "det2", "det2_last.pt"))
DET_POLICY = os.environ.get("STOA_DET_POLICY_FILE", os.path.join(C.ROOT, "results", "detpolicy_det2_count.json"))
MAX_BYTES = int(os.environ.get("STOA_UPLOAD_MAX_MB", "40")) * 1024 * 1024
MAX_PIXELS = 40_000_000
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
ALLOWED = IMAGE_EXT | {".pdf"}
Image.MAX_IMAGE_PIXELS = 200_000_000  # decompression-bomb guard (we downscale anything above MAX_PIXELS)

os.makedirs(UPLOAD_DIR, exist_ok=True)
_det = {"model": None, "err": None}
_det_lock = threading.Lock()

EXAMPLES = [
    ("How many windows are shown on this floor plan?", "en"),
    ("How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count.", "en"),
    ("How many toilet bowls (WC seats) are drawn on this floor plan?", "en"),
    ("How many bedrooms (makuuhuone, usually marked MH) are on this floor plan?", "en"),
    ("How many saunas are on this floor plan?", "en"),
    ("How many showers and bathtubs are drawn on this floor plan in total?", "en"),
    ("Kuinka monta ikkunaa pohjapiirustuksessa on?", "fi"),
    ("Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on?", "fi"),
]


def is_upload(did):
    return isinstance(did, str) and did.startswith("upload~")


def _dir(hexid):
    if not re.fullmatch(r"[0-9a-f]{12}", hexid or ""):
        return None
    return os.path.join(UPLOAD_DIR, hexid)


def describe(did):
    if not is_upload(did):
        return None
    p = _dir(did.split("~", 1)[1])
    if not p or not os.path.exists(os.path.join(p, "meta.json")):
        return None
    return json.load(open(os.path.join(p, "meta.json"), encoding="utf-8"))


def list_uploads(limit=50):
    out = []
    for h in sorted(os.listdir(UPLOAD_DIR), key=lambda h: -os.path.getmtime(os.path.join(UPLOAD_DIR, h)))[:limit]:
        d = describe(f"upload~{h}")
        if d:
            out.append(d)
    return out


# ------------------------------------------------------------------------------------------------ detector (CPU)
def _model():
    with _det_lock:
        if _det["model"] is None and _det["err"] is None:
            try:
                import torch
                from stoa.detector import build_model
                torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
                m = build_model()
                m.load_state_dict(torch.load(DET_CKPT, map_location="cpu"))
                _det["model"] = m.eval()
            except Exception as e:
                _det["err"] = f"{type(e).__name__}: {e}"[:300]
        return _det["model"]


def detector_status():
    return {"loaded": _det["model"] is not None, "error": _det["err"], "ckpt": os.path.basename(DET_CKPT)}


def _run_detector(d, img_path):
    m = _model()
    if m is None:
        return {"ok": False, "error": _det["err"]}
    from stoa.detector import detect
    from stoa.convert.raster_model import from_detections, load_policy
    t0 = time.time()
    img = Image.open(img_path).convert("RGB")
    dets = detect(m, img, device="cpu")
    doc = from_detections(d["q_path"], list(img.size), dets, load_policy(DET_POLICY), model_name="det2")
    doc["drawing_id"] = d["q_path"]
    out = os.path.join(C.STD_DIR, "upload", d["stem"] + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(doc, open(out, "w"), ensure_ascii=False)
    counts = {}
    for k in ("doors", "windows", "rooms", "symbols"):
        for it in doc.get(k, []):
            kind = it.get("kind") or k.rstrip("s")
            counts[kind] = counts.get(kind, 0) + 1
    return {"ok": True, "seconds": round(time.time() - t0, 1), "n_detections": len(dets), "counts": counts}


# ------------------------------------------------------------------------------------------------ ingest
class UploadError(ValueError):
    pass


def ingest(filename, data, title=None):
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED:
        raise UploadError(f"Unsupported file type '{ext or '?'}'. Upload a PNG, JPG, WEBP, TIFF or PDF drawing.")
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise UploadError(f"File too large ({len(data) // 1048576} MB); the limit is {MAX_BYTES // 1048576} MB.")
    hexid = uuid.uuid4().hex[:12]
    p = _dir(hexid)
    os.makedirs(p)
    img_path = os.path.join(p, "image.png")
    pages = None
    try:
        if ext == ".pdf":
            if not data.startswith(b"%PDF"):
                raise UploadError("This does not look like a PDF file.")
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            pages = doc.page_count
            if pages < 1:
                raise UploadError("The PDF has no pages.")
            page = doc[0]
            z = (6_000_000 / max(1.0, page.rect.width * page.rect.height)) ** 0.5
            page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).save(img_path)
        else:
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                im = im.convert("RGB")
                w, h = im.size
                if w * h > MAX_PIXELS:
                    s = (MAX_PIXELS / (w * h)) ** 0.5
                    im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
                im.save(img_path)  # re-encoded: the original bytes are kept but never served
    except UploadError:
        raise
    except Exception as e:
        raise UploadError(f"Could not read the drawing: {type(e).__name__}") from e
    finally:
        if not os.path.exists(img_path):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
    with open(os.path.join(p, "original" + ext), "wb") as f:
        f.write(data)
    safe_name = re.sub(r"[^\w.\- ()]+", "_", os.path.basename(filename))[:120]
    w, h = CAT.image_size(img_path)
    d = {
        "id": f"upload~{hexid}", "source": "upload", "source_label": "Your upload", "stem": hexid,
        "title": (title or safe_name or "Uploaded drawing")[:120],
        "subtitle": f"Uploaded {ext[1:].upper()}" + (f" · page 1 of {pages}" if pages and pages > 1 else ""),
        "q_path": f"uploads/{hexid}.png", "files": {"png": img_path},
        "formats": [ext[1:].upper()], "split": None, "seen_in_training": False, "track": "modern",
        "licence": "uploaded by the user", "credit": safe_name, "source_url": None,
        "has_context": False, "has_std": True, "image_ok": True, "original_name": safe_name,
        "uploaded_at": datetime.datetime.now().isoformat(timespec="seconds"), "image_size": [w, h],
    }
    d["detector"] = _run_detector(d, img_path)
    json.dump(d, open(os.path.join(p, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return d


# ------------------------------------------------------------------------------------------------ catalog hooks
def install():
    """route catalog lookups for upload~ ids to this module (engine.ask, viewer, MCP all go through CAT)"""
    orig_describe, orig_full, orig_examples = CAT.describe, CAT.describe_full, CAT.example_questions

    def describe_hook(did):
        return describe(did) if is_upload(did) else orig_describe(did)

    def examples_hook(d, limit=14):
        if d.get("source") == "upload":
            return [{"question": q, "answer": None, "unit": None, "type": "count", "lang": l} for q, l in EXAMPLES][:limit]
        return orig_examples(d, limit)

    def full_hook(did):
        if not is_upload(did):
            return orig_full(did)
        d = describe(did)
        if d is None:
            return None
        d = dict(d)
        d["examples"] = examples_hook(d)
        return d

    CAT.describe, CAT.describe_full, CAT.example_questions = describe_hook, full_hook, examples_hook
