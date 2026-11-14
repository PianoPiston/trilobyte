# Run ft-run1-step450

- date: 2026-11-14T01:22
- method: vlm model: run1-step450 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 73s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.5s p90 12.0s
- cost per 1k questions: n/a
- ALL: acc 0.413 | macro-by-cell 0.221 | abstain 0.000 | precision 0.413 | false-confident(>= 0.8) 0.010 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.756 | 0.00 | 0.756 | 0.022 |  |
| ifc_models/area | 30 | 0.100 | 0.00 | 0.100 | 0.000 | 0.433 |
| ifc_models/count | 25 | 0.080 | 0.00 | 0.080 | 0.040 |  |
| ifc_models/length | 10 | 0.200 | 0.00 | 0.200 | 0.000 | 0.161 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.993 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.117 | 0.00 | 0.117 | 0.000 | 0.146 |
| swiss_dwellings/count | 60 | 0.733 | 0.00 | 0.733 | 0.000 |  |
