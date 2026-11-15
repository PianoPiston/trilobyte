"""Trilobyte takeoff service: room geometry, drawing scale and live material prices.

Run: server/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8101
Geometry comes from the drawing API (stoa-app on 127.0.0.1:8090): exact room polygons for CAD files, room boxes for
IFC sheets, and a wall-mask segmentation of the image for raster plans. Prices come from context.dev web search.
"""
import asyncio, json, math, os, re, statistics, time
from datetime import datetime, timezone
from urllib.parse import quote

import cv2
import httpx
import numpy as np
from fastapi import FastAPI, HTTPException

API = os.environ.get("TRILOBYTE_API", "http://127.0.0.1:8090")
CACHE = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(os.path.join(CACHE, "takeoff"), exist_ok=True)
DOOR_M = 0.85  # typical clear width of an interior door, used only when nothing better gives the scale

app = FastAPI(title="Trilobyte takeoff")
http = httpx.AsyncClient(timeout=120)


# ---------- geometry ----------

def poly_area(p):
    return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2


def poly_perimeter(p):
    return sum(math.dist(p[i], p[i - 1]) for i in range(len(p)))


def box_poly(b):
    x0, y0, x1, y1 = b
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def shape_box(l):
    if l.get("bbox"):
        return l["bbox"]
    xs, ys = [p[0] for p in l["polygon"]], [p[1] for p in l["polygon"]]
    return [min(xs), min(ys), max(xs), max(ys)]


def opening(l):
    b = shape_box(l)
    return {"id": l["id"], "bbox": [round(v, 1) for v in b], "width_px": round(max(b[2] - b[0], b[3] - b[1]), 1)}


FI_ROOMS = {"mh": "Bedroom", "oh": "Living room", "k": "Kitchen", "kt": "Kitchenette", "kk": "Kitchenette", "kh": "Bathroom",
            "wc": "WC", "et": "Hall", "vh": "Walk-in closet", "s": "Sauna", "ph": "Washroom", "khh": "Utility room",
            "parv": "Balcony", "parveke": "Balcony", "var": "Storage", "tk": "Fireplace room", "rt": "Dining area",
            "at": "Garage", "tkh": "Technical room", "th": "Workroom", "aula": "Lobby", "terassi": "Terrace", "kuisti": "Porch"}
AREA_RE = re.compile(r"^(\d{1,3})[.,](\d{1,2})(?:m2|m²)?$", re.I)


