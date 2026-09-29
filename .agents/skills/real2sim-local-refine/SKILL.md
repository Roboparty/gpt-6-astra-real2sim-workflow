---
name: real2sim-local-refine
description: Diagnose frozen source-image region differences, map them to editable scene parts, make isolated geometry or material edits, and require other-view plus structural and collision regressions. Use for evidence-bound Real2Sim refinement; not automatic acceptance, SOTA claims or model training.
---

# Real2Sim local refinement

Use [the refinement protocol](references/workflow.md) for source-region diagnosis → corresponding part change → other-view/structure/collision regression. This is an orchestration skill and small adapter around existing methods, not a new reconstruction model; it does not alter GPT-6 weights.

Native integration: `local_geometry_feedback` runs after `build_geometry`, and `local_appearance_feedback` after `build_render`. Both execute this skill's diagnosis on actual source renders and deliver part-mapped reports to the existing review gates. `agent_calibrate_room` freezes `local_protocol.json` before modeling, unless an external frozen protocol is already configured. Existing `revise`/refinement routing invalidates and reruns affected render, local-feedback and downstream gates. See [generation flow](../../../docs/GENERATION_SKILLS.md).

Read [verified methods and limitations](references/evidence.md) when selecting a mechanism. Preserve rejected candidates. Do not infer visual success from structure checks, or geometry accuracy from a better image score.

Two executable entrypoints use Python (NumPy/Pillow only for diagnosis):

```sh
python scripts/refine.py diagnose frozen-roi.json new-report.json
python scripts/refine.py edit roomkit-base.json one-change.json new-candidate.json
```

Diagnosis reports per-view/per-region sRGB error, baseline delta, part mapping and fit-only edit priorities. It deliberately never emits an acceptance verdict. Edit changes exactly one stable RoomKit part, verifies the base hash, and rejects mixed geometry/material interventions. It reuses [RoomKit](../blender-roomkit/SKILL.md) validation, so keep those sibling folders together. Blender material and light controls remain independent; use a separate frozen lighting experiment rather than fitting light and albedo together. Existing detailed `.blend` scenes require isolated copies and their established authoring adapter; do not rebuild them with the minimal RoomKit fixture.

Run new generation cases in independent output directories. Preserve active research state, prior attempts, source bytes and budgets. Enabling this workflow for a new case does not authorize resetting a continuing research case's spent budget.

Parameter priors, hidden surfaces and contact coefficients remain **assumed**, with sources and ranges. Hinges, cloth and volumetric soft bodies are explicit optional experiments, disabled by default. Only actual solver traces and contacts can substantiate dynamics; static folds and keyframes cannot.

Use [Pi3X references](../pi3x-scene-reference/SKILL.md) only after its separate readiness/inference gates. See [validation](references/validation.md) for this delivery's tests, failures and absent capabilities.
