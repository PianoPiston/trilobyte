# Run zs-qwen3.5-4b

- date: 2026-11-14T00:08
- method: vlm model: Qwen/Qwen3.5-4B prompt: zs max_pixels: 2000000
- items: 305 (val300) wall: 64s concurrency: 32
- tokens/q in 1764 out 237; latency p50 3.4s p90 16.9s
- cost per 1k questions: €0.096
- ALL: acc 0.338 | macro-by-cell 0.181 | abstain 0.000 | precision 0.338 | false-confident(>= 0.8) 0.121 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.567 | 0.00 | 0.567 | 0.022 |  |
| ifc_models/area | 30 | 0.033 | 0.00 | 0.033 | 0.167 | 0.804 |
| ifc_models/count | 25 | 0.160 | 0.00 | 0.160 | 0.120 |  |
| ifc_models/length | 10 | 0.100 | 0.00 | 0.100 | 0.300 | 0.481 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 1.000 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.117 | 0.00 | 0.117 | 0.317 | 0.439 |
| swiss_dwellings/count | 60 | 0.650 | 0.00 | 0.650 | 0.083 |  |
