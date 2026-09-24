# Agent: geometry acceptance independent of materials

Compare the authorized original with same-camera clay/ID renders and silhouette/edge overlays, then inspect all four walls and reverse views. Diagnose camera error separately from shape error. A low residual on camera fit landmarks cannot validate every object. Review each major object's contour, pose, thickness, cushion shape, nesting, support and occlusion. Do not accept uniformly inflated primitives as finished upholstery.

Deliver geometry_review.json with decision pass/revise, checks for camera, room_surfaces, silhouettes, occlusion and support (each has status and evidence), per_object findings, issues with severity, and geometry_freeze_sha256. Any visible major mismatch remains blocking. Do not reclassify visible shape errors as uncertainty about invisible geometry. If revising, return changes_requested and invalidate agent_calibrate, agent_calibrate_room or agent_model as appropriate.

After acceptance, lock camera, architecture and object layout for material/light calibration. Preserve editable geometry; never replace it with a projected full-room image.

## Enforced structure review

Use build_geometry's model_binding.json and structural_audit.json. A failed mesh audit blocks acceptance; repair the model or correct a demonstrably wrong constraint with evidence and a new revision. The audit uses evaluated visible meshes, not dynamics proxies. Inspect each furniture alone from front/rear/side, the combined assembly from several angles, and the original furniture crop against the source-camera crop. Separate intended joinery/contact, photographic occlusion and unintended penetration. Explicitly inspect feet, rear-post ownership, crossbar endpoints, upholstery support, symmetric/parallel structure and load paths.

geometry_review.json must cover every current scene entity exactly once in per_object, each with entity, status (pass or hypothesized), concrete findings and actual delivered evidence filenames; hypotheses need uncertainty. geometry_freeze_sha256 must equal the current model_binding model hash and model_version must match. Deliver all referenced image/audit files. Empty captions, stale model hashes, missing objects or missing evidence files are rejected. Brightness ROI scores, camera-only landmark residuals, exporter success and a stable simulation cannot substitute for this review. Keep any major local defect blocking, even if the global image looks acceptable.
