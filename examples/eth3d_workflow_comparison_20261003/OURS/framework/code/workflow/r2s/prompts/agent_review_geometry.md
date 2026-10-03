# Agent: geometry acceptance independent of materials

Compare the authorized original with same-camera clay/ID renders and silhouette/edge overlays, then inspect all four walls and reverse views. Diagnose camera error separately from shape error. A low residual on camera fit landmarks cannot validate every object. Review each major object's contour, pose, thickness, cushion shape, nesting, support and occlusion. Do not accept uniformly inflated primitives as finished upholstery.

Deliver geometry_review.json with decision pass/revise, checks for camera, room_surfaces, silhouettes, occlusion and support (each has status and evidence), per_object findings, issues with severity, and geometry_freeze_sha256. Any visible major mismatch remains blocking. Do not reclassify visible shape errors as uncertainty about invisible geometry. If revising, return changes_requested and invalidate agent_calibrate, agent_calibrate_room or agent_model as appropriate.

After acceptance, lock camera, architecture and object layout for material/light calibration. Preserve editable geometry; never replace it with a projected full-room image.

## Enforced structure review

Use build_geometry's model_binding.json and structural_audit.json. A failed mesh audit blocks acceptance; repair the model or correct a demonstrably wrong constraint with evidence and a new revision. The audit uses evaluated visible meshes, not dynamics proxies. Inspect each furniture alone from front/rear/side, the combined assembly from several angles, and the original furniture crop against the source-camera crop. Separate intended joinery/contact, photographic occlusion and unintended penetration. Explicitly inspect feet, rear-post ownership, crossbar endpoints, upholstery support, symmetric/parallel structure and load paths.

geometry_review.json must cover every current scene entity exactly once in per_object, each with entity, status (pass or hypothesized), concrete findings and actual delivered evidence filenames; hypotheses need uncertainty. geometry_freeze_sha256 must equal the current model_binding model hash and model_version must match. Deliver all referenced image/audit files. Empty captions, stale model hashes, missing objects or missing evidence files are rejected. Brightness ROI scores, camera-only landmark residuals, exporter success and a stable simulation cannot substitute for this review. Keep any major local defect blocking, even if the global image looks acceptable.

When surface_contract_version >= 1, also follow surfaces.md; source-bound surface artifacts and front/raking review are mandatory.

When appearance_contract_version >= 1, also follow appearance.md. Whole-scene coverage, scoped textures, actual UV/material checks and persistent fixed-view comparisons are mandatory.
# Optional numerical feedback

When the build includes geometry_feedback/report.json, inspect every failed row
and the green-source/magenta-candidate overlays. Missing observations remain failures.
These are fixed-camera fitting diagnostics, not held-out or 3-D accuracy. Request
a responsible-stage revision for geometric defects; do not mark a failed metric as
passed just because rendering succeeded. Existing support, structure and complete
room checks still apply. Unseen-view evaluation must stay outside this agent packet.
# Generation skills integration

If local_geometry_feedback is present, inspect its part-mapped ROI report alongside the original source, other views and executable structural audit. Do not ignore worse regions or approve from MAE alone. Request one responsible upstream correction through the existing revision mechanism; the dependency graph reruns generation and local feedback.
