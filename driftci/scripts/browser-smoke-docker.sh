#!/usr/bin/env bash
# Reproducible real-Chromium QA without installing host browser libraries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${DRIFTCI_QA_OUT:-/tmp/driftci-browser}"
BASE="${DRIFTCI_URL:-http://10.0.2.2:8100}"
IMAGE="${PLAYWRIGHT_IMAGE:-mcr.microsoft.com/playwright:v1.65.1-noble}"
SCRIPT="${DRIFTCI_QA_SCRIPT:-release-smoke.cjs}"
if [[ $# -gt 0 ]]; then
  BASE="$1"
  shift
fi
if [[ $# -gt 0 ]]; then
  echo "Use DRIFTCI_QA_SCRIPT=release-smoke.cjs or browser-smoke.cjs; extra arguments are ignored." >&2
  exit 2
fi
case "$SCRIPT" in
  release-smoke.cjs|browser-smoke.cjs) ;;
  *) echo "Unknown QA script. Select an explicit checked-in smoke script." >&2; exit 2 ;;
esac

SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" ]]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

# The legacy workflow resets/replays demo state. It always gets a fresh database
# and offline server, including when the caller supplied a public target by mistake.
if [[ "$SCRIPT" = browser-smoke.cjs ]]; then
  mkdir -p "$OUT"
  PORT="${DRIFTCI_QA_PORT:-$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')}"
  DB="$OUT/isolated-$(date +%s%N).sqlite"
  DRIFTCI_OFFLINE=1 DRIFTCI_CONTEXTDEV_API_KEY=test-secret DRIFTCI_DB_PATH="$DB" \
    "$ROOT/.venv/bin/python" -m uvicorn server.main:app --app-dir "$ROOT" --host 127.0.0.1 --port "$PORT" >"$OUT/isolated-server.log" 2>&1 &
  SERVER_PID="$!"
  BASE="http://10.0.2.2:$PORT"
  for _ in {1..80}; do
    if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/api/health" >/dev/null; then break; fi
    sleep 0.25
  done
  curl -fsS --max-time 5 "http://127.0.0.1:$PORT/api/health" >/dev/null
  echo "Legacy QA: isolated database $DB; server $BASE"
fi

mkdir -p "$OUT"
# Rootless Docker maps its browser user to the host user; output is disposable QA data.
chmod a+rwx "$OUT"
if [[ ! -d "$OUT/node_modules/playwright-core" ]]; then
  npm install --prefix "$OUT" --no-audit --no-fund playwright-core@1.65.1
fi

docker run --rm --user root \
  -e PLAYWRIGHT_MODULE=/out/node_modules/playwright-core \
  -e DRIFTCI_URL="$BASE" \
  -e DRIFTCI_REPOSITORY="${DRIFTCI_REPOSITORY:-}" \
  -e DRIFTCI_KEEP_WORKSPACE="${DRIFTCI_KEEP_WORKSPACE:-}" \
  -e DRIFTCI_RELEASE_DECISION_QA="${DRIFTCI_RELEASE_DECISION_QA:-}" \
  -e OUT_DIR=/out/public \
  -e CHROMIUM_EXECUTABLE=/ms-playwright/chromium-1255/chrome-linux64/chrome \
  -v "$ROOT:/driftci:ro" \
  -v "$OUT:/out" \
  "$IMAGE" node "/driftci/scripts/$SCRIPT"
