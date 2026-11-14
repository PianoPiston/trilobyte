# Run TEST-router2-det2

- date: 2026-11-14T15:46
- method: std-router model: run1-step1050 prompt: zs max_pixels: 2000000 min_pixels: 0
- items: 6428 (test) wall: 210s concurrency: 32
- tokens/q in 499 out 9; latency p50 0.5s p90 2.7s
- cost per 1k questions: €0.016
- ALL: acc 0.577 | macro-by-cell 0.611 | abstain 0.418 | precision 0.992 | false-confident(>= 0.8) 0.004 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4305 | 0.413 | 0.58 | 0.985 | 0.006 |  |
| ifc_bench/text | 98 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 52 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/count | 29 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/count/ifc | 5 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/length | 6 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/volume | 12 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| opening_design/area | 9 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| opening_design/count | 22 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| opening_design/text | 13 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 599 | 0.920 | 0.08 | 0.995 | 0.005 | 0.000 |
| swiss_dwellings/count | 1278 | 1.000 | 0.00 | 1.000 | 0.000 |  |

| route | n | acc | abstain |
|---|---|---|---|
| det+vlm:agree | 985 | 0.982 | 0.00 |
| det+vlm:needs_check | 2495 | 0.000 | 1.00 |
| det+vlm:vlm | 346 | 0.980 | 0.00 |
| std:exact:apartment_area | 165 | 0.982 | 0.00 |
| std:exact:apartment_area:needs_check | 22 | 0.000 | 1.00 |
| std:exact:doors | 104 | 1.000 | 0.00 |
| std:exact:floor_area | 81 | 1.000 | 0.00 |
| std:exact:floor_area:needs_check | 23 | 0.000 | 1.00 |
| std:exact:ifc:IfcSlab_net_volume | 5 | 1.000 | 0.00 |
| std:exact:ifc:IfcWall_net_volume | 7 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcBeam | 1 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcColumn | 5 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcDoor | 6 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcLightFixture | 1 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcSanitaryTerminal | 3 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcSpace | 8 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcStair | 5 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcWall | 2 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcWindow | 3 | 1.000 | 0.00 |
| std:exact:ifc:space_area_ifc_qto | 45 | 1.000 | 0.00 |
| std:exact:ifc:spaces_total_area | 1 | 1.000 | 0.00 |
| std:exact:ifc:wall_length | 6 | 1.000 | 0.00 |
| std:exact:ifc:wall_net_side_area | 6 | 1.000 | 0.00 |
| std:exact:label_area | 101 | 1.000 | 0.00 |
| std:exact:room_area | 207 | 1.000 | 0.00 |
| std:exact:rooms_labelled | 637 | 1.000 | 0.00 |
| std:exact:symbols:bathtub | 89 | 1.000 | 0.00 |
| std:exact:symbols:shower | 32 | 1.000 | 0.00 |
| std:exact:symbols:toilet | 104 | 1.000 | 0.00 |
| std:exact:symbols:washbasin | 104 | 1.000 | 0.00 |
| std:exact:units | 104 | 1.000 | 0.00 |
| std:exact:windows | 104 | 1.000 | 0.00 |
| vlm-ft | 572 | 0.825 | 0.17 |
| vlm-ft:needs_check | 49 | 0.000 | 1.00 |
