#!/usr/bin/env bash
# At DEADLINE (default 01:30 local) stop the paced build and write final context files + COVERAGE.md from cache.
cd "$(dirname "$0")/.."
DEADLINE=${DEADLINE:-"tomorrow 01:30"}
target=$(date -d "$DEADLINE" +%s)
while [ "$(date +%s)" -lt "$target" ]; do
  pgrep -f context_run_all.sh > /dev/null || exit 0   # build finished on its own (it does its own final rebuild)
  sleep 60
done
for p in $(pgrep -f context_run_all.sh) $(pgrep -f "scripts/context_build.py") $(pgrep -f "scripts/context_fetch_archives.py"); do kill "$p" 2>/dev/null; done
sleep 5
echo "== $(date) deadline: final rebuild from cache" >> context/run_all.log
CONTEXT_CACHE_ONLY=1 /home/user/venvs/stoa/bin/python scripts/context_build.py --web >> context/run_all.log 2>&1
echo "== $(date) done (deadline)" >> context/run_all.log
