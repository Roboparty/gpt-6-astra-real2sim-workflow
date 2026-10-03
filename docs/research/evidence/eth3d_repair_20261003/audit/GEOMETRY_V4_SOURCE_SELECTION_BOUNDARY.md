# Geometry repair v4: source-selected LIMITED candidate

Frozen model SHA-256: `506982c1c94a94067b19a58dc1a55d7b9ab6039ca1b8d00f61fba76292cc5542`.

The fixed ten allowed source views were independently inspected. The lumber cart and cages are visible again in inputs 24/28; the giant-pipe gray obstruction is gone in 20/32/35. Input12 retains visibly approximate vehicles and an underfit dark/blue background region. This supports a **LIMITED source-selected candidate**, not full-scene visual certification.

## Pipe and control checks

All three repaired pipes now have evaluated world extents approximately **20.20 × 0.11 × 0.11 m**, X bounds **[-15, 5.2] m**, and Z bounds **[4.185, 4.295] m**. Their radius/height are restored rather than hidden. Camera/gauge/source-label/threshold checks, material/light/render/visibility parity, the planned floor union and garage aperture checks remain unchanged and pass their inspected scope.

There are **five**, not four, remaining external landmark occlusions. All five were also externally occluded in the original frozen baseline. Four retain the same column/platform blocker; the far-cage point's blocker changes from `cage1_rail1` to `cage_upper_wall`. These remain unresolved annotation/geometry visibility conditions; inherited status is not a waiver. No camera-inside candidate was found by the performed screen.

## Full source-reference regression, without GT

The 36 input RGB hashes, DA3-reference hashes, per-view domains and actual reference arrays match the original frozen baseline. The full denominator is **689,349** learned-depth reference pixels.

- Equal-view macro conditional AbsRel: **7.77340% → 6.66114%**; 30 views improve and 6 regress.
- Worst AbsRel regression: input12, **+1.24869 percentage points**.
- Macro 30m missing-penalty error: **0.53355 m → 0.50562 m**; 22 improve and **14 regress**.
- Missing predictions: **415 → 1120**.

The 30/6 count therefore describes conditional AbsRel only. It does not erase coverage loss or the fourteen missing-penalty regressions. All outcomes remain in the independent JSON evidence. These values use only allowed input RGB/DA3 and are not GT scores.

## Selection boundary

The author selected v4 after inspecting all ten source views and retaining the tradeoffs. Do not revise it based on later exposed-test results. The v3 geometry/texture visual rejection and earlier structural failures remain preserved. Full native Workflow diagnostics and the final v4 texture audit must be reported by their actual outcomes; this document does not predeclare either complete or accepted.

Evidence: `geometry_v4_source_depth_regression_review.json`, `pipe_v4_dimension_review.json`, `geometry_v4_source_visibility_review.json`, `v4_visibility_vs_baseline.json`, and `geometry_v4_control_shell_review.json`.
