# Run ft-run1-step300

- date: 2026-11-14T01:06
- method: vlm model: run1-step300 prompt: ft max_pixels: 2000000
- items: 305 (val300) wall: 74s concurrency: 32
- tokens/q in 1612 out 15; latency p50 6.3s p90 12.1s
- cost per 1k questions: n/a
- ALL: acc 0.400 | macro-by-cell 0.192 | abstain 0.000 | precision 0.400 | false-confident(>= 0.8) 0.007 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.744 | 0.00 | 0.744 | 0.011 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.000 | 0.532 |
| ifc_models/count | 25 | 0.120 | 0.00 | 0.120 | 0.040 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.142 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 0.000 | 0.937 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.150 | 0.00 | 0.150 | 0.000 | 0.166 |
| swiss_dwellings/count | 60 | 0.717 | 0.00 | 0.717 | 0.000 |  |
