# Trilobyte: make blueprints talk

Junction 2026, Stoa challenge "Make Blueprints Talk" (+ Verda Compute). Ask natural-language questions (EN/FI) about
construction drawings and get an answer **with its evidence**: the room polygons, IFC element IDs or detected symbols
it came from, a confidence score, and an honest "needs check" when the system is not sure.

**Modern drawings are standardized into data. Historic drawings get their context back. Every answer points to its evidence.**

## How it works
```
drawing + question
  ├─ CAD (DXF)  → standardized drawing file → exact rules            (rooms, apartments, doors, windows, fixtures, areas)
  ├─ BIM (IFC)  → standardized drawing file → exact queries          (storeys, spaces, Qto areas/volumes, element types)
  ├─ raster plan → symbol detector (Faster R-CNN, trained on CubiCasa5K train split) + fine-tuned VLM
  │               → calibrated policy: answer when the signals agree, otherwise "needs check" + evidence boxes
  ├─ historic drawing → context file (archive record + web context) → cited answer
  └─ anything else → fine-tuned Qwen3.5-4B (LoRA), answered only above a calibrated confidence
```
The standardized drawing format is `schema/drawing.schema.json`. Model-derived files are marked `ground_truth_eligible=false`.

## Results (held-out TEST split, split by drawing, official tolerance: counts exact, areas ±2%)
| system | accuracy | €/1k questions |
|---|---|---|
| zero-shot Qwen3.5-4B | 47.1% | 0.038 |
| fine-tuned Qwen3.5-4B (LoRA, trained on Verda) | 68.5% | 0.013 |
| hybrid router (exact CAD/IFC + VLM) | 81.1% | 0.021 |
| **router v2 + detector: auto-answers 58% of questions at 99.2% precision**, the rest "needs check" | 99.2% on answered | 0.016 |

Swiss CAD drawings: 99.8% precision on 98% answered; IFC models: 100%. Historic drawings: 57.6% → 93.7% with context files.
All runs: `results/leaderboard.md`.

## Run
```sh
python -m venv .venv && . .venv/bin/activate
pip install fastapi uvicorn pillow pymupdf ezdxf ifcopenshell python-multipart torch torchvision
(cd app/web && npm ci && npm run build)
uvicorn app.api.main:app --port 8090          # web UI + API on http://127.0.0.1:8090
python -m app.mcp.server                       # MCP server (stdio); --http for streamable HTTP
```
The dataset (not included) goes in `DATA/junction-dataset/`. Set `STOA_VLM_BASE_URL` to an OpenAI-compatible endpoint
(vLLM serving Qwen3.5-4B + the LoRA adapter) for live model answers; without it the exact routes, detector and answer
cache still work. Evaluation: `python eval.py run --help`.

## Layout
`src/stoa/` models, routes, converters, scoring · `app/` API, web UI, MCP server · `schema/` standardized drawing format ·
`scripts/` data prep, training, calibration · `results/` leaderboard · `DOCS/` design notes.

MIT licence (code). Datasets and annotations keep their own licences.
