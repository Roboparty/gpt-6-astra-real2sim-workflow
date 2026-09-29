# Shared benchmark readiness audit — detailed record, 2026-09-29

**The three-source feedback benchmark remains blocked.** All 18 target images
exist and are hash-bound, but only one source has a complete six-camera sparse
estimate. None of the three has a frozen shared editable initial scene, reviewed
object annotations, independent measured geometry, or measured scale. The four
intended comparison methods remain in the inventory; none has been reconstructed
from these common inputs under a common budget.

This is a read-only audit against research HEAD
`dd51a20f8e7ced270df9cf1cfeeaf859d8dfe61a`, completed during the 10:45 UTC
continuation. It launches no new reconstruction, installation, GPU task or paid
API request. It does not amend an earlier manifest, reset a budget, or promote a
development video to held-out evidence. This detailed record is retained beside
the [root-agent summary](SHARED_BENCHMARK_READINESS_20260929.md).

## What is frozen, and what is only a declaration

The cohort manifest [VIDEO_COHORT_20260929.json](VIDEO_COHORT_20260929.json)
still says `source_acquisition_pending` and has null source hashes. That is its
historical pre-acquisition state, not the current acquisition result. The actual
[acquisition receipt](evidence/heartbeat_0724/video_sources.json) reports all
three hashes and complete decodes. The subsequent
[frame receipt](evidence/heartbeat_0825/frames.json) binds every target PNG to
the same source bytes, exact PTS selection, and 960×540 resolution. Read the
receipts together; do not silently rewrite the historical manifest.

The licensed inputs are AHa project-site H.264 preview encodes associated with
SpatialVID-HQ, not the original dataset files. The recorded use scope is
noncommercial development evaluation under CC BY-NC-SA-4.0. Original clip UUIDs
and household overlap remain unknown. Three clips do not establish three
independent households. The sources were already author-tuned demonstrations.

## Source-by-source readiness

The six-frame camera columns below use the *single complete snapshot run 005*,
not a per-source best selection. All six initialization attempts remain in the
ledger. Run 006 is a separate eleven-input condition with five temporal bridge
frames; it retained the six original target hashes but was not adopted.

| Source | Available observation evidence | Run 005 target-camera coverage | Run 006 original-target / all-input coverage | Shared initialization / annotations | Independent geometry / scale |
|---|---|---|---|---|---|
| `open_concept_g0034` | 899 decoded video frames; target indices 0, 180, 359, 539, 718, 898; source SHA256 `5cc92190193a55e8ab6008dfbf44b80a8c70cf9d9c30b851b7a3c24c3855ed49` | 3/6; targets 0–2 missing; 109 sparse points; failed readiness | 2/6 targets; 4/11 inputs; 90 points; failed | No frozen editable scene or source object masks/landmarks found in the reviewed records | No measured geometry, metric scale, or gravity alignment |
| `bedroom_waterfront_g0024` | 243 decoded video frames; target indices 0, 48, 97, 145, 194, 242; source SHA256 `dc98fd19511837ab9c8888556cbd94c2327945072dd8f9ba653e5b8ded904836` | 6/6; 612 sparse points; camera-initialization readiness passed | 3/6 targets; 6/11 inputs; 1 point; failed | No frozen editable scene or source object masks/landmarks found; moving people still need an explicit annotation/occlusion policy | No measured geometry, metric scale, or gravity alignment |
| `breakfast_nook_kitchen_g0039` | 899 decoded video frames; target indices 0, 180, 359, 539, 718, 898; source SHA256 `1633ab49a325265c445861d217dce47aa84f2a3b221f5cd6077bf186811636f0` | 4/6; targets 0–1 missing; 118 sparse points; failed readiness | 5/6 targets; 10/11 inputs; 607 points; failed | No frozen editable scene or source object masks/landmarks found | No measured geometry, metric scale, or gravity alignment |

Evidence: [run 005](evidence/heartbeat_0825/sfm_005.json),
[run 006](evidence/parallel_20260929/sfm_006.json),
[original-target membership audit](evidence/parallel_20260929/auxiliary_cameras.json).
The readiness gate is one connected model containing every prescribed image
and at least 100 triangulated points. It remains unchanged. Run 005 readiness is
1/3 sources; run 006 readiness is 0/3. Run 006's waterfront reprojection residual
of approximately 0.0025 pixels comes from only one 3-D point and is not superior
reconstruction evidence.

Sparse-camera records contain estimated focal lengths, camera centres and
world-to-CV rotations in an arbitrary similarity coordinate system. Both
`physical_scale_m_per_unit` and `gravity_alignment` are null. A complete camera
record is not a calibrated physical camera or an editable room. Learned depth
and poses would also be predictions, not independent ground truth.

