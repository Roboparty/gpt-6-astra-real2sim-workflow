# Reusable findings and boundaries

Research evidence first read at commit `dd51a20f8e7ced270df9cf1cfeeaf859d8dfe61a` on 2026-09-29; integration is based on its later committed continuation `37976c0ccccc1dac53744b73ae7c625dbdfec6e8`. These are existing project evidence, not new experiments run by the skill. Resolve the following source paths relative to the repository root.

| Recorded result | Reusable method | Boundary |
|---|---|---|
| Rear-wall discrepancy ~25 mm reproduced; structural shell then passed frozen 6 mm checks | Build collision from canonical wall/floor/ceiling surfaces and explicit openings | Internal transfer accuracy, not measured real-room geometry |
| Fixed-camera occlusion oracle: target 200 pixels, absent entity 0 | Keep all geometry as occluders, stable entity IDs, source hashes | Synthetic evaluator validation |
| Pose annotation transport reduced same-mesh joint failures 9/49 → 2/49 | Move anchors/3-D bindings with rigid pose, retain source UV | Fine shoe-cabinet landmark still 19.28097 px > 18 px; proposal not accepted |
| Uniform bedding color fit worsened larger ROI MAE 0.123208 → 0.123498 | Inspect frozen full region and other regions, not just fit-polygon error | Color candidate rejected; same-image ROI is not heldout |
| Static duvet Solidify offset -1 → +1 passed 49/49 joints and reduced bedding MAE 0.12294109 → 0.11988752 | Check evaluated shell direction and attachment surfaces | Single candidate/in-sample evidence; folds still approximate; not cloth dynamics |
| Export bound drift 0.00872278 m → 5.96e-8 m | Preserve modifier-bearing meshes before export and compare evaluated bounds | Authoring/export preservation, not real-world metric accuracy |
| Synthetic hinge/cloth/volumetric examples produced numerical motion | Explicit optional mechanisms with solver traces | Not blanket physical qualification of a reconstructed scene |

Source documents: `docs/research/STATE.json`, `PROTOCOL_20260929.md`, `RESULTS_20260929.md`, `UPDATE_20260929T0945.md`. Small JSON evidence under `docs/research/evidence/heartbeat_0945/` includes `duvet_shell_structure.json`, `duvet_shell_appearance.json`, `bedding_comparison.json`, `pose_annotation_mesh.json`, `export_preservation.json` and `export_preservation_first.json` (retained setup failure).

The original independent whole-scene verdict remains `needs_revision`. No shared held-out competitor benchmark or SOTA result is established. Do not copy a later unverified research update into this table without reading its runtime evidence.
