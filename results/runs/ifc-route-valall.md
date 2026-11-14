# Run ifc-route-valall

- date: 2026-11-14T01:06
- method: ifc model: None prompt: zs max_pixels: 2000000
- items: 586 (val-ifc-all) wall: 29s concurrency: 4
- tokens/q in 0 out 0; latency p50 0.2s p90 0.3s
- cost per 1k questions: €0.001
- ALL: acc 0.993 | macro-by-cell 0.994 | abstain 0.002 | precision 0.995 | false-confident(>= 0.8) 0.005 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| ifc_models/area | 162 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/area/ifc | 268 | 0.996 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/count | 101 | 0.970 | 0.00 | 0.970 | 0.030 |  |
| ifc_models/count/ifc | 12 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/length | 14 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/volume | 29 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |

| route | n | acc | abstain |
|---|---|---|---|
| ifc | 1 | 0.000 | 1.00 |
| ifc:IfcSlab_net_volume | 15 | 1.000 | 0.00 |
| ifc:IfcWall_net_volume | 14 | 1.000 | 0.00 |
| ifc:count_IfcBeam | 3 | 1.000 | 0.00 |
| ifc:count_IfcColumn | 10 | 1.000 | 0.00 |
| ifc:count_IfcDoor | 22 | 1.000 | 0.00 |
| ifc:count_IfcSanitaryTerminal | 1 | 1.000 | 0.00 |
| ifc:count_IfcSpace | 23 | 1.000 | 0.00 |
| ifc:count_IfcStair | 14 | 0.786 | 0.00 |
| ifc:count_IfcWall | 22 | 1.000 | 0.00 |
| ifc:count_IfcWindow | 18 | 1.000 | 0.00 |
| ifc:space_geom_area | 284 | 1.000 | 0.00 |
| ifc:space_net_area | 118 | 1.000 | 0.00 |
| ifc:spaces_total_area | 13 | 1.000 | 0.00 |
| ifc:wall_length | 14 | 1.000 | 0.00 |
| ifc:wall_net_side_area | 14 | 1.000 | 0.00 |
