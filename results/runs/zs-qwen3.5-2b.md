# Run zs-qwen3.5-2b

- date: 2026-11-14T00:18
- method: vlm model: Qwen/Qwen3.5-2B prompt: zs max_pixels: 2000000
- items: 305 (val300) wall: 39s concurrency: 32
- tokens/q in 1764 out 265; latency p50 2.0s p90 9.2s
- cost per 1k questions: €0.058
- ALL: acc 0.200 | macro-by-cell 0.100 | abstain 0.000 | precision 0.200 | false-confident(>= 0.8) 0.007 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.322 | 0.00 | 0.322 | 0.022 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.000 | 0.800 |
| ifc_models/count | 25 | 0.080 | 0.00 | 0.080 | 0.000 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.571 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 1.067 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.067 | 0.00 | 0.067 | 0.000 | 0.428 |
| swiss_dwellings/count | 60 | 0.433 | 0.00 | 0.433 | 0.000 |  |
