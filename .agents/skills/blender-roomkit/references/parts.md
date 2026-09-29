# Part contract and recipes

See executable [example](../assets/room.json). Coordinates: Blender right-handed Z-up, metres, XYZ Euler radians; position is part center. Sizes are pre-modifier dimensions except folded-sheet Z, which is thickness. Folds extend the evaluated bounds. Colors are linear RGB values for Principled BSDF; source sRGB pixels need conversion before albedo fitting.

Required top level: `schema: roomkit/1`, `units: m`, nonempty `parts`. Each part has unique `id`, `assembly`, `kind`, positive `size[3]`, `position[3]`, `rotation[3]`, `prior_status: assumed`, human-readable `prior_source`, and `collision: box|none`. IDs begin with an ASCII letter, contain only letters/digits/underscore/hyphen, have at most 48 characters, and exclude the reserved `__collision` substring. Optional `color[3]`, `roughness` in [0,1], `fold_amplitude` in [0,0.25] metres. `dynamics` defaults off; true values are rejected by this static implementation.

Dimension selection order: supplied measurements with their uncertainty; manufacturer specification for the matching model; sourced category range; then explicitly declared scene-specific assumption. The current backend intentionally marks even authored dimensions as assumed: preserve actual measurements in the external source ledger and avoid claiming they were independently recovered. Do not infer a universal room scale from a generic bed size.

| Target | Editable decomposition | Boundary |
|---|---|---|
| Room | floor slab and separate wall strips around each opening | Never one solid room-sized collision cube. Doorways remain empty. Native Real2Sim requires all six shell surfaces; standalone part fixtures may omit the ceiling |
| Cabinet | sides, back, shelves, doors, toe kick/feet | AABBs only for each solid piece; no cavity-filling union |
| Bed | frame, legs, mattress cushion, folded-sheet cover, pillow cushions | Static analytic folds; visual plausibility needs source-view review |
| Upholstery | cushion primitive with bevel, separately editable seams as thin components | No recovered weave, seam or material parameters |
| Toy | several ellipsoids/boxes with separate IDs | Approximate blocking model, not detailed character reconstruction |
| Shoe | sole box/cushion, upper ellipsoid, tongue cushion, heel part | Keep pair instances and fine details separate; box collision often too coarse |

The included scene exercises every supported recipe. It is a synthetic fixture, not a reconstructed room. Attachments/joints are not inferred. For articulation or deformation use the existing Real2Sim engine's explicit mechanisms and runtime audits.
