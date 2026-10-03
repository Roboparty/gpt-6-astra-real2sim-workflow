# OURS geometry repair: source-selected LIMITED candidate

Authoritative model remains remote:
`/home/wqz/real2sim_agent_repair_20261003/geometry/candidate_v4/model.blend`

SHA256: `506982c1c94a94067b19a58dc1a55d7b9ab6039ca1b8d00f61fba76292cc5542`.

The actual nonrectangular shell replaces the old 2008.5 m² rectangle with an approximately 940.13 m² union of the main hall, storage bay, corridor, cage interiors and entrance recess. Source-supported boundaries and uncertain completions are recorded in `evidence/topology_plan.json`. All six shell meshes passed closedness, winding, duplicate-face, boundary-ray and floor-union checks. Explicit static shell box partitions are supplied; native canonical-rectangle simulation is **unsupported/refused**, not silently regenerated.

The repair preserves the 36 cameras, single gauge, original source UV/frame/part labels, 9/18 px thresholds, existing material bindings, lights, exposure and retained-object visibility. Evaluated-vertex transforms preserve shear instead of relying on object TRS decomposition. The front skip uses two source8/source9 rim triangulations; its support uses only visible source8 learned depth plus a floor-contact assumption. Failed secondary-view support tracking remains in evidence.

All four formerly failing landmark groups and measured contact declarations now pass the actual full native numerical structure audit. The full `Workflow.run` build completed 36 source views, 6 source crops, 45 isolated/combined views, a clay view, two overall views and four wall views. Actual `Workflow.accept` recorded **geometry review = changes_requested**: coarse source12 vehicle geometry, source-depth tradeoffs and unresolved/inherited visibility limitations were not erased. Downstream native material/light/final review/export/validate/report were not promoted. The texture work is a separate material-only candidate, not part of this geometry-only model.

The fixed ten source/render views were inspected after correcting the three oversized rotated pipes. On all 36 allowed input views, reference domain remains 689349 pixels: conditional macro AbsRel improves 7.7734% → 6.6611% (30 better, 6 worse), while missing predictions increase 415 → 1120. Including the 30 m missing penalty, macro MAE improves 0.53355 → 0.50562 m (22 better, 14 worse). Source12 is the largest conditional regression. These are **input learned-depth consistency**, not GT accuracy. No GT feedback was used to choose or modify this candidate.

## Replaying the geometry recipe

Requires the exact frozen baseline model, its metadata/input packet and shared DA3 reference under `BASE`, plus Blender 4.5.3. Large inputs/models are intentionally absent from this directory.

```sh
blender -b BASE/models/v3/model.blend --threads 2 \
  --python run_geometry_repair.py -- \
  --baseline-root BASE --repair-root NEW_ROOT --output-name replay_v4
```

The wrapper relocates filesystem paths and a new output name only. It keeps the strict baseline SHA pin:
`4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85`.
It refuses an existing output directory. A baseline rebuilt from source may have a different binary SHA because Blender saves paths/metadata; such a file does not automatically satisfy the pin. Rebuilt output geometry/control identity needs separate evaluated-mesh verification. Wrapper syntax/dependencies were checked; a new replay was not executed after final freeze.

`repair_geometry.py` is the final exact recipe. `run_native_repair_executed.py` records the actual staged workflow used in this run; it contains historical task paths and is not an automatic acceptance recipe for another dataset. The `runtime_changes` directory contains the two fail-closed nonrectangular collision guards, not permission to claim a new physics backend works. Full actual geometry-runtime hashes are included in evidence; the separately developed material-coordinate extension was not used by this geometry worker.

## Failures, revisions and provenance

All rejected model/JSON/audit versions stay remote. The neutral/visibility-changing and segmented-wall drafts were rejected. Geometry v1 lost affine shear; v2 retained two failures; v3 passed numeric gates but had a rotated-cylinder dimensions bug, expanding three 0.11 m radial spans to 18.75 m and hiding source objects. v4 fixes the actual world-axis geometry rather than hiding it or baking over it.

`attempt_sources/repair_v3_rejected.py` is the retained v3 recipe. The v1/v2 recipes are **post-hoc recovered** by reversing this run's recorded edits; their receipts explicitly state that no contemporaneous source hash or binary/geometry replay proof exists. Their frozen models, JSON and failure reports remain authoritative. Do not present the recovered hashes as historical pre-run hashes.

The initial 30-minute planning estimate was exceeded. `ITERATION_LEDGER.json` records actual elapsed time, all construction attempts, three direct NO_RENDER diagnostics, two actual full native build rounds and common source checks. Repair native rendering used an explicitly authorized 8 CPU threads; common input checks remained at 2. No GPU or other-user process changes were made. Large raw audits and models remain remote.

The after-reload receipt provides actual stable evaluated-mesh hashes. It supersedes pre-save candidate hashes only for verification; old receipts are retained. All final raw model bytes remain unchanged after selection.
