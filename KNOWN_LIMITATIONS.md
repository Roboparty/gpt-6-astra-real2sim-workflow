# Known limitations of this public preview

This release consolidates the native generation flow, historical examples and measured research checks. It does not include the proposed `quality_v3` redesign or establish a newly accepted room reconstruction. See the [2026-09-30 integration record](docs/RELEASE_20260930.md).

The integrated 2026-09-29 research work adds structural shell collision fixes, optional
fixed-camera geometry feedback, source-bound physical priors and task-trace
evaluation. See [the measured development results](docs/research/RESULTS_20260929.md).
These additions are not a new accepted room reconstruction or a SOTA result.

| Area | Current limitation |
|---|---|
| Generation entry | `tools/rebuild_artifacts.py` is a frozen recipe for the supplied photograph. New scenes need new observations, fitting and modelling; changing only the image path is insufficient. |
| Agent access | Agent stages require an operator or a configured `agent_command`. There is no bundled Astra inference service or completed automatic model-routing client. |
| Furniture specifications | Dimension-prior fitting code exists, but the example uses common priors. Automatic SKU search, universal CAD import and a measured specification-uplift benchmark are absent. |
| Small/empty assembly sets | Single-part and explicit zero-furniture fixtures pass structure, canonical static engine and three-format reload checks. The empty-room path requires a complete shell, fixed luminaires, one mesh per semantic object and no instances. These synthetic checks do not establish full Agent visual acceptance or arbitrary scene support. See [interchange evidence](docs/research/UPDATE_20260929T1346.md). |
| Mesh audit | Intended for the closed components in this example; intersection screening and signed-distance sampling are not an exact proof for every arbitrary mesh. Visual review remains necessary. |
| Freeze and evidence | `freeze()` requires every configured stage, including validate/report and applicable reviews, to remain valid. Hash consistency does not itself prove physical truth. |
| Cache granularity | Any Python/Markdown change under `workflow/r2s` changes the implementation fingerprint for every stage. Current reuse is conservative, not object-level incremental execution. |
| Export cost | Default delivery export includes a doubled-resolution, 128-sample render. Explicit `--interchange-only` skips presentation/ID renders for file diagnostics and is not complete visual delivery. |
| Portable appearance | The detailed room becomes visibly different in GLB/USD under the same native rig. Removing the imported floor Normal connection improves USD but worsens GLB; no universal repair is enabled. The GLB all-vertex bound failure from nonsurface source points remains separately recorded. |
| Interchange and physics | GLB requires extra intrinsics for the off-axis camera; shading can differ across formats. Mass/material/gap values are assumptions and the loading demonstration is finite-duration. |
| Structural collision | Canonical shell export supports axis-aligned rooms with explicit rectangular wall openings. Arbitrary wall proxy overrides are rejected until coverage validation exists. Window panes and frames remain separate collision geometry. |
| Geometry feedback | Automatic Blender feedback exports opaque visible masks. Automatic evaluated landmark bindings, transparent-object mask semantics and independent real 3-D measurements remain unresolved. |
| Numerical priors | Contact presets are explicit and compiled values are audited; density and PBR values are source-bound references for authors, not automatic changes to fitted masses or shaders. |
| Task evaluation | The container-task evaluator is tested with synthetic traces; no new robot controller or real-room manipulation success has been established. |

These limitations are retained rather than silently changing the already verified implementation during a presentation release. New generality, efficiency or accuracy claims require corresponding tests and experiments.

中文摘要：本版保留已验证案例与执行快照，不包含新的通用生成器、自动型号服务或 `quality_v3` 重构。单物体／空家具集合、冻结门槛、缓存粒度和导出成本仍有上述边界；现有三件家具案例通过不代表所有输入已覆盖。请同时阅读 [能力说明](public_contract/CAPABILITIES.md) 和 [结果](docs/example/RESULTS.md)。
