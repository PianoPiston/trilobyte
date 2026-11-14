# Run zs-qwen3.5-4b-4mp

- date: 2026-11-14T00:36
- method: vlm model: Qwen/Qwen3.5-4B prompt: zs max_pixels: 4300000
- items: 305 (val300) wall: 111s concurrency: 32
- tokens/q in 3367 out 232; latency p50 7.5s p90 29.3s
- cost per 1k questions: €0.166
- ALL: acc 0.341 | macro-by-cell 0.235 | abstain 0.000 | precision 0.341 | false-confident(>= 0.8) 0.167 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.578 | 0.00 | 0.578 | 0.022 |  |
| ifc_models/area | 30 | 0.067 | 0.00 | 0.067 | 0.100 | 0.683 |
| ifc_models/count | 25 | 0.120 | 0.00 | 0.120 | 0.080 |  |
| ifc_models/length | 10 | 0.100 | 0.00 | 0.100 | 0.500 | 0.518 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 1.000 |
| opening_design/count | 17 | 0.235 | 0.00 | 0.235 | 0.118 |  |
| opening_design/text | 3 | 0.333 | 0.00 | 0.333 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.117 | 0.00 | 0.117 | 0.433 | 0.429 |
| swiss_dwellings/count | 60 | 0.567 | 0.00 | 0.567 | 0.183 |  |
