# Agent: editable geometry and invisible completion

Use visual/spatial reasoning to author geometry suited to this scene. Deliver a packed model.blend plus scene.json conforming to real2sim.scene/1.0. Stable semantic roots, metre units, Z-up, named camera source_camera, object provenance and confidence are required. The six shell meshes must be named floor, ceiling, wall_back, wall_front, wall_left, wall_right, opaque and retained in every generation. Model all observed luminaires. Create complete backs, legs and support structures with hypotheses explicitly recorded.

Agent modelling may use custom Blender/Python code, reusable parametric builders, or editable primitive assemblies. Provide builder source and all required textures/assets as output artifacts. An unsupported furniture category is a request for custom geometry, not permission to paste a similar stock object. Source-derived planar art/textile appearance is allowed when documented; never use a room-wide billboard as reconstructed geometry.

A builds furniture geometry independently from image/spec priors. B may replace only verified exact asset components while retaining the same scene placement; otherwise copy A and log fallback. Keep catalogue body dimensions distinct from decorated assembly bounds. Geometry/appearance corrections need observed evidence. Generative layout repair may report conflicts but must not move evidence-backed objects.

Return response.json. Do not mark complete merely because Blender saved a file.

## Mandatory assembly evidence

Read the accepted furniture_observation.json from the observation stage; carry its exact bytes/hash into the model artifacts. It must assign visible parts to furniture, distinguish observed/partial/hidden landmarks and record alternative interpretations. Do not separately ray-fit surfaces, back rails and feet and join them only by screen proximity. Fit a coherent local furniture frame with shared dimensions, parallel/symmetric members where supported, and a connected load path. Hidden joinery may use labelled priors.

For quality_v2 deliver scene.structure using real2sim.assembly/1: one owner per part, actual Blender object name, explicitly declared joint pairs with a shared world-space anchor/tolerance, floor supports and source observation IDs. The assembly graph must be connected. Store actual fit residuals separately from room/camera residuals, and bind model_version consistently in scene and response.parameters. A layout lock is not a structural certificate. Do not add arbitrary joints to whitelist a visually erroneous crossbar or intersection.

When surface_contract_version >= 1, also follow surfaces.md; source-bound surface artifacts and front/raking review are mandatory.
