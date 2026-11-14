"""Load a drawing as a PIL image capped at max_pixels (keeps aspect ratio). PDFs rendered with PyMuPDF."""
import base64, io, math, os
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def load_image(path: str, max_pixels: int = 2_000_000, min_pixels: int = 0) -> Image.Image:
    if path.lower().endswith(".pdf"):
        import fitz  # pymupdf
        doc = fitz.open(path)
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        zoom = math.sqrt(max_pixels / (w * h))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        img = Image.open(path)
        img = img.convert("RGB") if img.mode != "RGB" else img
    w, h = img.size
    if w * h > max_pixels:
        s = math.sqrt(max_pixels / (w * h))
        img = img.resize((max(28, int(w * s)), max(28, int(h * s))), Image.LANCZOS)
    elif min_pixels and w * h < min_pixels:  # upscale small scans so small symbols span more vision patches
        s = math.sqrt(min_pixels / (w * h))
        img = img.resize((int(w * s), int(h * s)), Image.BICUBIC)
    return img


def to_data_url(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, optimize=False)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()
