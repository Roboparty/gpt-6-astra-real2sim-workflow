# Geometry repair v1: rejected, preserved

Frozen model SHA-256: `67b1f48fedcb86e58e43952d630d141d26943902bf7d830b5247c55291bb766b`.

This model is not promoted. The coordinator reported that the actual native object audit found 15 connection failures and 2 binding failures, and the author is producing a new v2 rather than overwriting this candidate.

Independent read-only checks in `geometry_v1_independent_review.json` established:

- Each of the six evaluated shell meshes has zero nonmanifold edges, zero inconsistent-winding edges, zero duplicate faces and positive signed volume.
- All 30 rectangular-grid floor-union cell checks and 133 garage shell-ray checks pass against the declared topology. This verifies implementation of the plan, not physical accuracy of assumed completion.
- Camera metadata, the rigid gauge, all 38 source UV/frame labels and acceptance thresholds match the frozen baseline exactly.
- Surviving-object material assignments and material nodes, all light definitions, render/color/world settings, visibility flags and collection visibility match the baseline. The five removed old partition objects are explicitly reported; no visibility toggle hid the changes.
- Two landmark transports disagree with the actual object transformation: `van_windshield_divider` by 95.636 mm and `car_rear_frame1` by 71.767 mm. These measurements support the identified loss of shear when an anisotropic world affine is assigned through Blender's decomposed object transforms.

The shell pass does not cancel these object/binding failures. No actual scene, model, label, tolerance, or source image was changed by this reviewer. The model hash was unchanged after inspection.

Final v2 review must inspect evaluated vertex geometry, including the handling of bevel/modifier output, and actual landmark/joint distances. A `matrix_world` declaration or source-code claim is insufficient evidence that an anisotropic transformation was realized correctly. The author was asked to supply baseline/candidate evaluated-mesh hashes, transformation/correspondence records, and actual per-part endpoint/contact distances.

Unknown cage depth, hidden corner returns and corridor-terminal uncertainty remain assumptions. Native rectangular simulation remains explicitly unsupported/refused for the mesh-only room; it is not a physical pass.
