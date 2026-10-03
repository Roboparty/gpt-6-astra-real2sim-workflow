# Source-local refinement and regression contract

1. Freeze accepted source-image bytes, camera/projection settings, image color pipeline, fit/heldout roles, region denominator, baseline model and renderer version before editing. Bind candidate renders to that exact camera. Keep independent views sealed from fitting. Another region from the same photograph is an in-sample diagnostic, not heldout evidence.
2. Diagnose source differences with fixed crops/masks and overlays. Map each region to stable assembly/part IDs; inspect occlusion and source landmarks. Separate possible shape/pose, material and illumination explanations. A rectangular RGB error is not a semantic diagnosis or 3-D measurement.
3. Choose one intervention and write the reason, targeted source region and assumed parameters. Create a new candidate. For geometry/pose edits transport attachment anchors and 3-D landmark bindings consistently, retain source UV/tolerances, and invalidate old audits. For materials use private material copies. For lighting freeze materials/geometry/camera, change a declared light parameter, retain exposure/color management and compare the same views. The small edit helper intentionally supports geometry/material RoomKit changes only; a light experiment uses the established Blender authoring adapter on a copy.
4. Render baseline and candidate at the same fixed cameras. Re-run all regions, including worse/unknown/absent observations. Diagnose fit and heldout separately, retaining failures. Do not combine per-region best candidates into an untested scene.
5. Run source masks and evaluated 3-D landmarks, stable part ownership, declared joints/support, shell/opening collision checks and modifier/export preservation checks. A new `.blend` receipt is not a structural or collision pass. If the corresponding existing project adapter is unavailable, mark the gate unknown; do not silently skip it.
6. Promote only after the frozen source-fit, other-view and applicable structure/physics gates all pass. Report quality, runtime and uncertainty separately. Absence of independent views limits the conclusion to fitting diagnostics.

Diagnosis schema example (all hashes must be actual frozen bytes):

```json
{"schema":"real2sim-roi/1","views":[{"id":"front","role":"fit","source_camera_sha256":"actual_camera_hash","baseline_camera_sha256":"actual_camera_hash","candidate_camera_sha256":"actual_camera_hash","source":{"path":"source.png","sha256":"actual_source_hash"},"baseline":{"path":"base.png","sha256":"actual_base_hash"},"candidate":{"path":"candidate.png","sha256":"actual_candidate_hash"},"regions":[{"id":"bed","xyxy":[10,20,90,80],"part_ids":["duvet"]}]}]}
```

Camera hashes are declarations in this small adapter; bind them to the renderer's retained effective camera receipt before trusting a comparison. The script rejects different hashes, image dimensions, non-RGB images, missing or out-of-bounds regions; it does not estimate cameras or perform hidden alignment. Source images should be RGB sRGB under a declared color pipeline. Reported sRGB MAE is an image diagnostic, not a linear-light photometric loss.

Edit example:

```json
{"schema":"real2sim-part-change/1","scene_sha256":"actual_base_manifest_sha256","part_id":"duvet","mode":"geometry","source_region":"front/bed","reason":"assumed static fold correction from fixed source ROI","set":{"fold_amplitude":0.015}}
```

Existing read-only project entrypoints (inspect current source/version before use):

- `tools/evaluate_geometry_feedback.py --protocol frozen.json --candidate candidate.json --expected-protocol-sha256 REGISTERED_HASH --output new-feedback.json`. Its protocol digest is canonical JSON, not raw file SHA256; use the project's documented `r2s.contracts.digest`. Do not replace frozen hashes with newly computed candidate-dependent values.
- Blender `workflow/r2s/blender_geometry_feedback.py` exports occlusion-aware masks from a saved scene. Its documented adapter does not supply requested 3-D landmarks; retain missing-landmark failures.
- `tools/compare_collision_export.py` compares matched source exports and explicit openings; use immutable code and new output paths. Do not launch the whole active research suite just to use this skill.
- Detailed docs: `docs/GEOMETRY_FEEDBACK.md`, `docs/PHYSICAL_PRIORS.md`, `docs/TASK_EVALUATION.md`; exact checked reference files are recorded in the delivery report.

No duplicated physics/export evaluator is bundled. RoomKit provides geometry primitives, Pi3X provides reference contracts, and this skill provides the local-edit and regression workflow.
