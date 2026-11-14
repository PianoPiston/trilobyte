#!/usr/bin/env bash
# Historic-context A/B eval: the same VLM with vs without the per-drawing context block.
# Needs a vLLM OpenAI-compatible endpoint serving Qwen/Qwen3.5-4B (+ optional LoRA), see DOCS/model-serving.md.
#
#   ssh -N -L 8000:127.0.0.1:8000 <gpu host> &   # tunnel to the vLLM server (see AGENTS.md GPU section)
#   BASE_URL=http://localhost:8000/v1 FT_NAME=stoa-ft HOURLY_EUR=1.65 scripts/context_eval.sh
#
# Images are read from DATA/historic-raw/junction-dataset (STOA_HISTORIC_DATA); only the 57 eval drawings are
# needed (scripts/context_fetch_eval_images.sh fetches them). Context files are read from context/.
# Run from the laptop: images are sent as data URLs, so nothing needs to be copied to the GPU host.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-$( [ -x /home/user/venvs/stoa/bin/python ] && echo /home/user/venvs/stoa/bin/python || echo python3 )}
BASE_URL=${BASE_URL:-http://localhost:8000/v1}
BASE_MODEL=${BASE_MODEL:-Qwen/Qwen3.5-4B}
FT_NAME=${FT_NAME:-}
HOURLY_EUR=${HOURLY_EUR:-1.65}   # reference A100 price (the Spark itself is free), keeps €/1k q comparable
CONC=${CONC:-16}
curl -sf "$BASE_URL/models" > /dev/null || { echo "no endpoint at $BASE_URL"; exit 1; }

$PY scripts/context_eval.py --dry-run
# 1) base model, zero-shot JSON prompt: no context / record+web context / record-only context
$PY scripts/context_eval.py --model "$BASE_MODEL" --base-url "$BASE_URL" --style zs --modes noctx,ctx,ctx-noweb \
    --run-name hist-base-zs --hourly-eur "$HOURLY_EUR" --concurrency "$CONC" --notes "base Qwen3.5-4B zero-shot"
# 2) fine-tuned LoRA (trained on quantity questions; context is prepended to the raw question)
if [ -n "$FT_NAME" ]; then
  $PY scripts/context_eval.py --model "$FT_NAME" --base-url "$BASE_URL" --style ft --modes noctx,ctx \
      --run-name hist-ft --hourly-eur "$HOURLY_EUR" --concurrency "$CONC" --notes "fine-tuned LoRA $FT_NAME"
fi
