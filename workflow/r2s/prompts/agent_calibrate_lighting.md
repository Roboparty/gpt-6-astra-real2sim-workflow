# Agent: source-image lighting calibration

Infer source direction, window/daylight versus artificial light, emitter extent, shadow direction/softness, lit/shadow ratios, white balance and plausible intensity ranges. Do not substitute a generic studio-light preset for the photographed illumination. Preserve physical luminaires and the complete shell. Unseen emitters are explicit hypotheses; do not invent visible windows just to illuminate the scene.

Use the accepted camera and geometry unchanged. Resolve exposure/albedo ambiguity by fixing one gauge; do not freely vary albedo, exposure and light power together. Start with neutral/known surface assumptions, then alternate light and material refinement under recorded locks. Compare selected source regions, shadow boundaries, highlights, color bias and contrast. Exclude source-projected/baked textures and transient occluders from independent photometric claims.

Deliver calibrated model.blend and scene.json plus lighting_calibration.json containing camera_locked, geometry_locked, exposure_albedo_gauge_fixed, lights, comparison_before, comparison_after, metrics_before, metrics_after and uncertainty. Include per-light parameters and diagnostic images. A wall/camera conflict requires an upstream revision. No major material or lighting mismatch can pass final review merely because rendering/export succeeds.
