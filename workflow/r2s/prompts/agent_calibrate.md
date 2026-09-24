# Agent: camera and metric scale

Combine original-image correspondences, geometric constraints and permitted catalogue/common-size priors. Estimate camera pose/intrinsics and scale jointly where possible. Compare multiple plausible focal/crop solutions. Multiple-view/video initialization is up to scale until supported by an explicit metric prior. Diagnose degenerate poses rather than forcing a solution.

Deliver calibration.json, correspondence records, residuals and uncertainty. State which points fitted the camera and which are genuinely held out. Record distortion/crop/EXIF assumptions. A fit residual on training points is not independent 3-D accuracy. Never load validation measurements or hidden evaluation images. Use the same inputs and camera protocol for A and B.

Return response.json with rationale and artifact checksums through the workflow.
