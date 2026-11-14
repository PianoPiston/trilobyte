# Run sel-r1s1182-cubi400

- date: 2026-11-14T02:36
- method: vlm model: r1s1182 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 400 (val-cubi400) wall: 21s concurrency: 64
- tokens/q in 678 out 13; latency p50 3.2s p90 4.2s
- cost per 1k questions: €0.024
- ALL: acc 0.767 | macro-by-cell 0.767 | abstain 0.000 | precision 0.767 | false-confident(>= 0.8) 0.018 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 400 | 0.767 | 0.00 | 0.767 | 0.018 |  |
