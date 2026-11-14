#!/bin/bash
# Router v2 pipeline on the GPU instance (run from /root/work/stoa). CKPT = detector checkpoint.
#  1. detector over train hold-out + val + test cubicasa drawings (images only)
#  2. detector count policy on the TRAIN hold-out
#  3. VAL collect run (policy=None records all signals; VLM answers live from vLLM)
#  4. router policy on VAL
#  5. held-out TEST run with the frozen policies
set -ex
CKPT=${CKPT:-/root/ckpt/det1/last.pt}
TAG=${TAG:-det1}
export STOA_DATA=/root/data/junction-dataset STOA_DET_MAX_SIDE=1600 STOA_DET_CLASSES=${STOA_DET_CLASSES:-v1}
LABELS=${LABELS:-/root/work/det_train.jsonl}
PY="/root/venv/bin/python -I"
EB='{"chat_template_kwargs": {"enable_thinking": false}}'
CUDA_VISIBLE_DEVICES=0 $PY scripts/run_detector.py --tta --ckpt $CKPT --data $STOA_DATA --paths /root/work/det_paths.txt --out /root/work/dets_$TAG.jsonl
$PY scripts/calibrate_detector.py /root/work/dets_$TAG.jsonl $LABELS results/detpolicy_$TAG.json
if [ -z "$SKIP_VAL" ]; then
$PY eval.py run --split val --method std-router --model run1-step1050 --extra-body "$EB" --concurrency 32 \
   --det-cache /root/work/dets_$TAG.jsonl --det-policy results/detpolicy_$TAG.json \
   --run-name VAL-collect-$TAG --notes "router v2 collect (answers everything, records signals) for VAL calibration"
fi
$PY scripts/calibrate_router.py results/runs/VAL-collect-$TAG.jsonl results/policy_$TAG.json
if [ -n "$RUN_TEST" ]; then
STOA_ALLOW_TEST=1 $PY eval.py run --split test --method std-router --model run1-step1050 --extra-body "$EB" --concurrency 32 \
   --det-cache /root/work/dets_$TAG.jsonl --det-policy results/detpolicy_$TAG.json --policy results/policy_$TAG.json \
   --hourly-eur 1.75 --run-name TEST-router2-$TAG --notes "HELD-OUT TEST router v2: std files + detector + fine-tuned VLM, VAL-calibrated policy; needs-check = abstain"
fi
echo PIPELINE_DONE
