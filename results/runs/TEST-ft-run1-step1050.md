# Run TEST-ft-run1-step1050

- date: 2026-11-14T02:49
- method: vlm model: run1-step1050 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 6428 (test) wall: 183s concurrency: 64
- tokens/q in 1111 out 13; latency p50 1.4s p90 1.9s
- cost per 1k questions: €0.013
- ALL: acc 0.685 | macro-by-cell 0.182 | abstain 0.016 | precision 0.696 | false-confident(>= 0.8) 0.019 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4305 | 0.785 | 0.00 | 0.785 | 0.019 |  |
| ifc_bench/text | 98 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 52 | 0.000 | 0.00 | 0.000 | 0.000 | 0.442 |
| ifc_models/count | 29 | 0.103 | 0.00 | 0.103 | 0.000 |  |
| ifc_models/count/ifc | 5 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/length | 6 | 0.000 | 0.00 | 0.000 | 0.000 | 0.356 |
| ifc_models/volume | 12 | 0.000 | 0.00 | 0.000 | 0.000 | 0.876 |
| opening_design/area | 9 | 0.111 | 0.00 | 0.111 | 0.111 | 0.910 |
| opening_design/count | 22 | 0.318 | 0.00 | 0.318 | 0.000 |  |
| opening_design/text | 13 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 599 | 0.147 | 0.00 | 0.147 | 0.000 | 0.112 |
| swiss_dwellings/count | 1278 | 0.724 | 0.00 | 0.724 | 0.030 |  |
