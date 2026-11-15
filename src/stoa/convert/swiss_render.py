"""Room categories of swiss_dwellings floors, read from the rendered PNG.

Printed room names are synthetic (see the sheet footer) and the DXF carries no room category, but the renderer fills
rooms by their dataset category: outdoor spaces (balconies, loggias, terraces) are flat grey 228, all other rooms are
white (with fixtures/stair hatching) or light grey 244. The DXF walls are registered to the PNG (the sheets are A3 at
150 dpi, 1:100 or 1:200, so the scale is one of two known values; the offset comes from cross-correlating the
rasterised WALL polygons with the dark pixels), then each room's eroded interior is sampled.
Calibrated on TRAIN floors: outdoor fill > 0.3 separates excluded from included unnamed rooms 76/76 vs 320/320.
"""
import numpy as np
from PIL import Image, ImageDraw

PX_PER_M = (2480 / 420 * 10, 2480 / 420 * 5)  # A3 long side = 2480 px; 1:100, 1:200
OUTDOOR_GREY = 228


def register(img, walls):
    """img: uint8 greyscale page, walls: list of world polygons -> (score, s, ox, oy) with px = ox + s*x, py = oy - s*y"""
    H, W = img.shape
    xs = [x for w in walls for x, _ in w]
    ys = [y for w in walls for _, y in w]
    x0, y1 = min(xs), max(ys)
    dark = ((img < 200) & (np.abs(img.astype(np.int16) - OUTDOOR_GREY) > 3)).astype(np.float32)
    F = np.fft.rfft2(dark)
    best = None
    for s in PX_PER_M:
        w, h = int((max(xs) - x0) * s) + 3, int((y1 - min(ys)) * s) + 3
        if w >= W or h >= H:
            continue
        m = Image.new("L", (w, h))
        dr = ImageDraw.Draw(m)
        for wl in walls:
            dr.polygon([((x - x0) * s + 1, (y1 - y) * s + 1) for x, y in wl], fill=1)
        t = np.asarray(m, np.float32)
        t = t - t.mean()
        c = np.fft.irfft2(F * np.conj(np.fft.rfft2(t, s=dark.shape)), s=dark.shape)[: H - h + 1, : W - w + 1]
        iy, ix = np.unravel_index(np.argmax(c), c.shape)
        score = float(c[iy, ix] / np.abs(t).sum())
        if best is None or score > best[0]:
            best = (score, s, ix + 1 - x0 * s, iy + 1 + y1 * s)
    return best


def room_fills(png, walls, room_polys):
    """-> (registration score, [outdoor-fill fraction per room polygon])"""
    img = np.asarray(Image.open(png).convert("L"))
    score, s, ox, oy = register(img, walls)
    out = []
    for poly in room_polys:
        pts = [(ox + s * x, oy - s * y) for x, y in poly]
        bx0, by0 = max(int(min(p[0] for p in pts)) - 4, 0), max(int(min(p[1] for p in pts)) - 4, 0)
        bx1, by1 = int(max(p[0] for p in pts)) + 5, int(max(p[1] for p in pts)) + 5
        m = Image.new("L", (bx1 - bx0, by1 - by0))
        ImageDraw.Draw(m).polygon([(x - bx0, y - by0) for x, y in pts], fill=1)
        mk = np.asarray(m).astype(bool)
        er = mk.copy()
        for d in ((3, 0), (-3, 0), (0, 3), (0, -3)):  # 3 px erosion keeps the outline out
            er &= np.roll(mk, d, (0, 1))
        v = img[by0:by1, bx0:bx1][: mk.shape[0], : mk.shape[1]]
        v = v[er if er.sum() > 20 else mk].astype(np.int16)
        out.append(float((np.abs(v - OUTDOOR_GREY) <= 2).mean()) if v.size else 0.0)
    return score, out
