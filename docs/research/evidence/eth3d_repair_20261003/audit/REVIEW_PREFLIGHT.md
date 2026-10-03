# Independent repair review preflight

Status: awaiting the repair protocol and final author receipts. This is a review checklist, not acceptance of an implementation.

Scope: read-only inspection of the new geometry and texture repair work. Previously frozen AWSM and OURS candidates remain unchanged. Authors receive no laser/depth evaluation results. The previously exposed heldout set is no longer an independent test; any later evaluation against it must be labelled an exposed-test diagnostic.

## Evidence required before the five-minute final review

- Base and candidate model SHA-256; source allowlist containing exactly the 36 mapping photographs and their byte hashes.
- Camera K/T, the single rigid gauge, original source UV/frame labels and unchanged acceptance thresholds. Geometry edits must update the corresponding mesh/anchor bindings without changing the image evidence.
- Stable semantic object/part inventory and evaluated geometry, transform and visibility fingerprints. Every added, removed or hidden object must be accounted for.
- Actual structure/contact/intersection receipts bound to the exact candidate. Preserve failed and unknown results; an author preparation report is not the native audit.
- For each texture: source frame/hash, source region, target object/material/UV mapping, generation recipe, output hash, and counts of supported and unsupported texels.
- Texture source support must include complete-scene first-hit or depth-consistency checks. FOV and normal-angle checks alone do not establish visibility.
- Fixed-view source/render pairs for the existing ten mapping views. Hold geometry, camera, lights, exposure and color settings fixed for the texture-only comparison. Record lighting-only changes separately.

## Critical false-improvement checks

1. Do not substitute source imagery through the world, camera background, compositor, render overlay or camera-facing billboard.
2. A projective texture must use a fixed source camera or stable surface mapping, not the current rendering camera. Projected source pixels must belong to the target surface rather than an intervening object.
3. Do not suppress incorrect geometry with collection/object hiding, alpha, holdout, ray-visibility changes or evaluation-exclusion flags. Render visibility and measurement visibility must remain traceable.
4. Photograph-derived color usually contains illumination. Label it photo-baked color when appropriate; do not claim recovered albedo or improved lighting from a confounded material/light change.
5. Filling an atlas, completing a shell or covering an unknown backside does not establish accuracy. Unsupported completion remains assumed or unknown.
6. Geometry changes invalidate old texture visibility supports and old structural/collision receipts. Preserve previous failed attempts and use a new candidate record.

## Review outcome

Report source-fit appearance, camera integrity, semantic coverage, texture provenance/occlusion support, structural state and light/material isolation separately. Use PASS, FAIL or UNKNOWN per gate. Final promotion requires the applicable gates to pass; a benchmark-measurable or visually improved candidate is not automatically a successfully repaired native workflow.

The initial remote check at 2026-10-03 06:47 UTC found that `/home/wqz/real2sim_agent_repair_20261003` had not yet been created, so no implementation-specific verdict was issued. Receipt requirements were sent to both authors through the existing coordination channel.
