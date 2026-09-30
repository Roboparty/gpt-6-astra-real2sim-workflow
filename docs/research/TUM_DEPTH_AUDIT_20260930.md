# Depth audit exposes scale errors hidden by aligned camera scores

2026-09-30, continuation starting 03:02 UTC. Reusing the frozen Pi3X outputs
without another inference, the raw predicted depth has substantial scale error
on the cabinet sequence: **39.77% AbsRel and 0.6843 m frame-mean RMSE**, despite
its previously reported GT-aligned camera-trajectory error of 2.50 cm. A small
aligned camera error does not establish metrically accurate scene geometry.

## Registered method and denominators

[Protocol](TUM_DEPTH_PROTOCOL_20260930.json) binds the original RGB index,
prediction receipt, raw NPZs through that receipt, and the already-frozen
trajectory evaluation. No model or preprocessing parameter is revised.

The official TUM format specifies RGB/depth pixel correspondence, depth PNG
values divided by 5000 to obtain optical-axis Z in metres, zero as missing
depth, and no additional correction to the supplied pre-scaled depths.
[Official file formats](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats).
The pinned Pi3X source constructs `local_points=[x*z,y*z,z]` and already applies
its learned metric factor. The evaluator uses `local_points[...,2]`, without
taking vector length or multiplying by the learned factor a second time.

Predicted float32 Z is upsampled from 574×434 to 640×480 using fixed bilinear
interpolation; reference depth is never interpolated or cropped. All positive
reference-depth pixels are included. No confidence mask, edge erosion, depth
range clipping or depth-derived scale fit is used. An invalid prediction on any
valid-reference pixel makes that frame's full score unavailable.

Two declared diagnostics are kept side by side: raw learned-scale depth and
depth multiplied by the previously fixed trajectory-Sim3 scale. The latter uses
ground truth and **is not an autonomous model improvement**. No minimum-error
arm, frame or pixel subset is selected.

## Complete results

Values below are arithmetic means of per-frame metrics, not pooled-pixel RMSE.
AbsRel is the mean absolute relative depth error. The texture-board row is
explicitly partial; its full-six-frame score remains null.

| Sequence | Evaluated / expected frames | Raw AbsRel | Raw RMSE (m) | Trajectory-scaled AbsRel | Trajectory-scaled RMSE (m) |
|---|---:|---:|---:|---:|---:|
| desk | 6/6 | 7.7887% | 0.150234 | 6.8062% | 0.145842 |
| texture board | **5/6, partial** | 14.3228% | 0.349844 | 1.7020% | 0.132425 |
| cabinet | 6/6 | 39.7718% | 0.684295 | 3.4106% | 0.166419 |

Scale multipliers are unchanged from the prior camera evaluation: 0.98773497,
1.17259711 and 0.72775650. Their large effect on board/cabinet depth is consistent
with scale error being a substantial contributor, but residual geometry,
registration, interpolation and RGB/depth timing errors remain. This diagnostic
does not isolate those other causes or validate hidden surfaces.

- **17/18** depth references are available; all 17 can be scored.
- Board ordinal 5 retains its **28.994 ms** nearest-depth gap and fails the
  unchanged 20 ms matching gate. It is not replaced or interpolated in time.
- **4,247,148** valid reference pixels are scored, out of 5,222,400 pixels in the
  17 matched images (81.33%). Across all 18 expected images, reference coverage
  is 76.81%; missing/zero depth does not provide full-surface truth.
- Invalid predictions at valid reference pixels: **0**. This is numerical
  coverage, not an accuracy threshold pass.
- Full-six-frame depth reporting is available for **2/3** sequences. The
  full-18-frame aggregate remains **null**. No success-filtered aggregate is
  presented as the cohort score.

## Verification, limits and disposition

Five test methods pass in the existing remote runtime, covering exact depth,
known scale error, invalid predictions, all-missing reference depth and shape/
reference guards. Invalid predicted pixels remain in the denominator and make
the full metric unavailable.

A second implementation uses explicit pixel-center bilinear sampling rather
than PIL resize, and different summation formulas. It recomputes all 17 frame
scores with maximum AbsRel difference **1.32e-10** and RMSE difference
**4.47e-10 m**. It rechecks saved NPZ/depth hashes and the retained missing frame.
This verifies the calculations, not the complete accuracy of the sensor or
underlying scene. RGB/depth observations can still differ in time by up to
20 ms, and reference invalid pixels are common.

[All per-frame results](evidence/tum_depth_001/receipt.json) ·
[independent calculation](evidence/tum_depth_001/independent_audit.json) ·
[tests and source binding](evidence/tum_depth_001/verification.json).
Full predictions and depth data remain on `4090-1`; new small audit outputs are
under `/data/real2sim_capability_wqz_20260929/tum_depth_001`.

Measured CPU evaluation/audit walls are **0.380849 s + 0.393106 s**; tests report
0.001 s separately. No new inference, GPU/API work, downloads or camera candidate
is consumed. Camera cap remains **8/8**, acquisition ledger remains unchanged,
and all earlier failures are retained.

Pi3X outputs remain provisional geometric references. Preserve their unverified
physical scale in native scene initialization; do not silently apply GT-derived
scales to production scenes or infer robot/collision acceptance from the camera
score. Next authorized work can bind existing outputs to native provenance and
audit scene construction without a ninth camera inference. No SOTA or formal
main-branch promotion follows from this audit.
