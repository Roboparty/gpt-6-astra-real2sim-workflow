# Generation integration validation — 2026-09-29

This validates that native generation executes the adapters and passes their outputs into existing gates. It does not establish real-image reconstruction accuracy, Pi3X inference success, full-scene visual acceptance or SOTA.

| Check | Result | Evidence |
|---|---|---|
| Skill contracts and CLIs | 49/49 | [case-level results](skill_contracts.json) |
| Native input → reference → modeling → rendering → ROI → review smoke | 29/29; actual Blender 4.5.3 CPU; structural audit passed | [native flow](native_flow.json) |
| Native integration rejection/cache/budget contracts | 20/20 | [integration contracts](integration_contracts.json) |
| Existing refinement tests | Passed routing, invalidation, persistent budgets, freeze gate, timeout child cleanup and evidence binding | `tools/test_refinement.py` |
| Existing geometry-feedback gate | Passed | `tools/test_geometry_feedback_gate.py` |
| Existing structural contracts | Passed eight schema/mutation cases | `tools/test_structure_contract.py` |
| Existing shell/opening collision tests | Passed after deploying the missing existing fixture | `tools/test_shell_collision.py` |

The native smoke uses explicit synthetic input and synthetic Agent responses (`formal_test: false`). `Workflow.accept(agent_model, ...)` actually calls the bundled RoomKit builder; the existing Blender metadata and structural audit code measures the resulting visible meshes; native `build_geometry` renders them; `local_geometry_feedback` reads those pixels through the local-refinement skill. The next actual stage is `agent_review_geometry`, with the ROI report and skill instructions in its packet. Full acceptance/freeze remains blocked. Revision invalidation covers the local-feedback stages and downstream export/validation. The separately tested appearance feedback route executes the same bound adapter, but no new real material/light optimization is claimed.

Pi3X optional blocked mode reports its blocker and retains `inference: not_run`; required blocked mode stops the native DAG at `needs_input`. A second explicitly synthetic consumer case runs the NPZ contract through `scene_reference`. Formal cases reject that synthetic origin. No installation, checkpoint load, forward inference, GPU launch or paid API request was performed.

The local protocol may be a frozen external file or an accepted `agent_calibrate_room/local_protocol.json` artifact. Negative tests cover heldout/unaccepted source, wrong camera, negative camera index, nonexistent part mapping and missing protocol. Changes to reference bytes invalidate cache; ROI-only configuration changes do not restart input ingestion. A spent existing refinement budget prevents RoomKit launch.

## Retained failed attempts

1. `verification-001`: the synthetic assembly fixture omitted the existing required local frame. Blender structural rendering failed with `KeyError: frame`. Fixed the fixture by supplying `frame.yaw_rad`; did not weaken the structural contract.
2. `verification-002`: structure passed, but the native default diagnostic render exceeded the explicit 240-second test timeout. The owned worker process group was stopped by the existing runner; partial outputs and failure logs remain. Added optional `inspection_resolution` for diagnostic views and used 128×128 for smoke only. Default diagnostic sizes and original source-camera dimensions/thresholds remain unchanged.
3. Shell regression first launch lacked its existing `examples/independent_whole_scene_20260926/authoring/room.json` fixture in the isolated remote deployment. The matching small fixture was then copied and the unchanged test rerun.

`verification-003` passed 29 checks in 24.407 s; final behavioral-code verification `verification-004` passed in 24.098 s. These are measured smoke wall times, not total development CPU time. Earlier standalone RoomKit tests used 11.725 s; those are separate fixture tests. Agent cost and total orchestration overhead remain unknown. Retained remote evidence root: `4090-1:/home/wqz/real2sim_generation_skills_20260929_01a0eccb`; model and full images stay remote. [Example generated ROI report](local_feedback_example.json) is a diagnostic, not an acceptance certificate.

## Reproduce

Use the repository's existing Python dependencies and Blender runtime on an execution host. All output directories must be new:

```bash
python tools/test_skill_contracts.py --skills "$PWD/.agents/skills" --output /new/skill-contracts
R2S_CPU=1 CUDA_VISIBLE_DEVICES= python tools/test_generation_flow.py \
  --skills "$PWD/.agents/skills" --blender /path/to/blender --output /new/native-smoke
python tools/test_generation_contracts.py --smoke /new/native-smoke --output /new/integration-contracts
```

No default GPU/paid inference is needed for these tests. The skill-creator frontmatter validators and Python compilation also passed. Original research code/state/processes and historical budgets were not changed; integration was implemented on an independent repository checkout based on `37976c0ccccc1dac53744b73ae7c625dbdfec6e8`.