The absence statements above are scoped to tracked research files and a read-only
listing of this research root's `runs/` model/annotation entries. Existing room
and single-assembly models belong to other development cases; no source-ID-bound
three-video initialization receipt was found. No claim is made about unrelated
files elsewhere on the server.

## Four-method inventory and actual execution evidence

| Intended method | Frozen code | What can actually be supported now | Shared three-video reconstruction status |
|---|---|---|---|
| AHa-3D | `82f4b1110cfe4b55fff19df3b3790852ce07b171` | Public workflow/asset code and the three preview videos are available. The pinned README requires external Pi3X/SAM3 checkpoints and compatible Blender; code availability is not an installed, tested runtime. No method execution on our common inputs is recorded. | **Blocked:** runtime/model bundle, per-source recipes, effective settings and matched authoring budget are not frozen/tested. Our Pi3X checkpoint download alone does not satisfy this method's runtime. |
| GPT6-real2sim | `736da5c2c6da040a653e581b8f8052ae5559ad51` | The ep2 subset was downloaded and a fresh MuJoCo contact simulation actually ran: 19,741 steps, finite states, passive lever endpoint passed. This supports the external model/controller diagnostic. Raw original episodes are excluded. | **Blocked / different input regime:** no generic common indoor-video reconstruction adapter or original raw reconstruction episode is available in this audit. Do not pool the ep2 task score with room image scores. |
| HKU three-view | `a1624d6431eb27e2a437feaf74fb34b7c8e937a2` | **New access result:** its pinned README was successfully read in this audit, resolving the earlier HTTP 503 uncertainty. It explicitly excludes `real_rgb/` from Git, expects three input image streams and describes image-estimated geometry/animation rather than measured robot dynamics. No local rerun was performed. | **Blocked:** original three-view source frames are absent, and the existing scene-specific workflow has not been adapted or run on our indoor-video cohort. |
| Real2Gym | unresolved | The earlier snapshot recorded repository-not-found and project-site HTTP 404. No retry or executable artifact inspection was performed in this audit, so current access remains **unknown** rather than newly confirmed absent. | **Blocked:** no resolved revision, inputs or runnable baseline. Keep the intended method slot. |

