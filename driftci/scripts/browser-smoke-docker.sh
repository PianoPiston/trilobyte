#!/usr/bin/env bash
# Reproducible real-Chromium QA without installing host browser libraries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${DRIFTCI_QA_OUT:-/tmp/driftci-browser}"
BASE="${DRIFTCI_URL:-http://10.0.2.2:8100}"
IMAGE="${PLAYWRIGHT_IMAGE:-mcr.microsoft.com/playwright:v1.65.1-noble}"

mkdir -p "$OUT"
# Rootless Docker maps its browser user to the host user; output is disposable QA data.
chmod a+rwx "$OUT"
if [[ ! -d "$OUT/node_modules/playwright-core" ]]; then
  npm install --prefix "$OUT" --no-audit --no-fund playwright-core@1.65.1
fi

exec docker run --rm --user root \
  -e PLAYWRIGHT_MODULE=/out/node_modules/playwright-core \
  -e DRIFTCI_URL="$BASE" \
  -e OUT_DIR=/out/public \
  -e CHROMIUM_EXECUTABLE=/ms-playwright/chromium-1255/chrome-linux64/chrome \
  -v "$ROOT:/driftci:ro" \
  -v "$OUT:/out" \
  "$IMAGE" node /driftci/scripts/browser-smoke.cjs
