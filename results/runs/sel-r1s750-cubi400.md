# Run sel-r1s750-cubi400

- date: 2026-11-14T02:35
- method: vlm model: r1s750 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 400 (val-cubi400) wall: 22s concurrency: 64
- tokens/q in 678 out 13; latency p50 3.2s p90 4.4s
- cost per 1k questions: €0.026
- ALL: acc 0.770 | macro-by-cell 0.770 | abstain 0.000 | precision 0.770 | false-confident(>= 0.8) 0.022 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 400 | 0.770 | 0.00 | 0.770 | 0.022 |  |
