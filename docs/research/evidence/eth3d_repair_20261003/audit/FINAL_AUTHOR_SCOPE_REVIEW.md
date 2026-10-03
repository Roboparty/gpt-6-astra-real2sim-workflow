# Frozen v4 author-scope review

Outcome: **LIMITED source-selected diagnostic candidate; native appearance acceptance remains rejected.**

Geometry: `506982c1c94a94067b19a58dc1a55d7b9ab6039ca1b8d00f61fba76292cc5542`.

Texture: `f36a6b79c439bf0fd53c2de58c84f4a42b4fddce29208d1fb0a273c1ba39bb2f`.

This review used the original 36 author inputs and frozen author artifacts only. It did not read new GT or previously heldout evaluation results, and did not modify a model.

## Implementation and provenance checks

The saved texture model has exactly the same mesh geometry, object transforms, cameras, lights, visibility, world, color and inspected render controls as the v4 geometry model. All original materials remain unchanged. Actual node/link/ColorRamp inspection verifies 24 new materials preserve the original fallback and non-BaseColor behavior and insert photographs only into Base Color. Photo alpha is a color-mix support factor; shader Alpha remains 1 and photo materials have zero emission strength. No background or compositor substitution was found.

Both actual image payloads are packed and match their external PNG hashes. They use sRGB RGB and CHANNEL_PACKED alpha. Named UV layers exist, and there are no linked-library dependencies.

All 36 source hashes and the actual decoded RGB cache match the allowed originals. Independent summation and inspection of all 1720 atlas tiles reproduce:

- 303 mapped objects and 738 supported surface polygons.
- 1,741,643 supported / 5,371,573 total surface texels: **32.4233%** support.
- 3,629,930 unknown texels retain the original fallback and are not claimed as observed reconstruction.
- Alpha values are 0/255; per-source assignment counts match the receipt.

Ninety-six deterministic supported-texel samples independently pass actual UV/atlas matching and full-scene first-hit support against their recorded source views. The maximum UV discrepancy is below 3e-8. This is a sampled support check, not a rerun of every baking ray or every DA3/color filter.

## Actual native material result

The stable per-node framework implementation was independently regression-tested, including actual Blender negatives and the corrected render-active implicit-UV case. The canonical audit was then independently rerun on the exact frozen texture model using its adapted per-node declarations.

The result is still **failed: 75 soft-world coordinate failures across 45 objects**. It exactly matches the author's preserved failure result. The inherited world-coordinate procedural fallback/bump on these soft objects is not waived, relabelled rigid or counted as a native appearance pass. A passing software test suite or narrow layered-binding audit does not change that outcome.

## Whole-source visual findings

All ten fixed source/geometry/texture triptychs were independently inspected. The photo layer adds wood, concrete, door and sack detail. The rejected giant-pipe obstruction is gone in inputs 20/24/28/32/35.

The result remains limited: A70 signage is visibly duplicated in inputs 24/28; door edges and support boundaries show seams or double contours; vehicle shape/color and the dark-blue service region in input12 remain imperfect. Thin real features are not always aligned with their existing reconstructed parts. These failures cannot be dismissed because texture pixels have candidate-BVH support.

Source-photo illumination, shadows and reflections are baked into color; this is captured appearance, not recovered intrinsic albedo. No arbitrary exposure or light adjustment was introduced to compensate. Texture and lighting effects remain separate.

## Selection and completion boundary

Geometry v4 is retained as the author's source-selected LIMITED candidate, with its complete 36-view DA3 regression and coverage losses recorded separately. Five source-landmark external occlusions remain unresolved relative to the original baseline; they are not silently waived. Full native Workflow completion, nonrectangular dynamics and delivery acceptance are not certified by this review.

The old rejected geometry/texture versions, original comparison freezes and failures remain preserved. Any later reuse of exposed evaluation data must be labelled exposed-test diagnostic and must not drive author revisions.

Detailed evidence: `final_author_scope_review.json`, `final_texture_v4_independent_nodes.json`, `final_texture_v4_source_counts_review.json`, `final_texture_v4_sample_support_review.json`, and `texture_v4_native_recheck_result.json`.
