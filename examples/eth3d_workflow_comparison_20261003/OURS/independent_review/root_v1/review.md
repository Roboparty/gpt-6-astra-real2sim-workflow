OURS v1 independent review — needs_revision / LIMITED

Exactly10 matched mapping-photo/render pairs at indices0,4,8,12,16,20,24,28,32,35, own current v1 component inventory, own36camera metadata, own visible mesh occlusion audit. No heldout images, laser/depth truth, prior pilots or comparator scores. Same scope and five-fix cap for each method.

Camera contract: PASS. 36 frame identities preserved; input K unchanged; poses match one declared rigid model_from_input. Do not adjust cameras to hide geometry residuals.

1. Expose the windshield surface outside the cab solid (P1; frames [12]; parts van_windshield, van_cab_body)
Frame12 DSC_0690 has a clearly dark glazed windshield; the render presents a white closed cab slope. Both windshield triangle-centre rays hit van_cab_body first,61.5mm and87.2mm before their target. This verifies the author note about glass occlusion.
Action: Cut/rebuild the cab front surface and place the glass on the actual sloped outer surface; retain a distinct frame and recheck first-hit visibility from frame12 and an additional own mapping view. Do not merely darken the existing buried plane.
Evidence: pairs_1.jpg, camera_occlusion_audit.json

2. Restore the recessed separation of the two foreground supports (P1; frames [16, 12]; parts column_1_lower, column_2_lower)
Frame16 DSC_0695 shows two distinct adjacent hazard-striped support faces with a recessed vertical separation and separate floor contacts. The model reads as a fused broad mass. The two lower meshes project to x172.8–298.3 and120.9–209.4 at640px width: their horizontal intervals overlap36.6px. This supports a separation/shape problem, not a blanket instruction to shrink one whole column.
Action: Refit the two column cross-sections and relative placement against their separate source boundaries, keeping their support feet and recessed join legible in frame16; regress the vehicle/column occlusion in frame12.
Evidence: pairs_1.jpg, pairs_2.jpg, camera_occlusion_audit.json

3. Replace regular disk-like sacks with the observed bulk-bag topology (P2; frames [8, 4]; parts storage_rack, rack_sack_*)
Frame8 DSC_0685 shows irregular filled sacks, folds/ties, stacked volume variation and uneven gaps on the shelf. The render has repeated near-identical circular/rounded units in straight rows, with much more uniform spacing and shelf occupancy. The regularity issue is directly visible, not inferred from the component count.
Action: Fit bag count, silhouettes, uneven stacking and free gaps per shelf from frame8 plus the nearby mapping photos; keep shelf beams exposed where the source exposes them. Preserve the current shelf layout while revising bag components.
Evidence: pairs_0.jpg, pairs_1.jpg

4. Recover the compactor silhouette at the corridor entrance (P2; frames [20, 32, 35]; parts compactor_body, compactor_hopper, compactor_yellow_front)
In frames20/32/35 the source has a substantial gray upper hopper/cage and a lower yellow mechanism with protrusions; the render reduces this to a clean rectangular gray/yellow stack. The source machine occupies more vertically articulated silhouette and interrupts the corridor wall/floor junction differently.
Action: Use those three fixed views to recover the sloping/open upper hopper, lower mechanism/support outline and visible protrusions. Treat hidden internal structure as unresolved; do not add an arbitrary box to match overall depth alone.
Evidence: pairs_2.jpg, pairs_4.jpg

5. Fit fluorescent fixtures to their observed line orientation and spacing (P2; frames [20, 32, 35]; parts corridor_luminaire_*, luminaire_*)
The source corridor views show long transverse bright strips spanning across the image with a receding central sequence. The render instead shows prominent strips directed along receding diagonals and a different near-field arrangement. This changes broad ceiling evidence even though fixtures exist semantically.
Action: Fit long-axis direction and endpoints of the visible near/middle fixtures from frames20/32/35 before repeating them down the corridor. Verify projected fixture endpoints and preserve actual dark gaps; avoid compensating with ceiling brightness.
Evidence: pairs_2.jpg, pairs_4.jpg

Source/render comparison and two triangle-centre windshield rays establish only the listed visual/occlusion findings; not exhaustive collision or dimensional certification. Semantic parts being present does not prove their visibility or likeness.
