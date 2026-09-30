# Classical RGB-only baseline: one complete trajectory out of three

The first sensor-reference prediction run completes only the texture-board
sequence. Desk and cabinet yield no registered cameras; their full-denominator
ATE remains null. All three sequences and all 18 frozen observations stay in
the comparison. There is no cohort-average accuracy or SOTA claim.

## Frozen prediction policy

[Protocol](TUM_SFM_PROTOCOL_20260930.json) and
[RGB input manifest](TUM_SFM_FRAMES_20260930.json) were saved before execution.
The existing PyCOLMAP 4.2.0 CPU initializer is byte-identical to the prior
initializer. Camera mode, SIMPLE_PINHOLE model, initial focal factor 1.2,
4,096-feature cap, SIFT threshold, seeds, one-model policy and geometric defaults
match `sfm_init_005`. Only cohort identity/input frames and reporting scope change.
No camera intrinsics, depth or GT pose is supplied to prediction. Original
640×480 RGB pixels are unchanged; logical input/evaluator separation is retained.

There is one execution, with two CPU threads and a 300-second per-source limit.
The initializer may perform its installed internal initial-pair search/relaxation;
these are frozen library behavior, not new assistant-selected runs. Overall exit
code 1 records incomplete cohort readiness, while all three worker processes
complete normally. No retry, threshold adjustment or failed-frame replacement.

## Full results and failure evidence

| Sequence | Registered poses | Triangulated points | Nonzero verified image pairs | Full Sim3 translation ATE |
|---|---:|---:|---:|---:|
| freiburg1_desk | 0/6 | unavailable | 5/15 | null — missing predictions |
| freiburg3_structure_texture_far | 6/6 | 374 | 15/15 | 0.013064819 m |
| freiburg3_cabinet | 0/6 | unavailable | 0/15 | null — missing predictions |

Desk has 1,373–3,690 keypoints per input, but its retained log repeatedly
discards bad initial pairs and finally finds no acceptable initial pair.
Cabinet has only 16–311 keypoints per input and no geometrically verified pair;
the mapper reports no images with matches. These observations distinguish
failure modes; they do not prove a single causal fix. The board has 1,696–2,851
keypoints per input. All 45 pair cells, including zeros, are retained in the
[model/matching audit](evidence/tum_sfm_007/model_audit.json).

The successful trajectory's 1.31 cm score follows a global Sim3 fit to mocap
over its six original RGB timestamps. **Scale is fitted from GT during
evaluation, not recovered as physical scale by the initializer.** No error is
averaged over the two missing trajectories. Orientation is exported but not
scored; depth/geometry accuracy and robot success are not evaluated. Existing
unscaled SE3 evaluator values are preserved as raw diagnostics and are not
interpreted as physical metre errors for this arbitrary-gauge prediction.

The previously retained depth gap affects one board frame, but all six RGB
timestamps have valid mocap associations. Thus the translation-only endpoint
can use all six, without pretending the depth endpoint is complete.

## Verification and cost

- Original input image and manifest hashes match before/after copying and run
  snapshots. The predictor never opens the evaluator directory.
- Actual persisted COLMAP model poses independently match the camera receipt;
  maximum center difference is 1.67e-15 in the SfM gauge. Rotations are checked
  against the inverse camera transform. Databases are opened read-only.
- All 18 expected timestamps enter the unchanged frozen trajectory evaluator.
  Missing predictions keep ATE null. Successful Sim3 residuals independently
  recompute to the reported RMSE within 1e-10.
- Exact initializer, protocol, frame index, evaluator, adapter, prediction,
  ground-truth and result hashes are retained. Both new audit/evaluation adapters
  execute successfully in the existing runtime and compile locally.

[Initializer receipt](evidence/tum_sfm_007/initializer.json) ·
[evaluation summary](evidence/tum_sfm_007/evaluation.json) ·
[desk evaluation](evidence/tum_sfm_007/desk_evaluation.json) ·
[board evaluation](evidence/tum_sfm_007/structure_evaluation.json) ·
[cabinet evaluation](evidence/tum_sfm_007/cabinet_evaluation.json).
Large runtime artifacts remain at
`4090-1:/data/real2sim_capability_wqz_20260929/tum_sfm_007`; evaluation artifacts
are in sibling `tum_sfm_007_evaluation`. Remote external CPU work was observed
and left untouched. No GPU job, dependency install or paid API request ran.

Camera attempts advance **6/8 → 7/8**. Initializer wall time is **4.502655 s**;
evaluation wall is **0.030735 s**. Read-only audit/orchestration overhead remains
unmeasured. Data-acquisition usage stays **519.597435/900 s**, appearance proposals
stay **6/8** and all earlier camera failures remain. The original AHa control's
1/3 readiness remains a separate cohort result, not pooled with TUM.

Preserve the last camera attempt until a justified intervention and its full-
cohort protocol are ready. A learned-reference route still requires its own
runtime/version/input checks; these classical results do not establish agent
feedback uplift. Main stays at `e7e321d`; all changes stay on research.
