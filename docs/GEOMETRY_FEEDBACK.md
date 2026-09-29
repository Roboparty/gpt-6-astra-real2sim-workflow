# Fixed-camera geometry feedback

`tools/evaluate_geometry_feedback.py` measures visible geometry against a frozen
image protocol. It provides per-object silhouette IoU, symmetric contour residuals
in pixels, signed centroid displacement, bounding-box scale ratios, and landmark
reprojection errors. It writes source-image overlays for human/agent inspection.
It supports multiple cameras and reports `fit` and `heldout` views separately.

This is a diagnostic capability, not a claim that reconstruction quality or SOTA
has been achieved. It does not estimate cameras, segment photographs, generate
geometry, or validate hidden geometry or physical parameters.

## Run the executable example

Use the existing runtime with NumPy, SciPy and Pillow. No model download is needed.
Keep full images and render artifacts on the reconstruction server.

```sh
python tools/test_geometry_feedback.py --output-dir /remote/evidence/geometry-feedback
```

The test creates a two-view 64 x 64 synthetic protocol, candidates, JSON reports
and PNG overlays. Known perturbations include a 6 px translation (IoU 0.6), a
twofold increase in width and height (IoU 0.25), absent geometry, missing views,
unreadable artifacts, camera drift, behind-camera points, stale hashes and
heldout leakage. It also exercises entity ID palettes and the command-line hash
gate. `synthetic-suite.json` retains the results. These tests measure evaluator
sensitivity and failure handling; they do not measure real-scene quality.

For a real candidate:

```sh
python tools/evaluate_geometry_feedback.py \
  --protocol /remote/case/frozen/geometry-protocol.json \
  --candidate /remote/case/candidate/geometry-candidate.json \
  --expected-protocol-sha256 <previously-registered-canonical-json-digest> \
  --output /remote/case/candidate/geometry-feedback.json
```

Exit code is 0 for all declared checks passed, 1 for a failed candidate, and 2
for a command-line protocol hash mismatch. Invalid protocol structures raise an
error; they cannot produce a passing report. Artifact paths are relative to their
own manifest's directory unless absolute. The protocol digest uses
`r2s.contracts.digest`: canonical JSON, sorted keys, no spacing, UTF-8 with
`ensure_ascii=False`. Record it before candidate generation; do not recalculate a
new acceptance hash each time a candidate changes.

## Protocol

The following is a schema example. Replace the hash placeholders with actual
SHA-256 file hashes. The thresholds are illustrative; choose and freeze thresholds
for the camera resolution and annotation noise before fitting.

```json
{
  "schema": "real2sim.geometry-feedback-protocol/1.0",
  "thresholds": {
    "minimum_iou": 0.9,
    "maximum_boundary_mean_px": 2.0,
    "maximum_landmark_error_px": 3.0
  },
  "views": [{
    "id": "source_0000",
    "role": "fit",
    "source": {"path": "source.png", "sha256": "ACTUAL_SOURCE_HASH"},
    "camera": {
      "image_size": [640, 480],
      "position": [0, 0, 0],
      "rotation_world_to_cv": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      "focal_px": 500,
      "principal_point": [320, 240]
    },
    "objects": [{
      "id": "cabinet",
      "mask": {"path": "cabinet-visible.png", "sha256": "ACTUAL_MASK_HASH"},
      "landmarks": [{"id": "front_corner", "uv": [300, 250]}]
    }]
  }]
}
```

Each view has an explicit object denominator and each object must have a mask,
landmarks, or both. Masks are binary grayscale/1-bit images (values 0/1 or 0/255),
the same size as the source image and frozen camera. They represent visible pixels,
after occlusion. Empty source masks are invalid observations, not perfect matches.
There is no automatic resizing, alignment, per-candidate crop, soft threshold or
source-mask modification. When starting from `evaluation.segmentation_scores`
polygon annotations, rasterize and review visible masks once, including its
documented occlusion ordering, then freeze their hashes.

Use the existing camera fields from `calibration.py` and `scene.json`.
`rotation_world_to_cv` maps world to OpenCV camera coordinates, position is the
camera center in world coordinates, focal length is in pixels, and UV uses
top-left image coordinates. If image resolution changes, freeze a new protocol
with consistently transformed intrinsics and observations; do not compare scores
as if the protocol had remained unchanged.

## Candidate

