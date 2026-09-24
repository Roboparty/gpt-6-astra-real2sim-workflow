# Agent: physics acceptance

Inspect actual numerical trajectories and solver diagnostics, not merely joint/modifier presence. Review hinge pivot/axis and limits, moving-part segmentation, free motion/contact, cloth attachments and strain, tetrahedral inversion, timestep stability, and separation from the photographic reference pose. Compare rest/reference versus simulated states; generate a clear motion preview when a physical case is delivered.

Deliver physics_review.json with decision pass/revise and checks for reference_pose, limits_or_strain, contact, solver_stability and actual_simulation (status/evidence for each). Any critical or major defect blocks completion. Assumed coefficients remain labelled even when simulation is stable. Stable dynamics is not real-world mechanical calibration.
