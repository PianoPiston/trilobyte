# Run ft-run1-step1050

- date: 2026-11-14T02:19
- method: vlm model: run1-step1050 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 73s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.0s p90 12.1s
- cost per 1k questions: n/a
- ALL: acc 0.459 | macro-by-cell 0.244 | abstain 0.000 | precision 0.459 | false-confident(>= 0.8) 0.003 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.822 | 0.00 | 0.822 | 0.000 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.000 | 0.350 |
| ifc_models/count | 25 | 0.320 | 0.00 | 0.320 | 0.000 |  |
| ifc_models/length | 10 | 0.100 | 0.00 | 0.100 | 0.000 | 0.150 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.491 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.183 | 0.00 | 0.183 | 0.000 | 0.077 |
| swiss_dwellings/count | 60 | 0.767 | 0.00 | 0.767 | 0.017 |  |
