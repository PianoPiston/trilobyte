# Run TEST-zs-qwen3.5-4b

- date: 2026-11-14T02:57
- method: vlm model: Qwen/Qwen3.5-4B prompt: zs max_pixels: 2000000 min_pixels: 0
- items: 6428 (test) wall: 534s concurrency: 64
- tokens/q in 1261 out 187; latency p50 2.8s p90 13.8s
- cost per 1k questions: €0.038
- ALL: acc 0.471 | macro-by-cell 0.141 | abstain 0.016 | precision 0.479 | false-confident(>= 0.8) 0.120 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4305 | 0.517 | 0.00 | 0.517 | 0.064 |  |
| ifc_bench/text | 98 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 52 | 0.000 | 0.00 | 0.000 | 0.058 | 0.998 |
| ifc_models/count | 29 | 0.172 | 0.00 | 0.172 | 0.276 |  |
| ifc_models/count/ifc | 5 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/length | 6 | 0.000 | 0.00 | 0.000 | 0.500 | 0.591 |
| ifc_models/volume | 12 | 0.000 | 0.00 | 0.000 | 0.000 | 1.000 |
| opening_design/area | 9 | 0.111 | 0.00 | 0.111 | 0.000 | 0.977 |
| opening_design/count | 22 | 0.227 | 0.00 | 0.227 | 0.000 |  |
| opening_design/text | 13 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 599 | 0.092 | 0.00 | 0.092 | 0.356 | 0.609 |
| swiss_dwellings/count | 1278 | 0.576 | 0.00 | 0.576 | 0.211 |  |
