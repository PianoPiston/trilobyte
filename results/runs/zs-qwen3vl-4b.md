# Run zs-qwen3vl-4b

- date: 2026-11-14T00:11
- method: vlm model: Qwen/Qwen3-VL-4B-Instruct prompt: zs max_pixels: 2000000
- items: 305 (val300) wall: 55s concurrency: 32
- tokens/q in 1759 out 171; latency p50 2.8s p90 17.8s
- cost per 1k questions: €0.083
- ALL: acc 0.259 | macro-by-cell 0.133 | abstain 0.000 | precision 0.259 | false-confident(>= 0.8) 0.187 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 90 | 0.433 | 0.00 | 0.433 | 0.156 |  |
| ifc_models/area | 30 | 0.000 | 0.00 | 0.000 | 0.233 | 0.675 |
| ifc_models/count | 25 | 0.160 | 0.00 | 0.160 | 0.120 |  |
| ifc_models/length | 10 | 0.000 | 0.00 | 0.000 | 0.200 | 0.858 |
| ifc_models/volume | 10 | 0.000 | 0.00 | 0.000 | 1.000 | 1.000 |
| opening_design/count | 17 | 0.000 | 0.00 | 0.000 | 0.294 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 60 | 0.067 | 0.00 | 0.067 | 0.150 | 0.490 |
| swiss_dwellings/count | 60 | 0.533 | 0.00 | 0.533 | 0.117 |  |
