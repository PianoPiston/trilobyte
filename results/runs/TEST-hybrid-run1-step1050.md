# Run TEST-hybrid-run1-step1050

- date: 2026-11-14T02:45
- method: router model: run1-step1050 prompt: ft max_pixels: 2000000 min_pixels: 0
- items: 6428 (test) wall: 291s concurrency: 64
- tokens/q in 602 out 10; latency p50 1.7s p90 4.7s
- cost per 1k questions: €0.021
- ALL: acc 0.811 | macro-by-cell 0.655 | abstain 0.015 | precision 0.823 | false-confident(>= 0.8) 0.023 | errors 0

| cell | n | acc | abstain | precision | false-conf | median rel err |
|---|---|---|---|---|---|---|
| cubicasa5k/count | 4305 | 0.786 | 0.00 | 0.786 | 0.019 |  |
| ifc_bench/text | 98 | 0.000 | 1.00 | 0.000 | 0.000 |  |
| ifc_models/area | 52 | 0.827 | 0.00 | 0.827 | 0.173 | 0.002 |
| ifc_models/count | 29 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/count/ifc | 5 | 1.000 | 0.00 | 1.000 | 0.000 |  |
| ifc_models/length | 6 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| ifc_models/volume | 12 | 1.000 | 0.00 | 1.000 | 0.000 | 0.000 |
| opening_design/area | 9 | 0.111 | 0.00 | 0.111 | 0.111 | 0.910 |
| opening_design/count | 22 | 0.273 | 0.00 | 0.273 | 0.000 |  |
| opening_design/text | 13 | 0.000 | 0.00 | 0.000 | 0.000 |  |
| swiss_dwellings/area | 599 | 0.955 | 0.00 | 0.955 | 0.035 | 0.000 |
| swiss_dwellings/count | 1278 | 0.903 | 0.00 | 0.903 | 0.029 |  |

| route | n | acc | abstain |
|---|---|---|---|
| dxf:apartment_area | 187 | 0.898 | 0.00 |
| dxf:door_frames | 104 | 1.000 | 0.00 |
| dxf:floor_area | 104 | 0.981 | 0.00 |
| dxf:label_area | 99 | 1.000 | 0.00 |
| dxf:room_area | 203 | 1.000 | 0.00 |
| dxf:rooms_labelled | 637 | 0.983 | 0.00 |
| dxf:units | 104 | 1.000 | 0.00 |
| dxf:windows/3 | 104 | 1.000 | 0.00 |
| ifc:IfcSlab_net_volume | 5 | 1.000 | 0.00 |
| ifc:IfcWall_net_volume | 7 | 1.000 | 0.00 |
| ifc:count_IfcBeam | 1 | 1.000 | 0.00 |
| ifc:count_IfcColumn | 5 | 1.000 | 0.00 |
| ifc:count_IfcDoor | 6 | 1.000 | 0.00 |
| ifc:count_IfcLightFixture | 1 | 1.000 | 0.00 |
| ifc:count_IfcSanitaryTerminal | 3 | 1.000 | 0.00 |
| ifc:count_IfcSpace | 8 | 1.000 | 0.00 |
| ifc:count_IfcStair | 5 | 1.000 | 0.00 |
| ifc:count_IfcWall | 2 | 1.000 | 0.00 |
| ifc:count_IfcWindow | 3 | 1.000 | 0.00 |
| ifc:space_net_area | 45 | 0.800 | 0.00 |
| ifc:spaces_total_area | 1 | 1.000 | 0.00 |
| ifc:wall_length | 6 | 1.000 | 0.00 |
| ifc:wall_net_side_area | 6 | 1.000 | 0.00 |
| vlm | 4782 | 0.754 | 0.02 |
