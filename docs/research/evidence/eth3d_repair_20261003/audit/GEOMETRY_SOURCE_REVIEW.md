# Geometry repair source review

Scope: read-only review of the initial `examples/eth3d_repair_20261003/geometry/repair_geometry.py` recipe, its topology/fit inputs, a minimal synthetic mesh reproduction and the frozen OURS v3 baseline. No author candidate or primary code was edited. This is not final-candidate acceptance; the author was actively correcting the source during review.

## Confirmed implementation problems

1. **Wall segments retain internal faces.** The recipe appends a closed box per boundary segment and then merges vertices. Merging vertices and recalculating normals does not compute a solid union. In Blender 4.5.3, the same recipe on two adjacent wall boxes retained two internal cap faces and two nonmanifold edges. The author accepted the finding and is replacing this with a coplanar u-z union extrusion. Final review must verify the revised mesh, including opening-height transitions and junctions; the proposed implementation is not yet accepted merely from its description.

2. **Wheel endpoint transport disagreed with actual mesh transport.** The original recipe transformed the wheel centre by the owner affine, but retained wheel shape through isotropic z-scale. It then transformed all landmarks and joints with the owner's anisotropic affine. With the actual supplied fit parameters and frozen v3 transforms, the resulting endpoint differences were 25.9 mm for `van_hub1_0`, 118.3 mm for `van_tyre-1_0`, and 87.1 mm for `car_tyre-1_0`. The author reports changing landmark transport to each bound object's `new_world_matrix @ inverse(old_world_matrix)`. This corrects the mathematical mismatch, but a shared joint must still be measured against both transformed physical parts; one transported point is not proof of maintained contact.

3. **Base identity needs an executable assertion.** The inspected recipe computed a hash of the named baseline file but did not check that Blender had actually opened that exact pinned model. The author was asked to assert the loaded path and hash before modifying the scene, so that baseline JSON and anchors cannot silently be paired with another loaded mesh.

## Checks without a new finding

The proposed new joint anchor `[6.55, 7.1, 0.39]` was read-only tested against the actual frozen v3 meshes. It lies inside `flatbed_frame` and on `flatbed_towA`; both native outside-distance values are zero. The frame's nearest-surface distance is 50 mm because the point is inside the solid, not because it is detached. The point is a valid shared anchor for those unchanged parts. Subsequent changes to either part require remeasurement and do not inherit this result automatically.

The floor/ceiling cell recipe omits side faces between adjacent occupied cells, unlike the defective per-segment wall-box recipe. A final whole-shell manifold/coverage check is still required; source inspection alone is not a topology pass.

## Coordinator findings retained

The coordinator separately identified the neutral-material override, render-bounce/light changes, global `hide_render=False`, absent garage aperture split coordinate and the declaration-only collision coverage receipt. Those are not treated as resolved here. Geometry-only renders must retain the comparison's appearance controls; aperture tests must use the intended continuous opening and actual occluders; collision coverage remains pending until measured.

## Evidence and communication

- `geometry_recipe_checks.json`: actual Blender reproduction and the baseline joint-anchor measurements.
- `wheel_transport_diagnostic.json`: exact old-affine versus actual-object endpoint discrepancies.
- Reproduction scripts and logs remain at `4090-1:/home/wqz/real2sim_agent_repair_20261003/reviewer_guard/`.

Findings and measured values were sent directly to the geometry author and coordinator. The author acknowledged the wall-union problem and reported the per-object landmark correction. No gate was relaxed, no unsupported completion was accepted, and no GT or heldout result was provided to the author.
