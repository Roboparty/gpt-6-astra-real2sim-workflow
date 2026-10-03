# OURS delivery-area reconstruction — LIMITED technical candidate

Selected immutable model SHA256: `4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85`. The model remains remote at `models/v3/model.blend`; it is not included in this small archive. The selected editable scene contains801 visible mesh components,107 semantic entities,36 unchanged supplied cameras, and one recorded rigid model_from_input. No camera scale, per-frame pose correction, fused pointmap mesh, external stock mesh, heldout photo, laser geometry or GT depth was used by this author.

This is a scene-specific authored asset and an execution record, not a claim of a general automatic reconstruction algorithm. Custom construction includes full outer shell, internal partitions and columns, sliding-door components, pallet rack and sacks, wooden crates, two skips, two trailers, van and car, lumber cart, mesh cages, compactor, pipes and lighting. Unseen outer boundaries, backs and mechanical internals remain hypotheses.

## Native result at bundle time

The real Workflow.run/accept path completed ingest, preprocess, observation, identity, calibrated cameras, room calibration and model submission. build_geometry is `running` at 20261003T061557Z. Its actual v3 structural audit is FAILED: four unchanged source-endpoint gates and one undeclared intended tow/frame contact. The latter is retained as a contract failure; the diagnostic note is not a waiver. No native geometry-review pass has been asserted. Native material/light calibration, final visual acceptance, export/validate/report stages cannot be promoted past this gate. Assigned candidate PBR materials and lights are provisional, with their actual bindings and parameters included.

The exact remaining source endpoint failures are front skip median25.556/max41.010px; van median7.064/max33.556px; car median4.735/max27.566px; far cage median18.045/max30.598px. Frozen limits remain median9/max18px. Independent reviews selected v3 only for external MEASUREMENT as LIMITED; no independent physical accuracy result is available to this author.

## Checks and budget

Three authored full versions were created (maximum5). Fixed ten-view checks used30/50 budgeted pairs. One justified extra RGB pair reused the already-required native frame14 render to inspect windshield visibility (1/10 supplemental allowance). Exactly three full36-view input predicted-depth checks were run: initialv1, major-repairv2, finalv3. The final36-view domain has689349 pixels,99.9398% coverage and0.533454m missing-penalty MAE versus learned input depth; this is input consistency, not heldout/GT accuracy. All outcomes and input denominators are retained. A v2 checker attempt rejected fonts before rendering any views; identical text surfaces were realized and the retry was recorded.

CPU Blender4.5.3 with2 threads was used, with OMP/OPENBLAS set2 and R2S_CPU=1. Native-required diagnostic images are counted separately in native/native_cost_and_status_snapshot.json. v2 native build timed out after1500s with its failed audit,45 isolated/combined views,6 source crops and29 full-source renders retained. v3 uses384px diagnostic-only inspection views, unchanged full-source raster, and a2100s bounded executable timeout. This archive does not declare a running worker finished.

## Technical interchange boundary

Additional read-only technical export checks were run outside the blocked native acceptance path. Derived Blender reload PASSED. GLB strict reload FAILED camera FOV/shift preservation; USD strict reload FAILED32 stable-part identity checks. Those files are not certified interchange equivalents. The selected Blender model plus all36_cameras.json remain authoritative. Procedural Blender materials can flatten to simpler PBR approximations in GLB/USD. Mesh colliders and large model/export/audit files remain remote.

## Reproduction

Unpack this archive. With Blender4.5.3, run `blender -b --factory-startup --threads 2 --python replay_builder.py -- --root /new/empty/path`. The wrapper creates a NEW workspace, copies only camera/parameter/observation metadata and the exact native source snapshot, then executes the preserved final scene recipe and measured assembly declarations. It relocates the ROOT path only. It does not rerun source inference, use raw photos/depth, or grant native acceptance. Full protocol replay requires the original hash-pinned authorized inputs and actual agent stage reviews. The reconstructed .blend byte hash may differ due to embedded save paths/metadata; geometry identity must be checked separately if required.

The native framework is frozen atop coordinator base735be2f. Its exact SOURCE_FROZEN receipt and the five changed files camera.py,media.py,blender_structure.py,structure.py,stage_worker.py are included, along with the small full runtime source for portability. Later coordinator fixes were not used by this run.

The working v1 builder was overwritten before a separate source snapshot. Its source text was subsequently recovered by reversing this run's recorded edits and checking against the original creation record. No pre-run source hash exists, and a geometry replay proof was not completed; metadata/v1_source_recovery.json preserves this caveat. Original v1 model/GLB/check bytes were never overwritten. Final v3 source/parameters and selected model hashes are explicit.

No models, raw images/depth, inference weights,110MB structural audits, private chat or other-author material are included. Native state and cost records are timestamped snapshots; later completion/timeout belongs in a separately versioned final-state addendum.