The Blender adapter can generate the candidate mask artifacts from a saved model:

```sh
blender -b /remote/case/scene.blend \
  -P workflow/r2s/blender_geometry_feedback.py -- \
  /remote/case/scene.json /remote/case/frozen/geometry-protocol.json \
  /remote/case/new-mask-render
```

It writes `candidate.json`, per-object binary masks and an opaque clay preview at
each exact protocol camera. It uses Cycles' Object Index pass and compositor
IDMask nodes with antialiasing disabled, avoiding RGB label confusion. Other
geometry still occludes the target; it is not hidden for per-object rendering.
Ownership follows `entity_id`, then `furniture_id`, then the Blender object name.
An absent owner generates an empty mask and fails the evaluator. The renderer
does not save or modify the input `.blend` file. Use a fresh output directory to
retain earlier evidence.

The adapter applies an opaque material override, including to glass. Its material
scan records common transparency/volume indicators, but is not a complete shader
analysis. Source mask annotations must use the same opaque-silhouette convention;
transmitted visibility is a separate future evaluation. Camera resolution is 100%,
pixel aspect is one, motion blur and depth of field are disabled, and the adapter
checks the actual Blender projection at five locations against the requested
camera to within 0.01 px. Float readback is recorded separately from the frozen
camera spec. The renderer uses deterministic one-sample CPU Cycles for this small
diagnostic pass; it is not a photorealistic quality render.

The workflow should populate `scene.json.reconstruction_source_sha256` from its
actual accepted reconstruction input ledger. When absent, the adapter conservatively
counts every protocol source as used, so a heldout claim fails. This avoids
inventing independence from the protocol's role labels. The adapter currently
generates masks only: requested landmarks remain missing and fail until an
evaluated vertex/part binding exporter is added. Do not remove landmarks from a
previously frozen protocol just to obtain a passing score.

Run the renderer integration check in a separate Blender process:

```sh
blender -b -P tools/test_blender_geometry_feedback.py -- /remote/evidence/new-renderer-test
```

It checks a known projected plane with an undeclared foreground occluder, an
absent entity, binary image values, actual camera projection and unchanged input
blend bytes. The visible target should have about 200 pixels rather than the 400
pixels it would have if the occluder were incorrectly hidden.

```json
{
  "schema": "real2sim.geometry-feedback-candidate/1.0",
  "protocol_sha256": "REGISTERED_CANONICAL_PROTOCOL_DIGEST",
  "model": {"path": "scene.blend", "sha256": "ACTUAL_MODEL_HASH"},
  "reconstruction_source_sha256": ["ACTUAL_SOURCE_HASH"],
  "views": [{
    "id": "source_0000",
    "camera": {
      "image_size": [640, 480],
      "position": [0, 0, 0],
      "rotation_world_to_cv": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      "focal_px": 500,
      "principal_point": [320, 240]
    },
    "render": {"path": "source_view.png", "sha256": "ACTUAL_RENDER_HASH"},
    "objects": [{
      "id": "cabinet",
      "mask": {"path": "rendered-cabinet.png", "sha256": "ACTUAL_RENDERED_MASK_HASH"},
      "landmarks": [{"id": "front_corner", "xyz": [-0.08, 0.04, 2.0]}]
    }]
  }]
}
```

Supply evaluated world-space landmark coordinates from the saved geometry. The
evaluator projects these itself using the frozen camera; it does not accept
candidate-supplied 2-D coordinates. Use stable vertex/part identifiers and have
the renderer export their coordinates, avoiding manually invented correspondences.

Alternatively, use one entity RGB ID image per view. Add these fields to that view
and omit all per-object candidate `mask` fields:

```json
{
  "id_image": {"path": "entity_ids.png", "sha256": "ACTUAL_ID_IMAGE_HASH"},
  "palette": {"cabinet": [17, 61, 149]}
}
```

Colors are exact integer RGB labels, unique and nonblack. Black is background;
unknown or antialiased colors fail rather than silently disappear. Freeze/export
the renderer's palette, use lossless images, and disable color management and
antialiasing for the ID pass. Candidate object records are still used for landmark
coordinates. The palette can supply mask-only objects without a duplicate object
record. Unknown object/view/landmark IDs fail the relevant scope rather than
expanding or replacing the predefined denominator.
The palette itself may include other scene entities so an existing full-scene ID
pass can be used without deleting occluders. Their IDs are explicitly reported as
`unscored_palette_entities`; they do not create additional evaluated objects.

