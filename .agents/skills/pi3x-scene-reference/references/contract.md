# Pinned reference contract

Official code: [yyfz/Pi3](https://github.com/yyfz/Pi3/tree/9fa3ddb3f8d53041f8b2738df404f62223bbaa7b), commit `9fa3ddb3f8d53041f8b2738df404f62223bbaa7b`. Code BSD-3-Clause. [Pi3X weights](https://huggingface.co/yyfz233/Pi3X) revision `bb1deea4d7423de5b30691739cb451a3f57dc1d5`, CC BY-NC 4.0; do not treat this research weight as commercially licensed. SHA256 `69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a`, bytes 5,440,325,620. No third-party code or weights are bundled here.

Freeze config (paths relative to config):

```json
{"preprocessing":{"resize":"none","crop":"none","color":"RGB","tensor":"float32_0_1"},"frames":[{"id":"f0","path":"frames/0000.png","pts_seconds":0.0,"role":"fit"},{"id":"f1","path":"frames/0001.png","pts_seconds":0.1,"role":"heldout"}]}
```

Use actual retained frame PTS, never frame index/fps when variable-rate timestamps exist. Hash the parent video and extraction command in the experiment's source ledger. The adapter verifies frame bytes and dimensions, but does not verify extraction timestamps against the video. Preprocessing is a recorded contract, not an implementation: a backend must reproduce and attest it, including resize dimensions, crop and transformed intrinsics. `none` is only suitable if the input sizes already satisfy the backend. No resizing or subsampling happens in this adapter.

Consumer requires raw floating NPZ arrays (`allow_pickle=False`): `points` and `local_points` [1,N,H,W,3], `conf` [1,N,H,W,1], `camera_poses` [1,N,4,4]. N is the exact ordered fit subset. Heldout frames must not enter this run. The inspected Pi3X model outputs raw confidence logits; apply sigmoid once. Do not apply sigmoid twice based on a generic README or export from another backend. `camera_poses` are OpenCV right/down/forward camera-to-world; point consistency and rotation validity are checked. Intrinsics are not an output of this adapter. Keep supplied intrinsics and preprocessing transforms separately; do not derive an invented focal length.

Provenance JSON keys: `input_sha256`, `npz_sha256`, `code_revision`, `weight_revision`, `weight_sha256`, `preprocessing` (exact manifest value), `frame_ids` (fit order), `kind` (`synthetic_contract` or `backend_output`). A backend output also requires `run_receipt` pointing to retained logs. Consumer checks declarations and numerical consistency; it does not independently attest that the model produced the arrays. Inspect logs/checkpoint loading/return code and actual runtime before reporting inference success.

For future inference, use the pinned official `Pi3X` forward API and save all outputs before confidence filtering. The shipped upstream example principally writes PLY, so PLY alone is insufficient for this consumer. A generation wrapper must retain dense points/local points/conf/camera poses, preprocessing, seed, effective dtype, checkpoint strict-loading evidence, duration, peak memory and errors. That wrapper and real forward pass remain unverified here.

Coordinate conversion to Blender requires a recorded global world alignment and scale fit; for camera axes use the OpenCV-to-Blender camera basis diag(1,-1,-1,1) composed on the right of C2W. This basis change alone does not establish Z-up world alignment or metric accuracy. Compare transformed landmarks and camera projections; never call approximate predicted scale measured scale.
