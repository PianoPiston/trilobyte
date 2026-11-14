# Run zs-qwen3vl-8b-fp8

- date: 2026-11-14T00:15
- method: vlm model: Qwen/Qwen3-VL-8B-Instruct-FP8 prompt: zs max_pixels: 2000000
- items: 305 (val300) wall: 66s concurrency: 32
- tokens/q in 1759 out 98; latency p50 4.6s p90 14.0s
- cost per 1k questions: €0.100
- ALL: acc 0.295 | macro-by-cell 0.152 | abstain 0.000 | precision 0.295 | false-confident(>= 0.8) 0.177 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.533 | 0.00 | 0.533 | 0.222 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.233 | 0.902 |
| ifc_models/count | 25 | 0.160 | 0.00 | 0.160 | 0.200 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.564 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 1.000 | 1.000 |
| opening_design/count | 17 | 0.059 | 0.00 | 0.059 | 0.118 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.333 |  |
| swiss_dwellings/area | 60 | 0.067 | 0.00 | 0.067 | 0.033 | 0.354 |
| swiss_dwellings/count | 60 | 0.550 | 0.00 | 0.550 | 0.117 |  |
