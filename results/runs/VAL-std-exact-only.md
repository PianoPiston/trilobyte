# Run VAL-std-exact-only

- date: 2026-11-14T15:42
- method: std-router model: None prompt: zs max_pixels: 2000000 min_pixels: 0
- items: 2481 (val) wall: 126s concurrency: 4
- tokens/q in 0 out 0; latency p50 0.0s p90 0.8s
- cost per 1k questions: n/a
- ALL: acc 0.835 | macro-by-cell 0.835 | abstain 0.165 | precision 1.000 | false-confident(>= 0.8) 0.000 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| ifc_models/area | 162 | 0.883 | 0.12 | 1.000 | 0.000 | 0.000 |
| ifc_models/area/ifc | 268 | 0.007 | 0.99 | 1.000 | 0.000 | 0.000 |
| ifc_models/count | 101 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/count/ifc | 12 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/length | 14 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/volume | 29 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| swiss_dwellings/area | 606 | 0.794 | 0.21 | 1.000 | 0.000 | 0.000 |
| swiss_dwellings/count | 1289 | 1.000 | 0.00 | 1.000 | 0.000 |  |

| route | n | acc | abstain |
|---|---|---|---|
| none | 1 | 0.000 | 1.00 |
| std:exact:apartment_area | 156 | 1.000 | 0.00 |
| std:exact:apartment_area:needs_check | 36 | 0.000 | 1.00 |
| std:exact:doors | 104 | 1.000 | 0.00 |
| std:exact:floor_area | 15 | 1.000 | 0.00 |
| std:exact:floor_area:needs_check | 89 | 0.000 | 1.00 |
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
| std:exact:ifc:space_area_ifc_geometry:needs_check | 284 | 0.000 | 1.00 |
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
