#!/usr/bin/env bash
# Fetch only the images of the historic eval drawings (HTTP range requests, ~50 MB) into DATA/historic-raw.
set -euo pipefail
cd "$(dirname "$0")/.."
URL=https://fwjydgxpttajiqpfmqtj.supabase.co/storage/v1/object/public/stoa-junction-2026/junction-dataset.zip
PREFIXES=$(python3 -c "import json; print(' '.join(sorted({'junction-dataset/'+json.loads(l)['path'] for l in open('results/samples/historic_eval.jsonl')})))")
python3 -I scripts/remote_zip.py "$URL" extract DATA/historic-raw $PREFIXES