Primary-source checks:
[AHa pinned README](https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/README.md),
[AHa reference-input exclusions](https://github.com/KevinXu02/aha-3d/blob/82f4b1110cfe4b55fff19df3b3790852ce07b171/references/README.md),
[GPT6-real2sim artifact scope](https://github.com/lingxiao-guo/GPT6-real2sim/blob/736da5c2c6da040a653e581b8f8052ae5559ad51/ARTIFACTS.md),
[HKU pinned README, now readable](https://github.com/hku-sail/Real2Sim_GPT6_ASTRA/blob/a1624d6431eb27e2a437feaf74fb34b7c8e937a2/README.md).
The historical [four-method snapshot](COMPARATORS_20260929.json) is preserved.
Fresh ep2 evidence is in [the contact report](PHYSICAL_EP2_20260929.md) and
[actual runtime result](evidence/parallel_20260929/result.json).

The methods span distinct input/task regimes. Preserve all four inventory slots,
but mark incompatibility explicitly rather than inventing a single 3×4 scalar
leaderboard. A future adapted workflow must receive a new, pinned adapter identity
and must not be called an unmodified upstream baseline.

## Metrics that are fair now, and metrics that are blocked

| Metric or claim | Current permitted comparison | Remaining condition |
|---|---|---|
| Acquisition and initializer coverage | Report 3/3 decoded sources, 18/18 frozen targets, per-source registered targets and complete-source count. Show every attempted configuration separately. | These are readiness metrics, not agent/reconstruction superiority. Eleven-input and six-input conditions must be labelled separately. |
| Sparse fit reprojection error | Diagnostic within each run, beside point count, camera coverage and failures. | Correspondences/point populations differ; lower conditional residual alone cannot rank geometry quality. |
| Fixed-camera visible-mask IoU, contour distance and source landmarks | The retained-photo pilot has real source-bound fitting scores. The evaluator supports fixed multiple views and failure penalties. | The three-video cases lack source annotations and common editable initialization; no three-video A/B score exists. |
| Source-image appearance error | The retained-photo component studies have frozen-region fitting errors. | Common video ROIs, rendering/exposure policy, occlusion policy and actual candidate renders are missing. Do not transfer the photo score to this cohort. |
| Held-out novel-view generalization | None established on these clips. | All 18 target images entered SfM; the extra run-006 images also entered initialization. They cannot retroactively be called unseen observations. A downstream feedback-withheld view must still disclose camera/preprocessing exposure. |
| Metric depth, 3-D Chamfer, camera trajectory error, unseen back surfaces | Blocked. | No independently measured reference geometry/trajectory/scale. Model predictions cannot act as truth against themselves. Assumed furniture sizes do not remove this blocker. |
| Real friction/material recovery or robot task success on reconstructed rooms | Blocked. | No measured physical reference and no new-cohort robot/control/task model. The ep2 experiment validates a separate supplied model/controller. |
| Efficiency or SOTA | Only measured component wall times are available. | No common end-to-end runs, equivalent model-call/token accounting, independent scene/seed replication, uncertainty or compatible competitor scores. |

`tools/prepare_geometry_protocol.py` currently prepares one view named `source`
with role `fit`; it does not create a multi-video benchmark or a held-out split.
`workflow/r2s/geometry_feedback.py` supports multiple fixed views, hashes and
separate fit/heldout summaries, but support in code is not execution evidence.
Missing or invalid candidate observations retain failure penalties; a future
wrapper must also retain blocked source slots instead of averaging only the
waterfront case.

## Smallest actionable next experiment

The next **unblocked preparation step** is to freeze reviewed annotations for all
three sources on the existing six target frames each. It requires no new model
download or camera trial: select a fixed small set of visible static object IDs
per source before candidate rendering, mark exact visible masks and identifiable
corners, record occlusion/ambiguity (including people), and bind the annotations
to existing PNG hashes. Keep every source and declared observation slot; ambiguous
geometry stays unknown rather than being guessed into a favourable label.

In parallel with annotation preparation, register the learned-reference route
before spending camera trial 7. It must use the same six target hashes per source,
freeze resizing/cropping and camera conventions, retain all outputs/confidences
and failures, and separate output availability from geometric accuracy. Pin the
model checkpoint and adapter. A six-pose neural output alone cannot be advertised
as satisfying the SfM triangulation gate: it needs a separately specified
cross-method readiness check. This report does not register or run that trial.

The first executable *feedback* pilot after annotation is a narrow waterfront
development pilot using **only run 005** as its frozen camera initializer. Create
one editable scene in that same arbitrary gauge, freeze its bytes and one bounded
rigid-object action space, and give both agents identical images, annotations,
camera/scene bytes, model settings, turns and render allowance. Record exact
token/model costs if available; otherwise state unknown. Compare the final
prescribed round and enforce fine source-fit and structure gates. It is a 1-source
pilot with the other **2/3 source slots still blocked**, not a completed three-source
benchmark. Metric scale is unnecessary for this narrowly labelled image-fit test;
any exporter scale choice must remain `assumed` and cannot support physics claims.

Before a full-cohort A/B, all three sources need the same preparation gates and
frozen common initializer policy. Do not combine per-source best SfM/learned
outputs without preregistering that hybrid as a distinct method. For genuinely
held-out evaluation, obtain a new independent cohort or preregister additional
observations and their allowed calibration access before exposing them to the
reconstruction agents. Previously used targets cannot be made unseen by renaming
their split.

## Resource and provenance boundary

At the audited HEAD: camera trials used **6/8**; new GPU-hours **0/4**; separately
billed API requests **0**. Pi3X preparation spent its full separately recorded
1,800-second budget; checkpoint bytes are verified but imports/model construction
and inference have not passed. Resuming that preparation needs a versioned budget
amendment that retains spent time and failed attempts. This audit spends no camera
trial and makes no such amendment. See [Pi3X preparation](PI3X_RUNTIME_20260929.md).

Useful immutable local report hashes (SHA256):

- Cohort manifest: `b10f9bcfae290444c746291506f53cdc8c598bc1edaa2cd07fe2a94f93fcc02a`.
- Comparator snapshot: `198bf8a0dad0b2b8fc5a6e003ecc2b81167ce13c5c66b0796bff5bd6968f64ec`.
- Frozen-frame receipt: `7304109f95fb441e404d0c7d544320b5b6ce11fb1b4b0a34c1d006fe89dd83f3`.
- Run 005 receipt: `92f1d71821fc121448dc7fb5bc49e4115015d900bd45b9dc557547686a023a8d`.
- Run 006 receipt: `8c8473b634b0f534ec77ea93770eded4c91006bb0addbbee4ae758a287ca0109`.

These are hashes of the checked-in report bytes, not a claim that line-ending
normalization preserves an upstream raw-file hash. Remote media and large model
artifacts remain on 4090-1. The original baseline and `needs_revision` verdict are
unchanged; the evidence does not support SOTA.
