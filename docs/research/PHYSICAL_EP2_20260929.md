# Fresh DROID ep2 contact-dynamics reproduction, 2026-09-29

**The first fresh nominal simulation passed the upstream faucet-lever criterion.** This is an actual new physics rollout of the pinned external model/controller, not playback of a saved replay. It demonstrates that the external contact task can be rerun and audited by this project's execution harness. It does not establish that our reconstructed room solves the task or that this project is SOTA.

## Frozen input and scope

Source: [lingxiao-guo/GPT6-real2sim at 736da5c2c6da040a653e581b8f8052ae5559ad51](https://github.com/lingxiao-guo/GPT6-real2sim/tree/736da5c2c6da040a653e581b8f8052ae5559ad51). We read the [ep2 simulator](https://github.com/lingxiao-guo/GPT6-real2sim/blob/736da5c2c6da040a653e581b8f8052ae5559ad51/real2sim_ep2/simulate.py), [task description](https://github.com/lingxiao-guo/GPT6-real2sim/blob/736da5c2c6da040a653e581b8f8052ae5559ad51/real2sim_ep2/README.md), [pipeline limitations](https://github.com/lingxiao-guo/GPT6-real2sim/blob/736da5c2c6da040a653e581b8f8052ae5559ad51/real2sim_pipeline.md), and [rights/provenance notes](https://github.com/lingxiao-guo/GPT6-real2sim/blob/736da5c2c6da040a653e581b8f8052ae5559ad51/ARTIFACTS.md#provenance-and-rights). Included FR3 and PointWorld repository license files are Apache-2.0; the upstream explicitly does not claim blanket rights for all assets or a separate Robotiq CAD license. External assets remain remote and are not redistributed in this repository.

The run used original `simulate.run(label='fresh_nominal', friction_scale=1, offset=[0,0,0], render=False, observed=True, timestep=None)`. The source XML, recorded reference trajectory, controller and scene parameters remained byte-identical to the pinned source. The lever was passive, with no actuator or equality constraint on it; nominal handle mass was 0.12 kg, hinge frictionloss 0.10 N·m, and timestep 0.001 s. These are the upstream assumptions, not measured real-world parameters.

The frozen original task predicate was independently recomputed from newly generated logs and actual per-step contact records:

- Final logged hinge angle > 0.55 rad.
- Handle contact duration > 0.03 s.
- Maximum hinge drift before episode time 13 s < 2°.

An `experiment_config.json` was saved before running, with timeout 600 s, two CPU threads, no GPU or paid APIs, and at most two compatibility retries. **Only one simulation attempt was needed; no physics/trajectory/pose tuning occurred.**

## Actual results

| Metric | Fresh result |
|---|---:|
| Actual `mj_step` calls | 19,741 |
| MuJoCo runtime | 3.13.0 |
| Integrated simulation time, including settling/post-roll | 19.741 s |
| Source reference duration | 18.4419999123 s |
| Physics execution wall time, including observation hook | 6.578 s |
| Total harness wall time, excluding download | 7.899 s |
| Final logged and final solver hinge angle | **40.0214408249°** |
| Gripper–handle contact steps | 199 |
| Gripper–handle contact duration | **0.199 s** |
| Individual handle-contact entries | 239 |
| Peak handle contact force | 11.0344004823 N |
| Drift before 13 s | 0.0019733533° |
| Maximum penetration across logged contacts | 0.0546687259 mm |
| Minimum arm position-limit margin, all steps | 0.7829918166 rad |
| Actual controls within model limits, all steps | Yes |
| States and controls finite, all steps | Yes |
| MuJoCo warning counts | None |
| Unexplained qpos/qvel changes between steps | None |
| Original task criterion, independently recomputed | **Pass** |

Contact occurred between the left inner finger collision geom and four lever-loop collision geoms. Sparse contact rows independently reproduce the 199 active steps reported by dense contact-count arrays. The original simulator reported no unintended penetration deeper than its detection threshold under its original exclusions; this is not an exhaustive claim that every modeled component is collision-free.

Controls were captured **before** every actual solver step; qpos, qvel, time and contact diagnostics were captured **after** it. The observer compared each next pre-step qpos/qvel with the previous post-step state and found zero state injections. It never wrote model state. Rendering was disabled, so the original script's optional render/playback state-setting branch was not executed. Historical `*_replay.npz` files were not downloaded or read. The only replay file present in the run input after execution was the newly generated `fresh_nominal_replay.npz`.

## Compatibility and transfer record

The remote runtime already contained MuJoCo, NumPy, SciPy and OpenCV but lacked `h5py`. The sole source adaptation, applied to a separate input copy, wrapped the `h5py` import as optional. The original `common.load_episode()` already falls back to `recorded_trajectory.npz` when its raw dataset path is absent; we checked that the raw path was absent. No HDF5 code path ran. The original/adapted hashes and a 299-byte unified diff are retained.

Git's filtered sparse checkout encountered GitHub HTTPS connection timeouts. We retained the fixed commit/tree metadata and fetched only the 356 required source/assets files **directly on 4090-1** from the commit-specific raw URLs. Every downloaded blob was verified against its Git blob SHA1 in that fixed commit's tree, plus recorded SHA256. This transferred 36,050,335 bytes and excluded old replays, videos, Blender scenes and rendering mesh duplicates. There was no local large-file relay. The final source plus experiment storage was approximately 78 MiB, below the 1 GB budget. Download failures were a preparation issue, not failed physical episodes or compatibility retries.

## Retained artifacts

Host: `4090-1`.

Source directory: `/home/wqz/real2sim_capability_20260929/external/gpt6_real2sim_736da5`.

Run directory: `/home/wqz/real2sim_capability_20260929/runs/physical_ep2_001`.

| Artifact relative to run directory | Purpose |
|---|---|
| `download_manifest.json` | Pinned source, file sizes and Git/SHA256 verification |
| `execution_01.log` | Complete fresh simulator/harness console output |
| `attempt_01/experiment_config.json` | Frozen nominal call, budget and original criterion |
| `attempt_01/runtime_setup.json` | Engine, dt, masses, friction, limits, actuator IDs and geom names |
| `attempt_01/source_hashes.json` | Input-copy hashes before the compatibility adaptation |
| `attempt_01/adaptation.json`, `compatibility.patch` | Sole optional-h5py import change |
| `attempt_01/actual_controls_and_states.npz` | Every solver step: controls, qpos/qvel, time and dense contacts; 5,036,889 bytes |
| `attempt_01/actual_handle_contacts.npz` | Each actual handle contact: step, geom pair, distance and six force/torque components |
| `attempt_01/result.json` | Fresh run verdict and original metrics |
| `attempt_01/independent_audit.json` | Independent saved-array checks, all-step limits and hashes |

Key SHA256 values:

```text
source scene.xml
ef87ff059438dc84a07da32ca6560edba879accf350629288f263202dc7a907b
source recorded_trajectory.npz
69ac909523e5aeeb23e013de56f29d820efd1c6ed92450270992088bfaaa74cb
source simulate.py
c2979db5c3e7a68de53d27006eb53b93abc7cd3b0487bc676cc35b12418dfb9e
experiment_config.json
01d55803d663315619eb746e58fb117798d2505ab6e86ec1d42b23657a075b6f
actual_controls_and_states.npz
2cd12b8dbb56896f622be56dc572ff3c9478686bd3fdf89c86e8983917dc4293
actual_handle_contacts.npz
2de33912f154f9c7bf9fd131f08f645f7581338c487552f726acb63a750d3e6a
controls array: float64, shape [19741,8], raw C-order bytes
33d817c1315445c34fa51e78c4236aaf65f5c7f4226e90804e3c056a2268bcbe
qpos trajectory array: float64, shape [19741,14], raw C-order bytes
00296f93a2dd1ee062bf74fa690ec1f8b01aafb5e7ef0e64925966cb19be113f
```

The reusable harness is `tools/run_ep2_contact_probe.py`. Run it remotely with the existing Python runtime and a **new** run directory; it refuses to overwrite an existing attempt:

```sh
/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python \
  run_ep2_contact_probe.py \
  --source /home/wqz/real2sim_capability_20260929/external/gpt6_real2sim_736da5 \
  --run /path/to/a/new/run
```

This result establishes one successful nominal **external-model reproduction** with fresh contact evidence. It does not validate new room geometry, quantify unseen-task success, establish robustness across material priors, test flexible bodies, prove hydraulic shutoff, or justify a SOTA label.
