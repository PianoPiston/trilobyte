# DriftCI frontend

Vite, React and TypeScript operations console for the DriftCI API.

## Development

```sh
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8100`. Start the DriftCI FastAPI backend on that port before loading the console. If bootstrap fails, the UI shows a retry screen and keeps the backend connection details visible.

No frontend environment variables or credentials are required. Source integrations and GitHub credentials belong to the backend.

## Production

```sh
npm run build
npm run preview
```

The production output is `dist/`, which the FastAPI process serves directly. All data, evidence, metrics and diffs come from the API contract in `../PRODUCT.md`.
