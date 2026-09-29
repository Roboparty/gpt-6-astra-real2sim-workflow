# Container placement task acceptance

`r2s.task_evaluation.evaluate_container_task(trace, protocol)` checks numeric trace evidence for entry, release, hand withdrawal, optional door closure, and sustained stability. It is a reusable evaluator, not evidence that a real room or robot has completed this task. It ignores producer `success` flags.

The caller freezes `episode_duration_seconds` and all thresholds before running the episode. Keep each attempted episode in the denominator, including task failures, invalid traces, missing artifacts, infrastructure errors and timeouts. Do not truncate a trace at its first apparent success or reset the object to produce a passing suffix.

```python
report = evaluate_container_task(trace, {
    "episode_duration_seconds": 4.0,
    "hold_seconds": 2.0,
    "max_sample_gap_seconds": 0.05,
    "containment_tolerance_m": 0.002,
    "min_hand_distance_m": 0.1,
    "max_linear_speed_m_s": 0.02,
    "max_angular_speed_rad_s": 0.1,
    "require_hinge_closed": False,
    "hinge_closed_angle_rad": 0.0,
    "hinge_tolerance_rad": 0.05
})
```

Only the episode duration is required; the example shows the other defaults. Thresholds are engineering choices for an initial protocol, not universal standards or physical calibration. `require_hinge_closed=false` supports a static container. This evaluator does not enable or generate joints, cloth or soft bodies.

## Trace data

```json
{
  "schema_version": "real2sim.container_task_trace/1.0",
  "vertex_frame": "container_local",
  "container_inner_bounds_m": [[0, 0, 0], [1, 1, 1]],
  "provenance": {
    "kind": "simulation",
    "engine": "MuJoCo",
    "engine_version": "actual runtime version",
    "model_sha256": "64 lowercase hexadecimal characters from the executed model",
    "source_artifact": "run/full_task_trace.json",
    "state_origin": "numerical_solver",
    "object_pose_control": "solver_only",
    "state_edits": []
  },
  "samples": [
    {
      "time_s": 0.0,
      "object_vertices_local_m": [[1.1,0.4,0.1],[1.2,0.4,0.1],[1.1,0.5,0.1],[1.1,0.4,0.2]],
      "gripper_object_contact_count": 2,
      "hand_container_distance_m": 0.01,
      "object_linear_speed_m_s": 0.1,
      "object_angular_speed_rad_s": 0.0,
      "hinge_angle_rad": 1.0
    }
  ]
}
```

The example shows one record; an executable trace needs every sample from time zero through the frozen duration. Use elapsed simulation time from the initial state. Timestamps must strictly increase and all numbers must be finite. Speeds, distances and contact counts cannot be negative; booleans are not accepted as numbers. Contact counts must be integers. Missing fields or malformed numeric input raise `ContractError`; the caller records this as an invalid trace, not a dropped episode.

The **container is stationary** in this initial protocol. Its inner box is fixed in container-local coordinates. At each timestamp transform the complete object collision vertices into that frame; use a consistent full vertex set, not just the center or selected convenient points. Bounds describe the usable interior task region and must be verified against actual geometry. For curved collision primitives, use conservative bounding geometry or a separately validated containment producer. A non-box interior needs a separate evaluator; an enclosing box alone cannot prove containment in an arbitrary cavity.

`hand_container_distance_m` is the minimum separation of any hand collision surface from the closed container region, including the interior volume. A hand still inside has distance zero. Do not use distance between body origins. `gripper_object_contact_count` counts all hand/finger contacts with the object, not just a selected fingertip. A non-contact weld or kinematic grasp must also be absent after release; such model constraints require independent runtime inspection. Speeds are SI magnitudes of object linear and angular velocity in the stationary world frame. The optional hinge angle is the actual joint coordinate in radians, using the protocol's closed reference; every sample requires it when enabled.

## Conditions

1. The recorded episode begins at zero and reaches the exact frozen end time. Choose the duration as an integer number of simulation steps. The evaluator does not shorten an incomplete episode to fit available data.
2. Every adjacent sample gap, including before the final window, is at most `max_sample_gap_seconds`. The final window has at least `ceil(hold_seconds / max_sample_gap_seconds) + 1` samples and covers at least the full hold duration. The sample at or immediately before the window start is included conservatively.
3. Object geometry is initially observed outside the region before its final release, establishing entry. A release is a positive-to-zero gripper-object contact-count transition. Both sides of the **last** release transition must already be fully contained within the declared tolerance. Releasing above the container and hoping it drops inside intentionally fails this placement protocol; define a separate drop task if that is intended.
4. Across **all** final-window samples: every object vertex is inside the inner bounds, object-gripper contacts remain zero, the whole hand is withdrawn far enough, linear and angular speed remain below their limits, and the hinge remains closed if requested. A brief escape, contact, motion spike or reopening in that window fails even if the last frame looks correct.

The report includes failed criterion names, measured extrema, release time, sample counts, observed durations, and SHA256 hashes of the normalized frozen protocol and supplied trace. `numeric_criteria_pass` reports the numeric criteria. `simulation_task_pass` additionally requires declared numerical-solver origin, solver-only object motion, and no state edits after initialization. State-reset and keyframe traces fail that gate. `kind=reference` can pass numeric checks but **never** passes `simulation_task_pass`.

## Evidence boundary and testing

A JSON provenance statement is not proof of runtime behavior. This pure evaluator cannot authenticate a producer, verify an external artifact hash, detect an unreported teleport, inspect hidden welds, establish complete geometry/contact coverage, or detect events between samples. The execution harness must export samples from actual solver state, independently bind model and run artifacts, and ensure robot actuation is the only manipulation mechanism. No post-initialization object pose injection or scripted object animation may be counted as a physics result.

Containment is separate from collision penetration, solver warnings, stability under disturbances and calibration of material/contact parameters. A passing simulation task is not real-world success or dataset qualification. Report optional tasks separately from static reconstruction quality.

Run `python tools/test_task_evaluation.py` with the standard library. The fixtures test numeric success, early release, a fallen/outside object, unclosed/reopened hinge, retained grasp, incomplete withdrawal, unstable motion, missing/truncated samples, static operation without a hinge, reference/keyframe/reset rejection and malformed input. These are synthetic fixtures that test the evaluator; they do not claim an actual physics rollout.
