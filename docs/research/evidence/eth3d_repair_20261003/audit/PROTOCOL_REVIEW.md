# Repair protocol and collision fallback review

Verdict: protocol is suitable for the bounded repair experiment; the declared nonrectangular-room fallback guard passes independent entrypoint tests. Candidate geometry, textures, mesh collision and physical readiness remain unreviewed.

## Protocol

Reviewed `examples/eth3d_repair_20261003/protocol.json`, SHA-256 `f581833368a950ba345d4a931554ae2e5ac9b818356166a1704100d2a6c73bc9`.

The protocol preserves the original candidates and failures, restricts authors to the 36 mapping photographs and supplied camera/depth-reference inputs, separates geometry, texture and lighting interventions, and explicitly labels reused heldout evaluation as an exposed-test diagnostic. It does not authorize GT-based author selection or background substitution. No blocking design inconsistency was found.

Final implementation must provide the concrete source allowlist and texture support receipts described in `REVIEW_PREFLIGHT.md`; the protocol's prose alone is not executable proof of source isolation, occlusion support or successful repair.

## Actual exporter guard

`simulation.py` calls `require_canonical_room(S['room'])` at line 14, before the XML root is created at line 16 and before either the canonical shell loop or the custom-object AABB fallback. `shell_boxes()` also calls the guard directly.

The existing 24 helper negative cases and historical regression receipt were read. Its shell module and test hashes match the current source exactly. I did not repeat that suite. Instead I ran eight fresh subprocess tests of the actual `simulation.py` entrypoint with the existing installed MuJoCo runtime:

- Four independent declarations: `bounds_only=true`, `nonrectangular_topology=true`, `topology=orthogonal_union`, or `collision_policy=mesh_only`.
- Each declaration tested with both an empty entity audit and a renamed, noncanonical shell entity.
- All eight executions returned nonzero with the explicit rectangle-fallback rejection.
- None produced `scene.xml`, `collision_recipes.json`, `simulation_audit.json` or `probe_test.xml`.

This confirms that rejection does not depend on entering a named canonical-surface branch. The synthetic inputs and logs remain at `4090-1:/home/wqz/real2sim_agent_repair_20261003/reviewer_guard/`. Local evidence is `entrypoint_guard_result.json`; the independent test is `test_entrypoint_guard.py`.

Validated source hashes:

- `shell_collision.py`: `1f472556d70ca5052687b2198e42848fdf10a7a8e3d5fdc9e43a1b414d4b89e9`
- `simulation.py`: `c7ffe98662ea1643dda82e37a0d0e2d36c359da4cf370e8ac21ce2cd2f8a510e`
- Existing `test_shell_collision.py`: `44424164d273d2d75214792b5adfa8353d047f14a3e213d49b4135a67af00cf5`

## Required boundary at final review

This is declaration-based rejection, not automatic topology inference. A scene that omits all of these room declarations can still reach legacy rectangular/custom-AABB behavior. The geometry author has therefore been asked to preserve `scene.room.bounds_only=true` and `scene.room.collision_policy="mesh_only"` through every serialization/export step, with an explicit nonrectangular topology where available.

The current guard deliberately refuses unsupported native MJCF export; it does not add a nonrectangular mesh-collision implementation. Final receipts must distinguish independently validated mesh collision, native export refused/unsupported, and actual dynamics status. A deliberate refusal is not a simulation or physical-acceptance pass.

No model, author source, frozen result or main implementation was edited in this review. No commit was made. Final candidate review will occur when handed off, without repeated polling.
