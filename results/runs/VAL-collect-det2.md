# Run VAL-collect-det2

- date: 2026-11-14T15:43
- method: std-router model: run1-step1050 prompt: zs max_pixels: 2000000 min_pixels: 0
- items: 6955 (val) wall: 250s concurrency: 32
- tokens/q in 450 out 8; latency p50 0.5s p90 2.8s
- cost per 1k questions: n/a
- ALL: acc 0.807 | macro-by-cell 0.730 | abstain 0.022 | precision 0.825 | false-confident(>= 0.8) 0.051 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4304 | 0.731 | 0.00 | 0.731 | 0.082 |  |
| ifc_bench/text | 150 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 162 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/area/ifc | 268 | 0.996 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/count | 101 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/count/ifc | 12 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/length | 14 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/volume | 29 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| opening_design/count | 17 | 0.059 | 0.00 | 0.059 | 0.000 |  |
| opening_design/text | 3 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 606 | 0.969 | 0.00 | 0.969 | 0.000 | 0.000 |
| swiss_dwellings/count | 1289 | 1.000 | 0.00 | 1.000 | 0.000 |  |

| route | n | acc | abstain |
|---|---|---|---|
| det+vlm:collect | 3826 | 0.699 | 0.00 |
| std:exact:apartment_area | 192 | 0.938 | 0.00 |
| std:exact:doors | 104 | 1.000 | 0.00 |
| std:exact:floor_area | 104 | 0.933 | 0.00 |
| std:exact:ifc:IfcSlab_net_volume | 15 | 1.000 | 0.00 |
| std:exact:ifc:IfcWall_net_volume | 14 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcBeam | 3 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcColumn | 10 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcDoor | 22 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcSanitaryTerminal | 1 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcSpace | 23 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcStair | 14 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcWall | 22 | 1.000 | 0.00 |
| std:exact:ifc:count_IfcWindow | 18 | 1.000 | 0.00 |
| std:exact:ifc:space_area_ifc_geometry | 284 | 1.000 | 0.00 |
| std:exact:ifc:space_area_ifc_qto | 118 | 1.000 | 0.00 |
| std:exact:ifc:spaces_total_area | 13 | 1.000 | 0.00 |
| std:exact:ifc:wall_length | 14 | 1.000 | 0.00 |
| std:exact:ifc:wall_net_side_area | 14 | 1.000 | 0.00 |
| std:exact:label_area | 102 | 1.000 | 0.00 |
| std:exact:room_area | 208 | 1.000 | 0.00 |
| std:exact:rooms_labelled | 643 | 1.000 | 0.00 |
| std:exact:symbols:bathtub | 95 | 1.000 | 0.00 |
| std:exact:symbols:shower | 31 | 1.000 | 0.00 |
| std:exact:symbols:toilet | 104 | 1.000 | 0.00 |
| std:exact:symbols:washbasin | 104 | 1.000 | 0.00 |
| std:exact:units | 104 | 1.000 | 0.00 |
| std:exact:windows | 104 | 1.000 | 0.00 |
| vlm-ft | 649 | 0.733 | 0.23 |
