# Agent: four-wall, floor and ceiling calibration

Fit actual architectural relationships before furniture detailing. Distinguish external walls, returns, columns, windows, doors and openings; never close a visible window merely to create an easy rectangular box. Cross-check vanishing lines, visible wall/ceiling and wall/floor intersections, furniture contact and any reviewed multiview correspondences. Refine camera and room jointly if needed, then record the revised camera explicitly.

Produce room_calibration.json. Its surfaces must account for wall_front, wall_back, wall_left, wall_right, floor and ceiling. Each needs plane parameters, visibility (observed/partial/unobserved), evidence and status. Visible/partial surfaces need image_constraints and residuals. Unseen surfaces must be hypothesized with uncertainty, not claimed calibrated. Record openings_and_columns_reviewed and explicit opening/column geometry. Keep all six surfaces in every scene generation; do not hide/delete walls for attractive previews.

Provide source-view architectural overlay, top view, four inward wall views and a reverse view. Evidence conflict requests an earlier-stage revision; do not move observed furniture to conceal wrong walls. Complete these checks before geometry freeze.
