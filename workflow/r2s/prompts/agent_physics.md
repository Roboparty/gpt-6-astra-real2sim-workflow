# Agent: optional articulated and deformable components

Read physics_options. All features are off unless enabled. Select actual components and document confirmed versus hypothesized mechanisms. If no suitable target exists, record not_applicable with evidence instead of fabricating a mechanism.

Hinges: segment moving leaf and fixed frame, define moving_body/parent_body, local pivot and axis, radian limits, mass, COM, inertia, damping and friction. Preserve world reference pose when reparenting. Never rotate an entire cabinet as a substitute for a door joint.

Cloth: use reviewed surface vertices/triangles, attachment vertices, mass, contact thickness, stretch/bending assumptions and actual numerical solving. Soft body: use valid tetrahedra, mass/density, Young modulus, Poisson ratio, damping and collision/contact; test inversion and strain. Distinguish photographic reference pose from stress-free rest shape. One photograph does not identify physical material coefficients; mark assumed values and ranges.

The built-in backend emits MuJoCo scene_dynamic.xml separately from immutable scene.xml and records trajectories. Do not call keyframe deformation a physics solution. Blender-specific simulation/cache output requires a separately implemented and verified backend; it is not implied by a MuJoCo recipe.

Deliver model.blend, scene.json with explicit dynamics.hinges/deformables recipes, and physics_setup.json with reference_pose_preserved, parameters_are_measured_or_prior_labelled and target_decisions. For an enabled but inapplicable feature, also write scene.dynamics.not_applicable[feature] with reason and evidence; otherwise validation fails. Only eligible enabled features may be generated. Keep the reconstruction reference pose and A/B layout fixed.
