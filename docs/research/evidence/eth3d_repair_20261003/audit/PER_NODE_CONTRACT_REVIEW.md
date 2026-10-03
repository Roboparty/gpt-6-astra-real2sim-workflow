# Per-node appearance contract: stable implementation review

Verdict: **PASS for the tested contract extension and regressions**. This is code validation, not acceptance of a frozen texture asset.

Stable source hashes:

- `appearance.py`: `f2126376eaa165a13f973e610895045f7ab93d4b8d149b4a74e30aeeefddc57c`
- `blender_appearance.py`: `cd8f3701bf5e930cb3a2b0c1f1d85eec00320079e4598ce4fda3497fa3a09dee`

Read review confirms exact material/node-key coverage, rejection of missing/extra coordinate fields, actual graph coordinate tracing, named and noncollapsed evaluated UV requirements, unchanged soft-surface UV-only rules, and rejection of active shader groups. Legacy single-mapping declarations remain supported. Material snapshot equality still protects the lighting-only stage.

Independent validation on these hashes:

- Existing appearance metadata contract regression: passed, including failed-audit rejection and persistent fixed comparison bindings.
- Existing actual Blender regression: passed, including legacy UV/world rejection, repetition bounds, collapsed UV, omitted assignments, material/lighting lock and equality of actual fixed-view rendered pixels.
- Sixteen actual Blender per-node cases were rerun in a new reviewer directory: passed, including expected rejections for missing/extra nodes/materials, wrong UV/world, extra fields, groups, soft-world mapping and implicit-render-UV mismatch; explicit and two-named-UV positives remain valid.
- Eleven independently written metadata cases: passed.
- The frozen diagnostic texture asset was not changed. Its adapted per-node audit still retains **75 soft-world failures**. The extension does not turn that asset into a native appearance pass.

## Independently found implicit-UV bug and verified correction

The inherited check used the UV editor's active layer instead of the shader's render-active layer. A real Blender fixture set editor-active `DeclaredUV`, render-active `RenderUV`, and used `Texture Coordinate.UV` for the image. The old audit incorrectly passed a `DeclaredUV` declaration; actual implicit rendering exactly matched explicit `RenderUV`, not explicit `DeclaredUV` (linear RGBA MAE 0.11725).

The final implementation rejects this case with `Implicit UV reads a different render-active map`. The same actual rendered pixel comparison was repeated and confirms the distinction. Empty-name UVMap cases are also rejected when they use the wrong render-active layer; explicit named UVMap nodes remain independent of editor/render selection.

Evidence is under `audit/per_node_contract/`. Full reviewer scripts/logs remain at `4090-1:/home/wqz/real2sim_agent_repair_20261003/reviewer_guard/per_node_review/`. No main source was edited by this reviewer and no frozen model was resaved.
