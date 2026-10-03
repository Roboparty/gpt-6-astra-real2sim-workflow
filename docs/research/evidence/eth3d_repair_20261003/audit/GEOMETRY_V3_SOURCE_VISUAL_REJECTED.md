# Geometry repair v3 and its texture diagnostic: rejected on source visibility

Geometry SHA-256: `c288f8bb9688defd71f2faeb8dfddfefdeac2c56b714187dde0c2a3125d771b4`.

Texture diagnostic SHA-256: `b9e1abb33fb4ab050478c3038127a1cfe755e861ed4b8373d47c0434b8ac2f34`.

## Overall outcome

Neither candidate is promoted. The fixed source-view triptych was independently inspected. In inputs 24/28 the lumber cart and cages disappear behind an apparent gray wall; in 20/32/35 much of the cage region is similarly hidden. These are source-image regressions even though the local projection/contact checks pass.

The initial visual description of a new wall was only a hypothesis. Full-scene ray tracing identifies **ceiling_pipe2** as the first-hit blocker for all four lumber-cart landmarks, five cage0/1 landmarks and both cage2 landmarks. The actual cause is a rotated-cylinder dimension error:

- Baseline world extents of each `ceiling_pipe0/1/2`: approximately **29 × 0.11 × 0.11 m**.
- Repair v3 world extents: approximately **29 × 0.11 × 18.75 m**.
- World Z bounds changed from approximately **[4.185, 4.295] m** to **[-5.135, 13.615] m**.
- Setting object-local `dimensions.x = 18.75` enlarged a radial dimension by approximately 170.45 times; it did not shorten the world-X pipe length.

The author and coordinator were informed before further shell edits. Repair must correct the actual pipe endpoints/radial dimensions, not hide the pipe, change alpha, or cut otherwise correct shell geometry.

## What passed, and why it was insufficient

The six shell meshes remain manifold, consistently wound, positive-volume and duplicate-free. Thirty planned floor cells and 133 garage rays pass. Camera metadata, gauge, 38 source labels and thresholds, materials, lights and visibility controls remain unchanged. The 141 parts retaining affine correspondence match evaluated geometry within 2.071 micrometres. All 38 surface bindings, 5706 declared joints and 14 local source-fit groups pass the independently checked static criteria.

Those criteria did not require the fitted point to be visible through the **complete scene**. A projected point can satisfy a pixel threshold while another object blocks it. This case demonstrates why whole-source-view and full-scene first-hit checks are separate gates.

Of 38 source landmarks, 15 have an external first-hit blocker. Eleven are the giant-pipe regression above. The other four involve columns or a loading platform; their inherited-versus-new status and annotation-binding meaning remain unresolved and must not be silently declared fixed with the pipes. No camera-inside candidate was found by the performed AABB/oriented-surface screen.

## Source rebuilding evidence remains scoped

The two rebuilt front-bin rim points reproduce the declared input8/input9 reprojection sums of 0.461804 and 0.259573 px. The foot remains based on input8 learned depth plus a ground-contact assumption; failed input9 tracking is explicitly not multiview validation. These checks do not turn unknown cage depth, hidden corner returns or the uncertain corridor terminus into surveyed geometry.

## Texture implementation result, not appearance acceptance

Independent inspection of the saved texture diagnostic verifies unchanged geometry, cameras, lights, world/render controls and visibility; all original materials remain unchanged. The 24 new materials preserve original node/link/ColorRamp properties and fallback paths, and insert photo color only into Base Color. Photo alpha controls a color mix, not transparency. The two actual packed PNG payloads match their recorded hashes, use sRGB/CHANNEL_PACKED, have valid named UV bindings and no linked-library dependency.

All 36 source hashes and all 1720 atlas-tile support counts were independently checked. Supported/total surface texels are **1,512,693 / 5,371,573**; unknown texels remain **3,858,880**. Alpha values are 0/255 and per-source assignment totals match the receipt. This does not independently rerun all 4.5 million visibility rays or prove every baked color sample. The original canonical appearance audit remains failed; narrow node-binding success is not native appearance acceptance.

The texture diagnostic inherits the rejected geometry's obstruction and therefore is not a successful final visual repair. Original v1/v2/v3 failures, models and evaluation outputs remain preserved. No GT or previously heldout result was sent to an author.

Evidence: `geometry_v3_source_visibility_rejection.json`, `pipe_dimension_regression.json`, the three `geometry_v3_*review.json` files, `final_texture_independent_nodes.json` and `final_texture_source_counts_review.json`.
