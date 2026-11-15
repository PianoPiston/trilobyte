# Trilobyte UI

Web interface for Trilobyte, which answers questions about construction drawings and marks the evidence on the sheet. It is a React + Vite single-page app that talks to the Trilobyte HTTP API (`/api`, served by the `stoa-app` backend on 127.0.0.1:8090).

- `npm run dev`: dev server on 127.0.0.1:5174, proxying `/api` to the backend.
- `npm run build`: type-check and build into `dist/`.
- `npm run preview`: serve `dist/` on 127.0.0.1:5175 with the same proxy.

Pages: `src/pages/Browse.tsx` (catalog and upload), `DrawingView.tsx` (viewer, question box, answer, evidence), `Search.tsx`, `Benchmark.tsx`, `Developers.tsx`. All styles are in `src/styles.css`.
