# Parallel development results, 2026-09-29

Actual two-arm refinement, a five-group combination comparison, a fresh robot
contact task, and an auxiliary-frame camera trial were executed. **This is not a
SOTA result or a newly accepted whole-room reconstruction.**

## Prescribed two-round feedback pilot

Two fresh local author agents received the same retained model, source image,
source polygons and camera data. Both had two author turns and two candidate
rounds. Only the feedback arm received candidate contour overlays and numeric
residuals. Actions were cumulative rigid XY/yaw corrections of two cabinets under
the [frozen limits](PILOT_AB_PROTOCOL_20260929.json). Round 2 was always the endpoint;
the control arm's better round-1 score was not selected instead.

| Arm | Initial mean IoU | Round 1 | Prescribed round 2 | Final contour distance |
|---|---:|---:|---:|---:|
| Ordinary renders | 0.954300 | 0.962199 | 0.960876 | 4.204057 px |
| Renders + numeric feedback | 0.954300 | 0.961323 | 0.961323 | 4.144214 px |

Both improved the two coarse fitting silhouettes. The feedback arm's final
advantage is only **0.000447 IoU (0.0447 percentage points)** on one scene, with no
independent replications. It is not evidence of a robust general advantage.
Actual author token costs and full author wall time are unavailable. The action
and render allowances were matched, not token consumption. One feedback dispatch
was rejected by the local agent-slot limit before execution; it did not create an
additional author turn. Both arms produced exactly two proposals.

## Five-group combination experiment

The [combination rule](COMBINED_PROTOCOL_20260929.json) was registered before the
run: the final numeric-feedback pose proposal plus one fixed appearance proposal.
It was not switched to whichever pose arm scored better. The appearance proposal
adds static duvet folds and lightens vent slats using independent material copies;
it changes no camera, rigid furniture transform or optional physics switch.

| Group | Cabinet IoU | Bedding RGB MAE | Vent RGB MAE | Static check after common metadata normalization |
|---|---:|---:|---:|---|
| Unchanged baseline | 0.954300 | 0.122941 | 0.135433 | Passed |
| Ordinary-render pose arm, round 2 | 0.960876 | 0.122950 | 0.135604 | Passed |
| Numeric-feedback pose arm, round 2 | 0.961323 | 0.123091 | 0.135584 | Passed |
| Appearance only | 0.954300 | 0.123080 | 0.107289 | Passed |
| Combined | 0.961323 | 0.123208 | 0.106826 | Passed |

RGB MAE uses values in [0,1], so lower is better. All five endpoint images used the
same camera, 851x638 raster, exposure, eight samples, denoising, seed 0 and disabled
adaptive sampling. These endpoint readouts were supplied to no author for another
revision. The fixed regions and the linear-luminance log metric are recorded in
the protocol and [full comparison](evidence/parallel_20260929/combined_comparison.json).

Combined vent-region RGB error decreased about **21.1%** from baseline, while
bedding RGB error **increased slightly**. The combination is not an across-the-board
improvement. The vent appears less excessively dark and the duvet less regular,
but the inspected render still lacks the source's fine folds, print and accessory
detail. Whole-scene visual acceptance remains unresolved. No component-specific
causal attribution is made from the combined group's gain.

The first endpoint run rejected the unchanged and appearance-only artifacts
because their inherited bed AABB metadata differed from the loaded mesh by
8.967 mm. That [failed attempt](evidence/parallel_20260929/combined_first_attempt.json)
is retained. Every group was then treated identically: derive metadata from its
actual mesh into a new evaluation copy, preserving source models and JSON.
This repair is not counted as a pose/appearance gain. The appearance authoring
script now writes remeasured metadata for future outputs.
Its compatibility check retained the same fixed appearance proposal, passed a
fresh metadata check, and differed from the original render by at most 1/255 in
68 channel values. The original prescribed endpoint image was retained; this
rerender was not used for score-based candidate selection.

The reusable exporter also gained `--geometry-only`: it uses the existing
evaluated-mesh export/audit path without expensive presentation rendering or
claiming a Blender/GLB/USD interchange delivery. Actual geometry-only export and
canonical shell/opening/support checks completed on all five groups. They do not
replace cloth contact, robot task or exhaustive scene-intersection validation.

## Fresh physical robot task

The fixed external DROID ep2 controller/model was run through **19,741 new
MuJoCo steps**, not loaded from an old physics replay. The passive lever ended at
40.02144 degrees with 0.199 seconds of actual gripper contact. The original task
criterion passed on independently recomputed recorded states. Controls stayed
within modeled limits, states remained finite, and no intervening state injection
or solver warning was observed. Peak handle contact force was 11.0344 N.

[Physical report](PHYSICAL_EP2_20260929.md),
[fresh result](evidence/parallel_20260929/result.json), and
[independent array audit](evidence/parallel_20260929/independent_audit.json).
This establishes a fresh nominal third-party task reproduction through our
execution harness, not task success in our newly reconstructed room or real-robot
transfer. Physical parameters remain inherited/assumed.

## Video camera attempt retained as unsuccessful

Five temporal bridge frames per video were added in a separately registered
[initializer protocol](SFM_AUXILIARY_PROTOCOL_20260929.json). All eighteen original
evaluation PNG hashes remained unchanged and present in the 33-frame set.

| Video | Original target frames registered | All initializer frames registered | Points |
|---|---:|---:|---:|
| Open concept | 2/6 | 4/11 | 90 |
| Waterfront | 3/6 | 6/11 | 1 |
| Breakfast nook | 5/6 | 10/11 | 607 |

No scene met the initializer gate; this candidate was not adopted or combined
with per-scene best results. [Target-hash/coverage audit](evidence/parallel_20260929/auxiliary_cameras.json)
and [complete run receipt](evidence/parallel_20260929/sfm_006.json).
Six of the first-round eight camera-initialization attempts are now used.

## Storage, integration and next step

Follow-up structural checks found that the bounded pose tool had not moved its
joint/landmark annotations with the cabinet. The tool is now corrected for future
runs; historical pilot outputs and silhouette scores remain unchanged. On the
same retained posed mesh, updating only those bindings reduced joint-check
failures from nine to two. Two bed attachment-anchor mismatches near 9 mm were
also present in the original baseline. The corrected shoe-cabinet maximum
landmark error is 19.28 px, above the existing 18 px threshold (baseline 16.38 px).
Thus the coarse-silhouette gain does not pass the finer structure/source-fit gate.
The earlier static-engine passes concern shell/opening/support probes and do not
contradict this stricter finding. See [follow-up evidence](UPDATE_20260929T0945.md).

All video, Blender models, physics arrays and meshes remain on `4090-1` under
`/home/wqz/real2sim_capability_20260929`. The local repository holds code and small
evidence JSON. All this round's compute used CPU; no new paid model API or GPU
workload ran. No main-branch merge or SOTA promotion was performed.

The next useful work is to improve the remaining bedding/accessory defects under
new fixed fine-detail annotations, make video geometry robust to changing views
and moving people within the remaining budget, and run contact tasks against
newly reconstructed task geometry. Repeating the same coarse cabinet pilot is
not the next priority. A shared independent benchmark remains unfinished.