## Interpretation and failure accounting

- Green outlines/circles are source observations; magenta outlines/crosses are
  candidate projections. White outlines coincide. Yellow segments connect
  corresponding landmarks. Inspect the image alongside its JSON status: an
  overlay does not override a failed hash or source-binding check.
- Contour mean is half the source-to-render boundary mean plus half the reverse
  boundary mean, using Euclidean nearest-pixel distances. This avoids weighting
  the direction with a longer perimeter more heavily. Boundary maximum is also
  reported. IoU is intersection / union of visible foreground pixels.
- Positive centroid `x` means the candidate is right of the source; positive `y`
  means below it. A bounding-box scale of 2 means twice the source width/height.
  These are image-space clues, not prescriptions to move a particular world axis.
  Camera errors, object shape, depth and occlusion can produce similar residuals.
- Missing objects, views, files, hashes and landmarks remain in the original
  denominator. Invalid rows receive IoU 0 and image-diagonal error penalties for
  their declared measurements. Means include those failures. A view with no
  declared heldout observations reports zero expected objects and null metrics,
  never a heldout success score. No in-sample and heldout scores are pooled into
  a claimed independent accuracy number.

`fit` observations may guide revisions. `heldout` observations must not have been
used to fit cameras, geometry, select a candidate or choose thresholds. Once an
agent sees heldout errors and adjusts the model, that split becomes development
data and a new sealed split is needed for final assessment. The code rejects
the same source hash in both roles and declared use of heldout source images.
It cannot establish that the supplied usage declaration is truthful, detect every
near-duplicate frame/processed derivative, or prove renderer execution solely from
a hash manifest. Enforce the split in the workflow input allowlist and sealed
evaluation process. Camera pose for an unseen view needs independent calibration;
fitting it on the evaluated target points would make those residuals in-sample.

## Workflow integration

1. At `agent_observe`, review visible object masks and landmark identities; freeze
   scope, source hashes, camera parameters and thresholds. Camera fitting still
   precedes this freeze. Keep heldout annotations outside reconstruction packets.
2. At `build_geometry`, export the entity ID pass (or per-object masks), evaluated
   landmark coordinates, actual render camera, model/render hashes and candidate
   manifest from the executable renderer. Preserve the complete room shell and
   normal occlusions. Match `render_binding.json`'s model and image hashes.
3. Run the evaluator and attach its JSON plus overlays to `agent_review_geometry`.
   Route systematic projection error to calibration, and local silhouettes to
   the responsible geometry stage. Retain the original human/agent checks for
   supports, occlusion, part structure and room completeness.
4. Compare baseline and candidate using the exact same registered protocol and
   complete results, retaining failures and runtime costs. Evaluate sealed views
   only after freezing the chosen candidate. These diagnostics supplement the
   existing quality gates; they do not replace independent visual/physics review.

The evaluator is available as a standalone tool and Python API. `build_geometry`
and `build_render` also support opt-in execution after their normal render:

```json
{
  "stages": {
    "build_geometry": {
      "parameters": {
        "blender": "/remote/runtime/blender",
        "geometry_feedback_protocol": "/remote/case/frozen/geometry-protocol.json",
        "geometry_feedback_protocol_sha256": "REGISTERED_CANONICAL_PROTOCOL_DIGEST"
      }
    }
  }
}
```

Use the same two geometry parameters under `build_render.parameters` to run the
check there too. Preserve the other required stage parameters in the existing
configuration. These reconstruction stages reject any protocol view whose role
is not `fit`. They retain `geometry_feedback/report.json`, `candidate.json`,
protocol snapshot, masks and overlays as stage artifacts. Failed numeric scores
remain failed feedback for the review/revision stage; execution completing does
not make geometry acceptable. Reviewers must resolve failed declared thresholds
or explicitly correct and refreeze demonstrably invalid observations, not ignore
the report. A malformed protocol or renderer failure stops executable work.

The protocol snapshot's relative artifact paths still refer to the original
protocol directory recorded as `protocol_original_path` in the report. Re-run
against that original frozen protocol and retain its referenced images/masks;
the copied JSON alone is not a portable artifact bundle. No historical case is
relabelled. Real-scene A/B evaluation remains the next acceptance step.
