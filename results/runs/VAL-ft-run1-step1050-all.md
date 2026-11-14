# Run VAL-ft-run1-step1050-all

- date: 2026-11-14T13:56
- method: vlm model: run1-step1050 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 6955 (val) wall: 139s concurrency: 32
- tokens/q in 1080 out 13; latency p50 0.5s p90 0.7s
- cost per 1k questions: €0.010
- ALL: acc 0.638 | macro-by-cell 0.180 | abstain 0.062 | precision 0.680 | false-confident(>= 0.8) 0.018 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4304 | 0.781 | 0.00 | 0.781 | 0.020 |  |
| ifc_bench/text | 150 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 162 | 0.019 | 0.00 | 0.019 | 0.000 | 0.277 |
| ifc_models/area/ifc | 268 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/count | 101 | 0.248 | 0.00 | 0.248 | 0.010 |  |
| ifc_models/count/ifc | 12 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/length | 14 | 0.143 | 0.00 | 0.143 | 0.000 | 0.125 |
| ifc_models/volume | 29 | 0.000 | 0.00 | 0.000 | 0.000 | 0.714 |
| opening_design/count | 17 | 0.059 | 0.00 | 0.059 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 606 | 0.186 | 0.00 | 0.186 | 0.000 | 0.094 |
| swiss_dwellings/count | 1289 | 0.721 | 0.00 | 0.721 | 0.026 |  |
