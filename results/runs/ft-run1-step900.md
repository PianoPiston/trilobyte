# Run ft-run1-step900

- date: 2026-11-14T02:04
- method: vlm model: run1-step900 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 73s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.4s p90 12.2s
- cost per 1k questions: n/a
- ALL: acc 0.443 | macro-by-cell 0.224 | abstain 0.000 | precision 0.443 | false-confident(>= 0.8) 0.003 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.800 | 0.00 | 0.800 | 0.000 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.000 | 0.358 |
| ifc_models/count | 25 | 0.280 | 0.00 | 0.280 | 0.000 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.089 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.746 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.150 | 0.00 | 0.150 | 0.000 | 0.083 |
| swiss_dwellings/count | 60 | 0.783 | 0.00 | 0.783 | 0.017 |  |
