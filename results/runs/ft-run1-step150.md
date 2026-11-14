# Run ft-run1-step150

- date: 2026-11-14T00:52
- method: vlm model: run1-step150 prompt: ft max_pixels: 2000000
- items: 305 (val300) wall: 75s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.8s p90 12.3s
- cost per 1k questions: n/a
- ALL: acc 0.380 | macro-by-cell 0.203 | abstain 0.000 | precision 0.380 | false-confident(>= 0.8) 0.013 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.689 | 0.00 | 0.689 | 0.033 |  |
| ifc_models/area | 30 | 0.033 | 0.00 | 0.033 | 0.000 | 0.371 |
| ifc_models/count | 25 | 0.240 | 0.00 | 0.240 | 0.040 |  |
| ifc_models/length | 10 | 0.100 | 0.00 | 0.100 | 0.000 | 0.123 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 1.000 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.100 | 0.00 | 0.100 | 0.000 | 0.284 |
| swiss_dwellings/count | 60 | 0.667 | 0.00 | 0.667 | 0.000 |  |
