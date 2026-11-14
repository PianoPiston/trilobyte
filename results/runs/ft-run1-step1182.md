# Run ft-run1-step1182

- date: 2026-11-14T02:30
- method: vlm model: run1-step1182 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 305 (val300) wall: 37s concurrency: 32
- tokens/q in 1612 out 15; latency p50 3.1s p90 5.5s
- cost per 1k questions: n/a
- ALL: acc 0.449 | macro-by-cell 0.227 | abstain 0.000 | precision 0.449 | false-confident(>= 0.8) 0.003 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.811 | 0.00 | 0.811 | 0.000 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.000 | 0.358 |
| ifc_models/count | 25 | 0.280 | 0.00 | 0.280 | 0.000 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.163 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.491 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.167 | 0.00 | 0.167 | 0.000 | 0.068 |
| swiss_dwellings/count | 60 | 0.783 | 0.00 | 0.783 | 0.017 |  |
