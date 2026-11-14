# Run exp-r1s300-cubi400-minpx0

- date: 2026-11-14T01:08
- method: vlm model: r1s300 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 400 (val-cubi400) wall: 45s concurrency: 32
- tokens/q in 678 out 13; latency p50 3.5s p90 4.3s
- cost per 1k questions: n/a
- ALL: acc 0.723 | macro-by-cell 0.723 | abstain 0.000 | precision 0.723 | false-confident(>= 0.8) 0.013 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 400 | 0.723 | 0.00 | 0.723 | 0.013 |  |
