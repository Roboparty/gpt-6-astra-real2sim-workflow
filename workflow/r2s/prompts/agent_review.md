# Agent: source-constrained visual review and correction

Inspect the original image(s), source-camera render, semantic/clay render and interior diagnostic views. Check camera, silhouettes, occlusion order, object scale, contacts, self-intersections, textures and full shell/luminaires. Distinguish fitting appearance from reconstructing metric geometry. Do not use source-textured regions to claim independent photometric accuracy.

Deliver review.json containing concrete issues, severity, evidence pixel regions, proposed changes, uncertainty and pass/fail status. If any blocking issue remains, return changes_requested rather than complete. Request `r2s revise CASE agent_model --reason ...` for model changes or agent_calibrate for camera changes, then rerun affected stages; old attempts must remain intact. Review must not supply replacement model.blend or scene.json; revise the responsible stage and review its new executable renders.

Use the same evaluation protocol in A and B. A missing measured dimension has status unavailable, never zero error. Interior renders verify completion but cannot substitute for withheld real photographs. Do not claim unseen-view accuracy from one source image.

Return response.json with evidence and auditable conclusions.

For workflow_profile quality_v2, review.json must additionally have decision pass/revise, source_comparison, same_camera_comparison, and separate checks for geometry, materials, lighting, source_alignment and novel_view_completeness. Each check needs status and evidence. A major visible mismatch blocks acceptance even if another field calls it nonblocking. Technical integrity, visual likeness and real-world physical accuracy are separate verdicts.

Also deliver furniture_local_review with status, concrete findings, source_crop and render_crop referring to real artifacts. Recheck the accepted furniture structure under final shading: do not let material highlights, source-view occlusion or all-image brightness scores conceal disconnected/incorrect members. A model-version change invalidates the prior local review and requires new images.

When surface_contract_version >= 1, also follow surfaces.md; source-bound surface artifacts and front/raking review are mandatory.
