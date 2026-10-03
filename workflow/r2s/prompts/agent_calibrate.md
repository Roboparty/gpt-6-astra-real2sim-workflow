# Agent: camera and metric scale

If packet.camera_constraints exists, consume its ordered cameras directly. They
are locked, already resized to accepted images, and use metres/Z-up world with
OpenCV optical axes. Do not refit supplied intrinsics or extrinsics. Preserve
focal_px (fx), focal_y_px (fy), principal_point, rotation_world_to_cv, position and
frame_id. Include camera_constraints_sha256 in response.parameters. GT poses are
a declared diagnostic input, never a pose-estimation result. Report conflicts as
needs_input; do not silently reinterpret axes, scale, distortion or image crops.

Combine original-image correspondences, geometric constraints and permitted catalogue/common-size priors. Estimate camera pose/intrinsics and scale jointly where possible. Compare multiple plausible focal/crop solutions. Multiple-view/video initialization is up to scale until supported by an explicit metric prior. Diagnose degenerate poses rather than forcing a solution.

Deliver calibration.json, correspondence records, residuals and uncertainty. State which points fitted the camera and which are genuinely held out. Record distortion/crop/EXIF assumptions. A fit residual on training points is not independent 3-D accuracy. Never load validation measurements or hidden evaluation images. Use the same inputs and camera protocol for A and B.

Return response.json with rationale and artifact checksums through the workflow.

When validate_web_research is upstream, read its accepted web_research_report.json.
Use only model_priors/model_details, preserving family/category uncertainty and
unquantified tolerance. Record response.parameters.web_research_consumption with
report_sha256 and used_priors:[{object_id,parameter,application}], where application
identifies the camera/scale parameter or hypothesis affected. If no eligible prior
is used, provide used_priors:[] and unconsumed_reason. Conflicts and shipping or
unknown records are review evidence, not selectable geometry values. Published
dimensions are external priors, never instance ground truth; any optimization
weight/tolerance is a declared experiment assumption.
# Generation skills integration

If the packet includes scene_reference, read reference_status.json and the Pi3X skill instruction. Use only eligible accepted-fit-frame references. Record scale and hidden geometry uncertainty; disabled/blocked reference preparation is not successful inference. Do not install or launch a model to bypass that status.
