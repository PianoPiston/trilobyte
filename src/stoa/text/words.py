"""Printed words of a drawing, with positions in the pixel frame of the image the UI/detector/VLM see.

  vector PDF  -> PyMuPDF words (exact text and boxes, no OCR), scaled from PDF points to image px
  raster/scan -> RapidOCR (PP-OCRv4 det+rec via onnxruntime, Apache-2.0) on CPU; small images are upscaled,
                 large ones tiled with overlap so drawing-size text survives the detector's resize

words file = {"version", "image_size", "method": "pdf"|"ocr", "seconds", "words": [{text, bbox [x0,y0,x1,y1], conf}]}
OCR text is a model output (never ground truth). Nothing here reads dataset labels.
"""
import json, os, re, threading, time

VERSION = "words@1.0"
_ocr = {"engine": None}
_lock = threading.Lock()
_CJK = re.compile(r"[⺀-鿿가-힯＀-￯]")


def _engine():
    with _lock:
        if _ocr["engine"] is None:
            from rapidocr_onnxruntime import RapidOCR
            n = max(1, min(4, (os.cpu_count() or 2) - 1))
            _ocr["engine"] = RapidOCR(intra_op_num_threads=n, inter_op_num_threads=1, max_side_len=2400, print_verbose=False)
        return _ocr["engine"]


def _clean(t):
    t = _CJK.sub("", t or "").strip()
    return t


def pdf_words(pdf_path, image_size, page=0):
    """vector text of a PDF page -> words in image px (image = that page rendered at any zoom)"""
    import fitz
    doc = fitz.open(pdf_path)
    if doc.page_count <= page:
        return []
    p = doc[page]
    W, H = image_size
    sx, sy = W / p.rect.width, H / p.rect.height
    out = []
    for x0, y0, x1, y1, t, b, l, w in p.get_text("words"):
        t = _clean(t)
        if t:
            out.append({"text": t, "bbox": [round(x0 * sx, 1), round(y0 * sy, 1), round(x1 * sx, 1), round(y1 * sy, 1)],
                        "conf": 1.0, "line": f"{b}.{l}"})
    return out


def _ocr_array(arr):
    res, _ = _engine()(arr)
    out = []
    for box, txt, conf in res or []:
        t = _clean(txt)
        if not t:
            continue
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append({"text": t, "bbox": [min(xs), min(ys), max(xs), max(ys)], "conf": float(conf)})
    return out


def _iou_small(a, b):
    iw = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    am = max(1e-6, min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])))
    return iw * ih / am


def _ocr_full(im, tile=1600, overlap=200):
    import numpy as np
    w, h = im.size
    arr = np.asarray(im)[:, :, ::-1]  # BGR for the cv2-based engine
    if max(w, h) <= 2400:
        return _ocr_array(np.ascontiguousarray(arr))
    words = []
    step = tile - overlap
    for y in range(0, max(1, h - overlap), step):
        for x in range(0, max(1, w - overlap), step):
            sub = arr[y:y + tile, x:x + tile]
            if sub.shape[0] < 20 or sub.shape[1] < 20 or sub.min() > 245:  # blank tile
                continue
            for wd in _ocr_array(np.ascontiguousarray(sub)):
                b = wd["bbox"]
                wd["bbox"] = [b[0] + x, b[1] + y, b[2] + x, b[3] + y]
                words.append(wd)
    # de-duplicate words seen in two overlapping tiles (keep the longer / more confident one)
    words.sort(key=lambda d: (-len(d["text"]), -d["conf"]))
    kept = []
    for wd in words:
        if not any(_iou_small(wd["bbox"], k["bbox"]) > 0.6 for k in kept):
            kept.append(wd)
    return kept


def _unrotate(b, rot, w, h):
    """box in the rotated image -> box in the unrotated image (w, h = unrotated size; PIL rotate is counter-clockwise)"""
    x0, y0, x1, y1 = b
    if rot == 180:
        return [w - x1, h - y1, w - x0, h - y0]
    if rot == 90:   # (x, y) -> (y, w - x)
        return [w - y1, x0, w - y0, x1]
    if rot == 270:  # (x, y) -> (h - y, x)
        return [y0, h - x1, y1, h - x0]
    return b


def ocr_words(image_path):
    """OCR in the best of the four orientations (scanned/rotated plans are common; cubicasa has upside-down sheets)"""
    from PIL import Image
    from .measure import label_score
    Image.MAX_IMAGE_PIXELS = 200_000_000
    im = Image.open(image_path).convert("RGB")
    W, H = im.size
    s = 1.0
    if max(W, H) < 1400:  # small raster plans: text is a few px high -> upscale
        s = min(3.0, 1800 / max(W, H))
        im = im.resize((int(W * s), int(H * s)), Image.LANCZOS)
    w, h = im.size
    best = None
    rots = (0, 180, 90, 270) if max(w, h) <= 2400 else (0,)
    for rot in rots:
        ws = _ocr_full(im if rot == 0 else im.rotate(rot, expand=True))
        for wd in ws:
            wd["bbox"] = _unrotate(wd["bbox"], rot, w, h)
        sc = label_score(ws)
        if best is None or sc > best[0]:
            best = (sc, rot, ws)
        if best[0] >= 3 and rot in (0, 180):
            break
    _, rot, words = best
    for wd in words:
        wd["bbox"] = [round(v / s, 1) for v in wd["bbox"]]
        wd["conf"] = round(wd["conf"], 3)
        if rot:
            wd["rot"] = rot
    words.sort(key=lambda d: (d["bbox"][1], d["bbox"][0]))
    return words, [W, H]


def extract(image_path, pdf_path=None, pdf_page=0):
    """-> words file dict. Vector PDF text wins when the PDF has a text layer; otherwise OCR on the raster."""
    from PIL import Image
    t0 = time.time()
    with Image.open(image_path) as im:
        size = list(im.size)
    if pdf_path and os.path.exists(pdf_path):
        try:
            ws = pdf_words(pdf_path, size, pdf_page)
            if len(ws) >= 3:
                return {"version": VERSION, "image_size": size, "method": "pdf", "seconds": round(time.time() - t0, 2), "words": ws}
        except Exception:
            pass
    ws, size = ocr_words(image_path)
    return {"version": VERSION, "image_size": size, "method": "ocr", "engine": "rapidocr-onnxruntime PP-OCRv4",
            "seconds": round(time.time() - t0, 2), "words": ws}


def load_or_extract(out_path, image_path, pdf_path=None, compute=True):
    if os.path.exists(out_path):
        try:
            d = json.load(open(out_path, encoding="utf-8"))
            if d.get("version") == VERSION:
                return d
        except Exception:
            pass
    if not compute:
        return None
    d = extract(image_path, pdf_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, out_path)
    return d