def segment(img, doors, windows):
    """Rooms of a raster plan: thick dark strokes are walls, door and window boxes seal the gaps, and every free
    region that the outside cannot reach is a room. Returns (room contours, wall rectangles), both in image px."""
    H, W = img.shape[:2]
    s = min(1.0, 1400 / max(H, W))
    g = cv2.cvtColor(cv2.resize(img, (round(W * s), round(H * s)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    otsu, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = (g < min(140, otsu)).astype(np.uint8)
    dt = cv2.distanceTransform(dark, cv2.DIST_L2, 3)
    t = 2 * float(np.percentile(dt[dark > 0], 97)) if dark.any() else 0  # thickness of the thick strokes
    walls = dark
    if t >= 5:
        k = max(1, round(t * 0.15))  # keeps interior walls (thinner than outer walls), drops text and furniture lines
        opened = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
        if opened.sum() > 0.004 * h * w:
            walls = opened
    barrier = walls.copy()
    for o in doors + windows:
        x0, y0, x1, y1 = (int(round(v * s)) for v in o["bbox"])
        cv2.rectangle(barrier, (x0 - 1, y0 - 1), (x1 + 1, y1 + 1), 1, -1)
    door = statistics.median(o["width_px"] for o in doors) * s if doors else 0.03 * w
    rooms = []
    for close in (max(3, t), door * 0.5, door * 0.9, door * 1.4):
        k = max(1, int(close / 2))
        sealed = cv2.morphologyEx(barrier, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (2 * k + 1, 2 * k + 1)))
        free = np.pad(1 - sealed, 1, constant_values=1).astype(np.uint8)
        cv2.floodFill(free, None, (0, 0), 0)
        inside = free[1:-1, 1:-1]
        if inside.sum() > 0.06 * h * w:
            break
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inside, connectivity=4)
    min_area = max((0.8 * door) ** 2, 0.0008 * h * w)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        mask = (labels == i).astype(np.uint8)
        cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        approx = cv2.approxPolyDP(c, 0.006 * cv2.arcLength(c, True), True).reshape(-1, 2)
        if len(approx) < 3:
            continue
        rooms.append({"polygon": [[round(x / s, 1), round(y / s, 1)] for x, y in approx.tolist()],
                      "area_px": float(stats[i, cv2.CC_STAT_AREA]) / s / s})
    # wall rectangles for the 3D view: row runs of a coarse mask, merged down while the run repeats
    cs3 = min(1.0, 260 / max(h, w))
    coarse = cv2.resize(walls, (max(1, round(w * cs3)), max(1, round(h * cs3))), interpolation=cv2.INTER_AREA)
    rects, open_runs = [], {}
    for y in range(coarse.shape[0] + 1):
        row = coarse[y] if y < coarse.shape[0] else np.zeros(coarse.shape[1], np.uint8)
        edges = np.flatnonzero(np.diff(np.concatenate(([0], row, [0]))))
        runs = set(zip(edges[::2].tolist(), edges[1::2].tolist()))
        for r in list(open_runs):
            if r not in runs:
                rects.append([r[0], open_runs.pop(r), r[1], y])
        for r in runs:
            open_runs.setdefault(r, y)
    f = 1 / (s * cs3)
    return rooms, [[round(v * f, 1) for v in r] for r in rects[:6000]]


def name_rooms(rooms, layer, words):
    """Label segmented rooms from detector room boxes and printed words; return printed-area scale candidates."""
    scales = []
    for i, r in enumerate(rooms):
        r["id"] = f"S{i + 1}"
        cnt = np.array(r["polygon"], np.float32)
        inside = lambda x, y: cv2.pointPolygonTest(cnt, (float(x), float(y)), False) >= 0
        for l in layer:
            if l["kind"] == "room" and l.get("bbox"):
                b = l["bbox"]
                if inside((b[0] + b[2]) / 2, (b[1] + b[3]) / 2):
                    r["name"] = l["label"].replace("room_", "").replace("_", " ").capitalize()
        labels = []
        for wd in words:
            b, text = wd["bbox"], wd["text"].strip()
            if not inside((b[0] + b[2]) / 2, (b[1] + b[3]) / 2):
                continue
            m = AREA_RE.match(text.replace(" ", ""))
            if m and 1 <= float(f"{m[1]}.{m[2]}") <= 250:
                r["printed_area_m2"] = float(f"{m[1]}.{m[2]}")
            elif text.lower().strip(".:") in FI_ROOMS:
                labels.append(FI_ROOMS[text.lower().strip(".:")])
        if labels:
            r["name"] = labels[0]
        if r.get("printed_area_m2"):
            scales.append(math.sqrt(r["printed_area_m2"] / r["area_px"]))
    return scales


async def get(path, **kw):
    r = await http.get(API + path, **kw)
    return r.json() if r.status_code == 200 else None


async def build_takeoff(did):
    d = await get(f"/api/drawings/{quote(did)}")
    if d is None:
        raise HTTPException(404, f"unknown drawing {did}")
    layer = d.get("std_layer") or []
    std = (await get(f"/api/drawings/{quote(did)}/standardized")) or {}
    by_id = {r["id"]: r for r in std.get("rooms", [])}
    doors = [opening(l) for l in layer if l["kind"] == "door"]
    windows = [opening(l) for l in layer if l["kind"] == "window"]
    out = {"id": did, "image_size": d["image_size"], "doors": doors, "windows": windows, "walls": []}
    exact_rooms = [l for l in layer if l["kind"] == "room" and (l.get("polygon") or by_id.get(l["id"], {}).get("area_m2"))]

    if exact_rooms:
        out["source"] = "cad" if any(l.get("polygon") for l in exact_rooms) else "bim"
        rooms, scales = [], []
        for l in exact_rooms:
            src = by_id.get(l["id"], {})
            poly = l.get("polygon") or box_poly(l["bbox"])
            if poly[0] == poly[-1]:
                poly = poly[:-1]
            name = " ".join(str(x) for x in (src.get("name"), src.get("number")) if x) or l["label"].split(" · ")[0]
            r = {"id": l["id"], "name": name, "polygon": poly, "area_px": poly_area(poly), "area_m2": src.get("area_m2"),
                 "outdoor": bool(src.get("is_outdoor")), "shaft": bool(src.get("is_shaft"))}
            if r["area_m2"] and r["area_px"] > 0:
                scales.append(math.sqrt(r["area_m2"] / r["area_px"]))
            rooms.append(r)
        out["rooms"] = rooms
        reg = (d.get("standardized") or {}).get("registration") or {}
        if reg.get("px_per_m"):
            out["scale"] = {"m_per_px": 1 / reg["px_per_m"], "method": "CAD coordinates registered to the sheet", "confidence": 1.0}
        elif scales:
            out["scale"] = {"m_per_px": statistics.median(scales), "confidence": 0.8,
                            "method": f"room areas from the {'CAD file' if out['source'] == 'cad' else 'BIM model'} ({len(scales)} rooms)"}
    else:
        out["source"] = "segmented"
        img_bytes = (await http.get(f"{API}/api/drawings/{quote(did)}/image")).content
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(422, "the drawing image could not be read")
        if [img.shape[1], img.shape[0]] != list(d["image_size"]):
            img = cv2.resize(img, tuple(d["image_size"]))
        rooms, walls = await asyncio.to_thread(segment, img, doors, windows)
        try:
            words = ((await get(f"/api/drawings/{quote(did)}/words", params={"compute": 1}, timeout=90)) or {}).get("words", [])
        except httpx.HTTPError:
            words = []
        scales = name_rooms(rooms, layer, words)
        out["rooms"], out["walls"] = rooms, walls
        if len(scales) >= 2:
            out["scale"] = {"m_per_px": statistics.median(scales), "confidence": 0.8,
                            "method": f"room areas printed on the drawing ({len(scales)} rooms)"}
        elif scales:
            out["scale"] = {"m_per_px": scales[0], "confidence": 0.5, "method": "one room area printed on the drawing"}
        elif doors:
            out["scale"] = {"m_per_px": DOOR_M / statistics.median(o["width_px"] for o in doors), "confidence": 0.35,
                            "method": f"door widths, assuming {DOOR_M} m doors ({len(doors)} detected)"}
    out.setdefault("scale", {"m_per_px": None, "method": "unknown", "confidence": 0})
    for r in out["rooms"]:
        r["perimeter_px"] = round(poly_perimeter(r["polygon"]), 1)
        r["area_px"] = round(r["area_px"], 1)
    return out


@app.get("/x/takeoff/{did}")
async def takeoff(did: str, refresh: bool = False):
    path = os.path.join(CACHE, "takeoff", re.sub(r"[^\w.~-]", "_", did) + ".json")
    if not refresh and os.path.exists(path):
        return json.load(open(path))
    out = await build_takeoff(did)
    json.dump(out, open(path, "w"))
    return out


# ---------- live material prices (context.dev web search) ----------

UNIT_RE = {"m3": r"m\s?[3³]|kuutio(?:metri)?", "m2": r"m\s?[2²]|neliö(?:metri)?", "l": r"l(?:itra)?(?![a-zäö])",
           "kg": r"kg", "m": r"(?:jm|metri|m)(?![a-zäö0-9²³])"}
MATERIALS = [
    {"key": "concrete", "label": "Ready-mix concrete C25/30", "unit": "m3", "range": (110, 330), "reference": 185.0,
     "queries": ["valmisbetoni C25/30 hinta €/m3 2026", "valmisbetonin kuutiohinta lattiabetoni C25/30 €/m3"]},
    {"key": "screed", "label": "Floor levelling compound", "unit": "kg", "range": (0.3, 4), "reference": 0.9,
     "queries": ["lattiatasoite 20 kg säkki hinta €/kg", "weber vetonit lattiatasoite hinta €/kg rautakauppa"]},
    {"key": "flooring", "label": "Laminate flooring", "unit": "m2", "range": (6, 70), "reference": 19.9,
     "queries": ["laminaatti hinta €/m2 rautakauppa", "laminaatti KL32 8 mm €/m² tarjous"]},
    {"key": "plasterboard", "label": "Plasterboard 13 mm", "unit": "m2", "range": (1.5, 12), "reference": 3.2,
     "queries": ["kipsilevy 13 mm 1200x2600 hinta €/m2", "kipsilevy EK 13 hinta €/m² rautakauppa"]},
    {"key": "paint", "label": "Interior wall paint", "unit": "l", "range": (3, 40), "reference": 11.0,
     "queries": ["sisämaali seinämaali 9 l hinta €/l", "seinämaali valkoinen himmeä hinta €/l rautakauppa"]},
    {"key": "skirting", "label": "Skirting board", "unit": "m", "range": (0.8, 15), "reference": 3.5,
     "queries": ["jalkalista MDF valkoinen hinta €/m", "jalkalista 12x58 hinta €/m rautakauppa"]},
]
PRICES_FILE = os.path.join(CACHE, "prices.json")
PRICE_TTL = 12 * 3600
_refresh_lock = asyncio.Lock()


def _key():
    k = os.environ.get("CONTEXTDEV_API_KEY")
    if not k:
        for line in open(os.path.expanduser("~/.config/contextdev/api.env")):
            if line.startswith("CONTEXTDEV_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("'\"")
    return k


def clean(text):
    """Markdown and escape characters stripped from a search highlight."""
    text = re.sub(r"\\([-*_\[\]()#.])", r"\1", text)
    text = re.sub(r"\*\*|__|#{1,6} |\[|\]\([^)]*\)|\]|&#x20;|…", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -|>")


def extract_prices(text, unit, lo, hi):
    """Unit prices like '184,36 €/m³' found in text, with the surrounding quote."""
    pat = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:€|eur(?:oa)?)\s*(?:/|per)\s*(?:" + UNIT_RE[unit] + ")", re.I)
    out = []
    for m in pat.finditer(text):
        v = float(m[1].replace(",", "."))
        if lo <= v <= hi:
            quote_ = clean(text[max(0, m.start() - 70):m.end() + 50])
            out.append((v, quote_))
    return out


async def fetch_price(mat):
    found, credits = [], 0
    for q in mat["queries"]:
        r = await http.post("https://api.context.dev/v1/web/search", headers={"Authorization": f"Bearer {_key()}"},
                            json={"query": q, "numResults": 8, "highlightsOptions": {"enabled": True, "maxCharacters": 1500},
                                  "timeoutOpts": {"milliseconds": 30000, "behavior": "return-partial"}})
        await asyncio.sleep(6.5)  # the organisation limit is 10 requests per minute
        if r.status_code != 200:
            continue
        data = r.json()
        credits += (data.get("key_metadata") or {}).get("credits_consumed", 0)
        for res in data.get("results", []):
            hl = res.get("highlights") or {}
            text = " … ".join(hl.get("highlights") or []) if isinstance(hl, dict) else ""
            for v, quote_ in extract_prices(text, mat["unit"], *mat["range"]):
                found.append({"price": v, "quote": quote_, "url": res.get("url"), "title": res.get("title")})
        if len(found) >= 3:
            break
    base = {k: mat[k] for k in ("key", "label", "unit")} | {"credits": credits}
    if not found:
        return base | {"live": False, "price": mat["reference"], "note": "No live price found; this is a reference estimate."}
    finnish = [f for f in found if re.match(r"https?://[^/]+\.fi(/|$)", f["url"] or "")]
    if len(finnish) >= 2:  # Finnish suppliers price for this market; foreign pages only fill a gap
        found = finnish
    med = statistics.median(f["price"] for f in found)
    best = min(found, key=lambda f: abs(f["price"] - med))
    seen, sources = set(), []
    for f in sorted(found, key=lambda f: abs(f["price"] - med)):
        if f["url"] not in seen:
            seen.add(f["url"])
            sources.append(f)
    return base | {"live": True, "price": best["price"], "low": min(f["price"] for f in found), "high": max(f["price"] for f in found),
                   "n": len(found), "sources": sources[:4]}


async def refresh_prices():
    if _refresh_lock.locked():
        return
    async with _refresh_lock:
        items = [await fetch_price(m) for m in MATERIALS]
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ts": time.time(), "items": items},
                  open(PRICES_FILE, "w"), ensure_ascii=False, indent=1)


@app.get("/x/prices")
async def prices(refresh: bool = False):
    """Unit prices per material. A stale or missing cache starts a background refresh (about one minute)."""
    cached = json.load(open(PRICES_FILE)) if os.path.exists(PRICES_FILE) else None
    if refresh or not cached or time.time() - cached["ts"] > PRICE_TTL:
        asyncio.create_task(refresh_prices())
    items = cached["items"] if cached else [
        {k: m[k] for k in ("key", "label", "unit")} | {"live": False, "price": m["reference"], "note": "Fetching live prices…"} for m in MATERIALS]
    return {"fetched_at": cached and cached["fetched_at"], "refreshing": _refresh_lock.locked() or refresh or not cached, "items": items}
