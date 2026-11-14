# Run sel-r1s900-cubi400

- date: 2026-11-14T02:36
- method: vlm model: r1s900 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 400 (val-cubi400) wall: 21s concurrency: 64
- tokens/q in 678 out 13; latency p50 3.2s p90 4.0s
- cost per 1k questions: €0.024
- ALL: acc 0.765 | macro-by-cell 0.765 | abstain 0.000 | precision 0.765 | false-confident(>= 0.8) 0.013 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 400 | 0.765 | 0.00 | 0.765 | 0.013 |  |
