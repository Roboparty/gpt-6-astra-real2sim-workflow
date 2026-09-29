# Shared benchmark readiness audit — 2026-09-29 10:45 UTC continuation

The intended denominators remain **three indoor-video development sources and
four comparator methods**. No common reconstruction leaderboard can yet be
computed. This audit separates source availability, initializer output and the
missing inputs needed for an equal-input experiment; it creates no new runs.

## Three-source input readiness

All three browser-preview videos were downloaded directly to the remote host,
fully decoded and hashed. Six frames per source (18 total) are frozen at their
original 960×540 resolution and exact presentation timestamps. The old cohort
manifest's acquisition-pending state is historical; the subsequent
[acquisition receipt](evidence/heartbeat_0724/video_sources.json) and
[frame freeze](evidence/heartbeat_0825/frames.json) are the executed evidence.

| Source | Frozen decoded indices | Seeded control original target cameras | Auxiliary attempt original target cameras | Shared editable scene / object annotations |
|---|---|---:|---:|---|
| open_concept_g0034 | 0, 180, 359, 539, 718, 898 | 3/6 | 2/6 | Missing / missing |
| bedroom_waterfront_g0024 | 0, 48, 97, 145, 194, 242 | 6/6 | 3/6 | Missing / missing |
| breakfast_nook_kitchen_g0039 | 0, 180, 359, 539, 718, 898 | 4/6 | 5/6 | Missing / missing |

The camera columns describe the complete retained
[snapshot control](evidence/heartbeat_0825/sfm_005.json) and
[auxiliary attempt](evidence/parallel_20260929/sfm_006.json), respectively. They
are not a stitched per-source best result. The original readiness gate is all
six target cameras in one model and at least 100 triangulated points: control
passes 1/3 sources, auxiliary passes 0/3. Six of eight camera attempts are spent.

For **every** source, metric scale, gravity alignment, independent calibrated
poses/depth/geometry and physical material measurements remain unavailable.
Sparse points/poses are estimates in an arbitrary similarity gauge. Source
household identities and overlap are unresolved. The public videos are
author-tuned development examples under CC BY-NC-SA-4.0, not three proven
independent held-out homes. A screenshot or rendered author result is not GT.
All 18 target frames already participated in SfM; they cannot retroactively be
declared unseen evaluation data.

## Comparator readiness, without pooling input regimes

The [original code snapshot](COMPARATORS_20260929.json) remains immutable.

| Method / frozen commit | Available evidence | Remaining obstacle to common reconstruction evaluation |
|---|---|---|
| AHa-3D / `82f4b1110cfe4b55fff19df3b3790852ce07b171` | Public code and three attributable source previews | No completed common-input reconstruction rerun; shared initialization, runtime/model settings and comparable budgets still need binding. Predicted example meshes/cameras are not independent GT. |
| GPT6-real2sim / `736da5c2c6da040a653e581b8f8052ae5559ad51` | Portable ep2 model and trajectory; fresh MuJoCo contact replay independently audited | Missing raw original episodes for a from-scratch rerun. Multiview robot-action input is a separate stratum from indoor video. |
| HKU three-view / `a1624d6431eb27e2a437feaf74fb34b7c8e937a2` | Pinned README now readable; editable replay model and estimation code described | Original `real_rgb` inputs are excluded from Git. Replay is a visual approximation, with estimated scale/poses and interpolated released-object motion; it is not solver task success. |
| Real2Gym / unresolved | Prior repository-not-found and project-site access failures retained | Version and runnable public inputs unresolved. No new accessibility conclusion is inferred in this continuation. |

The HKU update resolves the prior HTTP 503 documentation uncertainty, not the
missing raw inputs. It is directly supported by the
[fixed-version README](https://github.com/hku-sail/Real2Sim_GPT6_ASTRA/blob/a1624d6431eb27e2a437feaf74fb34b7c8e937a2/README.md).
The third-party ep2 result is scoped in the
[physical reproduction report](PHYSICAL_EP2_20260929.md); success there does not
establish reconstruction quality or robustness on these three video sources.

## Fair endpoints and next executable step

- **Available now:** all-source input decode/hash coverage and complete-source
  camera-initialization readiness under a frozen method configuration. These are
  engineering readiness endpoints, not relative 3-D accuracy or agent uplift.
- **Blocked A/B:** source-bound editable initialization, object/part annotations,
  common camera policy and a per-arm generation budget must exist before running
  two agents on each of the three sources. Both arms must receive the same
  observations; retain missing sources in the denominator. The one-room pilot
  does not fill these cells, nor establish equal token/model costs.
- **Blocked reconstruction accuracy:** do not compute metric Chamfer, camera
  calibration accuracy or material recovery against estimated outputs as if
  they were measured truth. A separate source with independent ground truth
  and a frozen evaluation split is required for those endpoints.
- **Next step without dependency work:** freeze source-bound visible static
  object annotations across all three sources, preserving occluded/ambiguous
  labels as such. Waterfront can support a clearly labeled one-source development
  A/B preparation; the other 2/3 remain blocked and are not removed. This does
  not establish a complete three-source comparison.
- **Separate initializer experiment:** preregister a six-frame learned-reference
  initializer for all three sources, retaining original frame hashes, fixed
  preprocessing, one configuration and complete output/confidence coverage.
  Geometry-quality and scale gates must be separate from merely producing six
  predictions. Do not consume camera trial 7 until its runtime and protocol are
  ready. Then build one versioned common scene/annotation bundle per source;
  any source not ready stays a blocked cell, rather than being dropped.

Pi3X weights are verified, but its environment is not ready and its 1,800-second
preparation budget is exhausted. No restart or budget reset occurred in this
continuation. The [preparation audit](evidence/heartbeat_0945/pi3x_preparation_audit.json)
retains that blocker and reusable remote bytes. An explicit versioned budget
amendment must precede any further dependency work. Shared benchmark claims
remain blocked even if a learned model subsequently emits dense geometry.
