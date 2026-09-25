# Visual refinement contract

Applies when packet.refinement exists. Read this alongside the stage prompt. The Agent must actually inspect images and author modelling changes; the executor cannot judge likeness from a JSON verdict.

## Observe and model

In observation.json declare appearance_targets: a nonempty list of {entity, source_crop_xyxy, features}. Coordinates are integers in the selected appearance_source image; include every observed furniture assembly and other visually important regions. appearance_source is a {path, sha256} selected from packet.comparison_inputs: the first original image is the default for image inputs; video must explicitly select an accepted decoded frame. The primary scene camera must correspond to this image. Other available source views still require the ordinary multi-view review. Record distinguishing silhouette, cross-section/taper, curvature, joins, upholstery volume, texture direction/scale and uncertainty as applicable. Do not invent hidden details. These priorities are fixed until an explicit observation revision.

Treat parametric templates as starting points. If their variables cannot express an observed feature, change the representation or locally rebuild it. Keep semantic ownership, joints and simple collision proxies while improving visible geometry. Preserve source-constrained layout. Materials need appropriate colour/roughness/normal detail and correctly scaled/directed texture, not a universal noise bump. No V5 scene assets may be imported into an independent reconstruction.

At overlapping furniture boundaries, identify which object owns each visible segment before fitting it. Record visible endpoints, curvature and occlusion intervals separately from support landmarks. A table stretcher crossing a chair in the image is not evidence for a long chair arm/back. Include these discriminating features in the object's review; positional landmark error alone cannot approve shape. If ownership remains ambiguous, compare plausible local constructions against the source crop and a diagnostic side view, retain uncertainty, and reject unsupported extensions. Preserve the neighbouring object's geometry while correcting the mistaken part. Record fitting residuals as fitting evidence, never as independent accuracy.

## Review every candidate, including rejected ones

Copy the executable render's relevant PNGs without editing them. Deliver appearance_review.json in response.artifacts:

```json
{
  "render_binding_sha256": "SHA256 of the upstream render_binding.json",
  "checks": {
    "source_similarity": {"status": "revise", "findings": "Specific source-view mismatch", "evidence": ["source_reference.png", "source_view.png"]},
    "local_detail": {"status": "revise", "findings": "Observed feature missing from current geometry", "evidence": ["priority_000_source.png", "priority_000_render.png"]},
    "novel_structure": {"status": "pass", "findings": "What was actually inspected; hidden surfaces remain hypotheses", "evidence": ["diagnostic_reverse.png"]}
  },
  "per_object": [{"entity": "object_id", "status": "revise", "findings": "Concrete local finding", "source_crop": "priority_000_source.png", "render_crop": "priority_000_render.png"}],
  "comparison": {"relation": "baseline", "findings": "First candidate; no improvement claim"}
}
```

All priority objects must appear exactly once. `complete` requires all three dimensions and all objects to pass, plus the existing stage-specific review/structure contracts. Never write a passing review merely to advance the runner. A local improvement does not certify the entire room or V5-level generalization.

Review stages must not deliver replacement model.blend/scene.json files. Any model change goes through the responsible upstream stage and a new actual render before approval, preventing an audited model from being replaced during export.

When a best candidate exists in packet.refinement.history[stage].best, comparison must contain against=best.review_sha256, protocol_sha256=current binding's protocol, relation=better|equivalent|worse, findings, and before/after lists referencing delivered image copies from the two candidates. Inspect those images under matched camera, raster and colour transform. Lighting/material parameters may differ because they are the subject of the correction; document them. A worse candidate cannot be completed. Archive references preserve the best model; do not silently restore it into current dependencies.

For `changes_requested`, response must include issues [{entity, defect, severity, evidence:[artifact names], responsible_stage}] and revision {stage, reason, strategy}. Route one responsible upstream stage at a time: camera→agent_calibrate; walls→agent_calibrate_room; shape→agent_model; surface→agent_materials; lighting→agent_calibrate_lighting. Keep other outstanding defects in appearance_review findings. Supply actual review evidence for failed candidates too. The runner calls revise and re-executes affected dependencies automatically, or emits an awaiting_agent packet for interactive execution.

Read packet.revision_request, including the prior review directory and best candidates. After two stagnant reviews change the modelling strategy, not only numerical values. Finite revision/stagnation/execution-time budgets persist across resumes; waiting for an interactive Agent is excluded from execution time. A resource stop remains needs_revision, with best references and unresolved findings. Budgets can be explicitly increased in case.json without discarding history. Camera/observation revisions archive the previous comparison series; the next candidate is a new baseline, not claimed improvement.

Final freeze requires every configured stage, including final visual/physics review and report, to be valid. Existing old cases without a refinement field retain their stage contracts; new initialized cases enable this contract.

When surface_contract_version >= 1, also follow surfaces.md; source-bound surface artifacts and front/raking review are mandatory.
