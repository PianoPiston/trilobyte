import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// stoa-app (junction/app) serves /api; the takeoff service in server/ serves /x
const proxy = { "/api": "http://127.0.0.1:8090", "/docs": "http://127.0.0.1:8090", "/openapi.json": "http://127.0.0.1:8090", "/x": "http://127.0.0.1:8101" };

export default defineConfig({
  plugins: [react()],
  server: { port: 5174, strictPort: true, proxy },
  preview: { port: 5175, strictPort: true, proxy, allowedHosts: ["trilobyte.ajc.contexio.fi"], headers: { "Cache-Control": "no-cache" } },
});
