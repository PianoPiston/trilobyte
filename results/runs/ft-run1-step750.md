# Run ft-run1-step750

- date: 2026-11-14T01:50
- method: vlm model: run1-step750 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 75s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.3s p90 12.0s
- cost per 1k questions: n/a
- ALL: acc 0.436 | macro-by-cell 0.220 | abstain 0.000 | precision 0.436 | false-confident(>= 0.8) 0.010 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.833 | 0.00 | 0.833 | 0.022 |  |
| ifc_models/area | 30 | 0.033 | 0.00 | 0.033 | 0.000 | 0.450 |
| ifc_models/count | 25 | 0.280 | 0.00 | 0.280 | 0.000 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.126 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.508 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.083 | 0.00 | 0.083 | 0.000 | 0.166 |
| swiss_dwellings/count | 60 | 0.750 | 0.00 | 0.750 | 0.017 |  |
