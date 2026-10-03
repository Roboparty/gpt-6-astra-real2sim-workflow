# Geometry repair v2: structure acceptance rejected

Model SHA-256: `569fe2adbfe1f596bf6ec00d7ab736907f09d821f55933a05d19e7a5450182b4`.

Reviewed scene SHA-256: `15e679959e0de6aa99901bff952d82dab9bfb3770daf8c190f2538a5f60bc57a`.

This report preserves the reviewed v2 state. It does not accept a later contact-anchor proposal or another scene file implicitly.

## Independently verified repairs

- All six evaluated shell meshes are closed manifold, consistently wound, positive-volume and free of duplicate faces. Thirty floor-union cell checks and 133 garage aperture/header rays pass against the declared plan.
- The room retains the required bounds-only/nonrectangular/mesh-only flags. Native rectangular simulation remains unsupported/refused, not passed.
- Camera metadata, rigid gauge, all 38 source labels and thresholds are unchanged. Inspected material assignments/nodes, lighting, world/render/color settings, visibility and collection settings match the frozen baseline.
- The actual evaluated vertices of 148 deformed parts match their declared world transport within 2.071 micrometres, with modifiers baked. The previous approximately 96/72 mm binding errors are repaired: the two relevant landmarks now have below 0.3 micrometre transport discrepancy and zero/sub-micrometre nearest-surface distance.
- All 38 landmark bindings pass the original surface-distance criterion. A single tail-light polygon was tessellated differently, but its polygon loops are unchanged and 108 triangle-centre checks differ by at most 1.068 micrometres. This is not a new shape or binding failure.

## Remaining rejection grounds

The direct native diagnostic is **not** an accepted Workflow stage. It reports two failures bound to this exact model and scene:

1. `lime_skip_0` source-fit median is **10.27865 px**, above the unchanged **9 px** median gate; maximum 17.44328 px remains below 18 px. The failed median is retained.
2. The declared `van_cab_body` / `van_windshield` joint anchor has outside distances **[0.57869846 m, 0]** against a **0.01 m** tolerance. Independent inspection of all 5706 declared joints reproduces this single connection failure. A replacement anchor on actual shared geometry needs a separately preserved proposal and verification; it is not accepted by this report.

Additionally, 19 author-recorded candidate vertex hashes do not match the evaluated hashes after reloading the frozen file. All baseline hashes match, and actual geometry errors are microscopic, consistent with serialization/transform rounding rather than the previous deformation bug. The author was asked to append an after-reload receipt and preserve the original one; the mismatch is not silently erased.

## Texture boundary

The texture version that rebuilt material trees is diagnostic only. Final texture review must inspect actual shader links and node inputs, not just the receipt: only Base Color may change, with the original fallback, Normal/Bump, roughness, metallic, displacement, alpha, emission, lighting and visibility behavior retained as applicable. Texture visibility support must be recomputed for the final stable geometry hash.

Evidence: `geometry_v2_control_shell_review.json`, `geometry_v2_actual_mesh_review.json`, `tail_light_tessellation_review.json`. Model bytes were not changed by the reviewer. No GT or previously heldout result was provided to either author.
