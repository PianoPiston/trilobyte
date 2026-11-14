# Run ft-run1-step600

- date: 2026-11-14T01:36
- method: vlm model: run1-step600 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 73s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.6s p90 11.7s
- cost per 1k questions: n/a
- ALL: acc 0.430 | macro-by-cell 0.212 | abstain 0.000 | precision 0.430 | false-confident(>= 0.8) 0.010 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.778 | 0.00 | 0.778 | 0.022 |  |
| ifc_models/area | 30 | 0.033 | 0.00 | 0.033 | 0.000 | 0.478 |
| ifc_models/count | 25 | 0.160 | 0.00 | 0.160 | 0.000 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.410 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.941 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.133 | 0.00 | 0.133 | 0.000 | 0.098 |
| swiss_dwellings/count | 60 | 0.800 | 0.00 | 0.800 | 0.017 |  |
