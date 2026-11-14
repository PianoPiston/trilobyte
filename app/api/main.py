"""Stoa product API. Run: ~/venvs/stoa-app/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8090"""
import asyncio, os, time
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config as C
from . import catalog as CAT
from . import engine as E
from . import search as S
from . import benchmark as B
from .vlm_client import VLM
from . import uploads as U

U.install()  # upload~ ids resolve through the catalog like any other drawing

app = FastAPI(title="Stoa · Make Blueprints Talk", version="1.0",
              description="Ask questions about construction drawings; every answer cites its evidence.")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def _get(did):
    d = CAT.describe(did)
    if d is None:
        raise HTTPException(404, f"unknown drawing {did}")
    return d


class AskIn(BaseModel):
    drawing_id: str
    question: str = Field(min_length=2, max_length=500)
    lang: str | None = None


@app.get("/api/health")
async def health():
    h = await VLM.health()
    return {"ok": True, "vlm": {k: v for k, v in h.items() if k != "models"} | {"models": h.get("models", [])},
            "drawings": len(CAT.featured()), "answer_cache": len(E.CACHE.d), "prefer_cache": C.PREFER_CACHE,
            "conf_threshold": C.CONF_AUTO}


def _card(it):
    return {**it, "thumb_url": f"/api/drawings/{it['id']}/thumb", "image_url": f"/api/drawings/{it['id']}/image"}


@app.get("/api/drawings")
async def drawings(source: str | None = None, track: str | None = None, format: str | None = None,
                   has_questions: bool | None = None, unseen_only: bool = False):
    out = []
    for it in CAT.featured():
        if source and it["source"] != source:
            continue
        if track and it["track"] != track:
            continue
        if format and format.upper() not in it["formats"]:
            continue
        if has_questions is not None and bool(it.get("n_questions")) != has_questions:
            continue
        if unseen_only and it.get("seen_in_training"):
            continue
        out.append(_card(it))
    sources = {}
    for it in CAT.featured():
        sources.setdefault(it["source"], {"source": it["source"], "label": it["source_label"], "track": it["track"], "n": 0})["n"] += 1
    return {"drawings": out, "sources": list(sources.values())}


@app.get("/api/drawings/{did}")
async def drawing(did: str, std: bool = True):
    d = await asyncio.to_thread(CAT.describe_full, did)
    if d is None:
        raise HTTPException(404, f"unknown drawing {did}")
    d = _card(d)
    d["context"] = CAT.load_context(d["source"], d["stem"]) if d["track"] == "historic" else None
    if std:
        layer, summary = await asyncio.to_thread(E.std_layer, d)
        d["standardized"] = summary
        d["std_layer"] = layer
        d["standardized_url"] = f"/api/drawings/{did}/standardized" if summary else None
    return d


@app.get("/api/drawings/{did}/standardized")
async def standardized(did: str):
    d = _get(did)
    doc = await asyncio.to_thread(E.std_doc, d)
    if not doc:
        raise HTTPException(404, "no standardized file for this drawing")
    return JSONResponse(doc)


@app.get("/api/drawings/{did}/context")
async def context(did: str):
    d = _get(did)
    ctx = CAT.load_context(d["source"], d["stem"])
    if not ctx:
        raise HTTPException(404, "no context file for this drawing")
    return ctx


@app.get("/api/drawings/{did}/image")
async def image(did: str):
    d = _get(did)
    p = await asyncio.to_thread(CAT.image_file, d)
    if not p:
        raise HTTPException(404, "no image")
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/drawings/{did}/thumb")
async def thumb(did: str):
    d = _get(did)
    p = await asyncio.to_thread(CAT.thumb_file, d)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.post("/api/ask")
async def ask(body: AskIn):
    r = await E.ask(body.drawing_id, body.question, body.lang)
    if "error" in r:
        raise HTTPException(404, r["error"])
    return r


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), title: str | None = Form(None)):
    """Upload a drawing (PNG/JPG/WEBP/TIFF or PDF, page 1). Runs the symbol detector once, then ask questions with
    POST /api/ask using the returned id."""
    data = await file.read(U.MAX_BYTES + 1)
    try:
        d = await asyncio.to_thread(U.ingest, file.filename or "", data, title)
    except U.UploadError as e:
        raise HTTPException(400, str(e))
    d = {k: v for k, v in d.items() if k != "files"}  # no server paths in responses
    return _card(d)


@app.get("/api/uploads")
async def uploads(limit: int = 30):
    return {"drawings": [_card(d) for d in U.list_uploads(min(limit, 100))], "detector": U.detector_status()}


@app.get("/api/search")
async def search(q: str = Query("", max_length=300), source: str | None = None, limit: int = 40):
    r = await asyncio.to_thread(S.search, q, min(limit, 200), source)
    for it in r["results"]:
        it["thumb_url"] = f"/api/drawings/{it['id']}/thumb"
    return r


@app.get("/api/benchmark")
async def benchmark():
    return await asyncio.to_thread(B.benchmark)


# ---- static web UI (built by `npm run build` in app/web) ----
DIST = os.path.join(C.ROOT, "app", "web", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        f = os.path.join(DIST, path)
        if path and os.path.isfile(f) and os.path.realpath(f).startswith(os.path.realpath(DIST)):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))
