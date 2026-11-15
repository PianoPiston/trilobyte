# Trilobyte UI

Floor-plan editor for Trilobyte: drop in a drawing, see its rooms measured, get concrete and finishing-material quantities with live prices, ask questions with the evidence marked on the sheet, and orbit a 3D model built from the plan. Type and colour follow Stoa's brand (Playfair Display, Inter, JetBrains Mono; moss ink on a cool grey ground).

## Parts

- `src/` – React + Vite + TypeScript single-page app.
  - `pages/DrawingView.tsx` – the editor: plan viewer with Select / Distance / Area / Set scale tools, 3D model toggle, question box, and Summary / Materials / Answer / Archive / Source tabs.
  - `components/Viewer.tsx` – pan/zoom plan with room polygons, evidence, measurements and scale calibration.
  - `components/Scene3D.tsx` – three.js model: the sheet on the ground, tinted room floors, walls raised from the wall mask (raster plans) or room outlines (CAD/BIM).
  - `components/MaterialsPanel.tsx`, `TakeoffAnswer.tsx`, `lib/takeoff.ts`, `lib/intent.ts` – quantity takeoff (concrete slab, levelling compound, laminate, plasterboard, paint, skirting), editable assumptions and prices, and material questions answered from the plan.
- `server/main.py` – takeoff service (FastAPI, port 8101):
  - `GET /x/takeoff/{drawing_id}` – rooms, doors, windows, wall rectangles and scale. CAD drawings give exact room polygons and areas, BIM sheets give exact areas, raster plans are segmented from their walls (OpenCV) and named from detector room boxes and OCR labels. Scale comes from CAD registration, BIM areas, room areas printed on the sheet, or door widths (0.85 m), in that order. Cached in `server/cache/takeoff/`.
  - `GET /x/prices` – unit prices per material from context.dev web search of Finnish supplier and price-guide pages (median of listed prices, with quotes and links), cached for 12 hours in `server/cache/prices.json`. The key is read from `CONTEXTDEV_API_KEY` or `~/.config/contextdev/api.env`.
- `/api` is served by the Trilobyte backend (`stoa-app`, port 8090, in the junction repo).

## Running

- `npm run dev` – dev server on 127.0.0.1:5174; `npm run build` then `npm run preview` serves `dist/` on 127.0.0.1:5175. Both proxy `/api` to 8090 and `/x` to 8101.
- Takeoff service: `uv venv server/.venv && uv pip install --python server/.venv/bin/python fastapi uvicorn httpx opencv-python-headless numpy`, then `server/.venv/bin/uvicorn server.main:app --host 127.0.0.1 --port 8101`.
- On this host both run as systemd user services, `trilobyte-ui` and `trilobyte-takeoff`, behind https://trilobyte.ajc.contexio.fi.
