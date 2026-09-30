# Pi3X completes all three fixed trajectories; comparison remains limited

2026-09-30, continuation starting 02:00 UTC. The frozen Pi3X RGB-only route
produces all **18/18 camera poses across 3/3 TUM sequences**. The retained
classical reference completes only 1/3. Translation error is evaluated against
the same mocap observations with the unchanged full-denominator evaluator.

| Fixed sequence | Classical poses | Classical Sim3 ATE | Pi3X poses | Pi3X Sim3 ATE |
|---|---:|---:|---:|---:|
| freiburg1_desk | 0/6 | null | 6/6 | 0.018360941 m |
| freiburg3_structure_texture_far | 6/6 | 0.013064819 m | 6/6 | 0.009635311 m |
| freiburg3_cabinet | 0/6 | null | 6/6 | 0.024985522 m |

There is **no SOTA or matched-budget agent A/B claim**. Both routes receive the
same six original RGB frame identities per sequence, but Pi3X resizes them and
uses a pretrained GPU model while the classical reference processes full-size
images on CPU. These are three correlated benchmark setups, one configuration
and one seed; pretraining exposure is unknown. No failed classical source is
removed or assigned a fabricated finite error.

## Runtime reconciliation, without repeating installation

The main research state still said Pi3X was uninstalled. Existing separate
installation/startup records in the same remote runtime contradicted that state.
Read-only checks confirmed its package consistency, unchanged runner/model/loader
hashes, original input hashes, NPZ hash, finite arrays, six camera matrices and
point-transform agreement (maximum 1.43e-6). `pip check` reports no broken
requirements. No installation or dependency download occurred this turn.

The original failed preparation **1800.107195 s** remains unchanged. Two separate
completion records are now retained: a failed/interrupted phase **168.529979 s**
and successful phase **90.375579 s**. Their recorded installation exception is
historical context, not authorization for future unlimited work. The existing
Waterfront startup is retained as one separately scoped qualification forward,
not reclassified as a complete TUM/AHa comparison or a tuned research candidate.

[Reconciliation](evidence/pi3x_reconciled_20260930/reconciliation.json) ·
[separate failed install](evidence/pi3x_reconciled_20260930/installation_failed.json) ·
[separate completed install](evidence/pi3x_reconciled_20260930/installation.json) ·
[existing startup](evidence/pi3x_reconciled_20260930/startup.json) ·
[startup inputs](evidence/pi3x_reconciled_20260930/startup_inputs.json).

## Frozen learned-reference execution

[Protocol](TUM_PI3X_PROTOCOL_20260930.json) was saved before this run and binds
the same [TUM RGB manifest](TUM_SFM_FRAMES_20260930.json), model/loader bytes,
recorded source revision `9fa3ddb3f8d53041f8b2738df404f62223bbaa7b`, weight
revision `bb1deea4d7423de5b30691739cb451a3f57dc1d5`, and checkpoint SHA256
`69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a`.

The existing Torch 2.5.1+cu124 / NumPy 1.26.4 environment loads weights strictly,
then disables optional multimodal conditions. No intrinsics, poses or depths
are supplied. The pinned loader resizes 640×480 RGB to **574×434** using LANCZOS,
no crop, 255,000-pixel cap and dimensions divisible by 14. Seed is zero;
inference uses bf16 autocast and the existing PyTorch RoPE fallback. No extension
was compiled. Three forwards run once each; all raw output tensors are saved
before numerical checks, without confidence filtering or choosing best views.

The selected RTX 4090 (GPU 3) had 1 MiB reported use, zero utilization and no
compute process at preflight. Each source checks again for external processes,
excluding only this runner's PID. External GPU jobs on GPUs 0–2 remain. A final
process query confirms this run exited and released GPU 3.

All three inputs and protocol hashes remain unchanged. All output arrays are
finite, homogeneous camera matrices and rotations pass numerical checks, and
predicted world/local point transforms agree within 1.44e-6. Those checks alone
do not establish geometric truth; the separate trajectory evaluation supplies
the reported translation diagnostics.

## Evaluation boundary and evidence

Ground truth is opened only by the CPU evaluation adapter after prediction.
The adapter verifies the saved NPZ hashes and exact camera-matrix agreement
with receipts, converts the actual camera-to-world poses, then calls the same
20 ms timestamp association and full-denominator translation evaluator used by
the classical run. All 18 expected timestamps remain. Residuals independently
recomputed from the fitted transforms agree within 1e-10.

Sim3 scale is fitted using GT; the per-sequence scales are approximately
**0.9877, 1.1726, 0.7278**. Consequently these errors do not prove recovered
metric scale. Unscaled SE3 values remain in raw evaluator records, with physical
scale unverified. Orientation, depth-map accuracy, dense geometry, robot tasks
and material recovery are not scored. The original missing depth association
remains 17/18, without changing the 20 ms gate or replacing its RGB frame.

[Prediction receipt](evidence/tum_pi3x_008/prediction.json) ·
[evaluation summary](evidence/tum_pi3x_008/evaluation.json) ·
[desk](evidence/tum_pi3x_008/desk_evaluation.json) ·
[texture board](evidence/tum_pi3x_008/structure_evaluation.json) ·
[cabinet](evidence/tum_pi3x_008/cabinet_evaluation.json).
All raw tensors remain under
`4090-1:/data/real2sim_capability_wqz_20260929/tum_pi3x_008`.

## Ledger and next permitted work

New prediction wall is **20.511734 s**, including loading/checks; its GPU-session
window is **14.006367 s**, with **1.696036 s** of synchronized forward time.
Maximum reserved memory is 9,298,771,968 bytes. CPU evaluation is 0.251600 s.
Earlier startup wall is 17.634805 s, with GPU-session window 11.526548 s.

The corrected GPU ledger conservatively charges the two entire recorded run
walls: **0.010596261 / 4 GPU-hours**. This replaces the stale zero that omitted
the separate startup, without rewriting earlier individual CPU-only run records.
Raw session/kernel timings remain separate and are not added again. Paid API
requests stay zero. Uninstrumented orchestration/teardown and agent costs stay
unknown. [Detailed ledger](evidence/tum_pi3x_008/ledger.json).

Camera candidate attempts reach **8/8**; do not start a ninth without a versioned
budget amendment. Acquisition remains 519.597435/900 s and appearance proposals
6/8. Next work can audit these retained depth/point outputs and implement
provenance-bound native consumption without new inference. This experiment's
receipts are not yet verified through the native reference consumer, and this
does not declare the full reconstructed scene accepted. Hinges/cloth/soft bodies
remain optional. Main stays at `e7e321d`; this is research-branch work.
