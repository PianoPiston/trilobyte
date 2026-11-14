# Serving the question-answering stack (for the demo/API)

Everything below runs on the current Verda instance (`ssh root@<gpu-host>`, 2x RTX PRO 6000; vLLM on GPU1, already running in tmux `vllm` with the adapter named `run1-step1050`, bound to 127.0.0.1). Code is in `/root/work/stoa` (a mirror of this repo's `src/`, `eval.py` and `results/`).

## 1. Start the model server (base + fine-tuned LoRA)

```bash
# NAME = adapter name clients will use, AD = adapter dir (best checkpoint, see results/leaderboard.md)
tmux new-session -d -s vllm "/root/work/serve.sh Qwen/Qwen3.5-4B --max-model-len 8192 \
   --enable-lora --max-lora-rank 32 --lora-modules NAME=AD > /root/logs/vllm.log 2>&1"
curl localhost:8000/v1/models     # lists Qwen/Qwen3.5-4B (base) and NAME (fine-tuned)
```

The server speaks the OpenAI-compatible API on port 8000. It is not exposed publicly; tunnel with `ssh -N -L 8000:127.0.0.1:8000 root@<gpu-host>`, or put the demo backend on the same machine.

## 2. Ask the fine-tuned model directly

The prompt must match training exactly: user content = the image, then the raw question. Do not add a system prompt, and disable thinking.

```python
from openai import OpenAI
c = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
r = c.chat.completions.create(model="NAME", max_tokens=64, temperature=0, logprobs=True,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url}},   # PNG data URL, <= 2 MP (stoa.images.load_image)
        {"type": "text", "text": "How many saunas are on this floor plan?"}]}])
# -> '{"answer": 1, "unit": "count"}'
```

Confidence is the probability of the answer tokens (`stoa.methods.vlm.answer_value_prob`), not a self-reported number. On val, answers with confidence >= 0.7 are about 97% precise. Show lower-confidence answers as "needs check" with the evidence (see `results/leaderboard.md`).

## 3. Router v2 (RECOMMENDED for the product): standardized files + detector + VLM, with "needs check"

```python
import asyncio, os, sys; sys.path.insert(0, "src")
os.environ["STOA_DET_CLASSES"] = "v2"          # det2 (selected; symbols + room-type boxes). "v1" for det1
from stoa.methods.std_router import StdRouter
from stoa.methods.vlm import VLMMethod          # or FTWithEvidence(...) to add base-model grounding boxes
vlm = VLMMethod("run1-step1050", "http://localhost:8000/v1", prompt="ft", max_tokens=64,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}})
r = StdRouter(vlm, det_cache="artifacts/det2/dets_det2_all.jsonl",      # cached detector output, all 4,787 cubicasa drawings
              det_policy="results/detpolicy_det2.json", policy="results/policy_det2.json")
print(asyncio.run(r.answer("data/cubicasa5k/high_quality-10360.png", "How many toilet bowls are drawn?")))
```

- swiss_dwellings / ifc_models: answered from the exact standardized file (`stoa.answer.answer_std`); no GPU needed. Ambiguous cases (flags) return `needs_check`.
- cubicasa5k: detector boxes (from the cache; for a new drawing run `scripts/run_detector.py --tta` on GPU, ~0.4 s) + the fine-tuned VLM; answered only when the VAL-calibrated policy accepts.
- Output keys: `value` (None = **needs check**), `needs_check`, `suggested_value` + `suggested_by` (best guess shown to the user for checking), `evidence` (polygons/boxes; detector boxes are `bbox_px` in original image pixels plus `bbox_norm` 0-1), `method`, `confidence`, `flags`, `drawing_id`, `ground_truth_eligible` (False for model-derived files).
- Standardized files: `scripts/export_std.py OUTDIR [--dets ... --det-policy ...] --validate` writes one JSON per drawing (`schema/drawing.schema.json`). A local export of all swiss + IFC files is in `standardized/` (git-ignored, 62 MB, regenerable).
- TEST numbers (auto-answered share / precision per cell) are in `results/leaderboard.md`, section "Router v2 result".

## 3b. Old router (v1, answers everything)

```python
import asyncio, sys; sys.path.insert(0, "src")
from stoa.methods.router import Router
from stoa.methods.swiss_dxf import SwissDXFMethod
from stoa.methods.ifc_route import IFCMethod
from stoa.methods.vlm import FTWithEvidence
m = Router([SwissDXFMethod(), IFCMethod()],
           FTWithEvidence("NAME", "Qwen/Qwen3.5-4B", "http://localhost:8000/v1",
                          extra_body={"chat_template_kwargs": {"enable_thinking": False}}))
print(asyncio.run(m.answer("data/cubicasa5k/high_quality-10360.png", "How many toilet bowls are drawn?")))
```

Paths are relative to `STOA_DATA` (the dataset root). Every answer is a dict:

| key | meaning |
|---|---|
| `value`, `unit` | the answer (`None` means abstain / needs check) |
| `method` | `dxf:<rule>`, `ifc:<rule>` or `vlm-ft` |
| `confidence` | 0.99 for deterministic routes, answer-token probability for the VLM |
| `evidence` | DXF: room/unit polygons (`polygon_dxf`, `polygon_norm` in 0-1 page coordinates, y down) or door bboxes. IFC: element `ifc_global_id`s. VLM: boxes from a grounding call to the base model (`bbox_norm1000`, `bbox_px` in the image as sent to the model) |
| `tokens_in/out`, `latency_s` | for the cost display |

Evidence quality: the DXF/IFC evidence is exact. The VLM boxes come from zero-shot grounding by the base model, so treat them as approximate pointers.

## Cost reference

Router v2 (det2) on TEST: €0.016 per 1k questions (one RTX PRO 6000 at ~€1.75/h for the VLM, concurrency 32; the detector adds ~0.4 s GPU per drawing with TTA, computed once per drawing). Older numbers were measured by `eval.py` with vLLM on one A100 (€1.65/h), at concurrency 64. See `results/leaderboard.md` for the current numbers per route. The DXF and IFC routes are CPU-only and cost effectively nothing.
