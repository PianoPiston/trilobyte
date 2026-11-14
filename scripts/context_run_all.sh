#!/usr/bin/env bash
# Full context build, paced for the context.dev plan limit (10 requests/min): eval drawings first, then
# HABS records, then web search for all sources. Everything is cached; safe to kill and rerun.
# Rebuild from cache only (no API calls): CONTEXT_CACHE_ONLY=1 python scripts/context_build.py --web
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; . ~/.config/contextdev/api.env; set +a
PY=${PY:-/home/user/venvs/stoa/bin/python}
export CONTEXTDEV_MIN_INTERVAL=${CONTEXTDEV_MIN_INTERVAL:-6.2} HABS_WORKERS=6
# echo "== $(date) eval drawings"; $PY scripts/context_build.py --only-stems context/_eval_stems.txt --web --workers 6
echo "== $(date) habs records"; $PY scripts/context_fetch_archives.py habs
for s in habs finna wikimedia europeana; do
  echo "== $(date) web $s"; $PY scripts/context_build.py $s --web --workers 6
done
echo "== $(date) final rebuild (cache only) + coverage"; CONTEXT_CACHE_ONLY=1 $PY scripts/context_build.py --web
echo "== $(date) done"
