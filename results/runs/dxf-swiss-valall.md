# Run dxf-swiss-valall

- date: 2026-11-14T00:57
- method: swiss-dxf model: None prompt: zs max_pixels: 2000000
- items: 1895 (val-swiss-all) wall: 69s concurrency: 8
- tokens/q in 0 out 0; latency p50 0.0s p90 0.9s
- cost per 1k questions: €0.001
- ALL: acc 0.802 | macro-by-cell 0.839 | abstain 0.177 | precision 0.975 | false-confident(>= 0.8) 0.021 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| swiss_dwellings/area | 606 | 0.942 | 0.00 | 0.945 | 0.054 | 0.000 |
| swiss_dwellings/count | 1289 | 0.736 | 0.26 | 0.994 | 0.005 |  |

| route | n | acc | abstain |
|---|---|---|---|
| dxf:apartment_area | 192 | 0.865 | 0.00 |
| dxf:door_frames | 104 | 1.000 | 0.00 |
| dxf:floor_area | 104 | 0.933 | 0.00 |
| dxf:label_area | 102 | 1.000 | 0.00 |
| dxf:room_area | 206 | 1.000 | 0.00 |
| dxf:rooms_labelled | 643 | 0.991 | 0.00 |
| dxf:units | 104 | 1.000 | 0.00 |
| dxf:windows/3 | 104 | 1.000 | 0.00 |
| swiss-dxf | 336 | 0.000 | 1.00 |
