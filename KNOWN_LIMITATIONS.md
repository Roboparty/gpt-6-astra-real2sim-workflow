# Known limitations of this public preview

This release packages the verified room example and its execution snapshot. It does not include the proposed `quality_v3` redesign.

| Area | Current limitation |
|---|---|
| Generation entry | `tools/rebuild_artifacts.py` is a frozen recipe for the supplied photograph. New scenes need new observations, fitting and modelling; changing only the image path is insufficient. |
| Agent access | Agent stages require an operator or a configured `agent_command`. There is no bundled Astra inference service or completed automatic model-routing client. |
| Furniture specifications | Dimension-prior fitting code exists, but the example uses common priors. Automatic SKU search, universal CAD import and a measured specification-uplift benchmark are absent. |
| Small/empty assembly sets | The current review rejects an empty inter-assembly check list, including a single-assembly scene. The diagnostic renderer also expects nonempty furniture landmarks. These cases need adaptation; do not add invented objects to bypass the checks. The three-furniture example does not exercise these edge cases. |
| Mesh audit | Intended for the closed components in this example; intersection screening and signed-distance sampling are not an exact proof for every arbitrary mesh. Visual review remains necessary. |
| Freeze and evidence | `freeze()` explicitly requires `validate`, then includes other valid stages. Operators must additionally ensure every required final review is complete. The published example has actual records for all 18 stages. Hash consistency does not itself prove physical truth. |
| Cache granularity | Any Python/Markdown change under `workflow/r2s` changes the implementation fingerprint for every stage. Current reuse is conservative, not object-level incremental execution. |
| Export cost | Export currently includes a doubled-resolution, 128-sample render. Export and presentation rendering are not yet fully decoupled. |
| Interchange and physics | GLB requires extra intrinsics for the off-axis camera; shading can differ across formats. Mass/material/gap values are assumptions and the loading demonstration is finite-duration. |

These limitations are retained rather than silently changing the already verified implementation during a presentation release. New generality, efficiency or accuracy claims require corresponding tests and experiments.

中文摘要：本版保留已验证案例与执行快照，不包含新的通用生成器、自动型号服务或 `quality_v3` 重构。单物体／空家具集合、冻结门槛、缓存粒度和导出成本仍有上述边界；现有三件家具案例通过不代表所有输入已覆盖。请同时阅读 [能力说明](public_contract/CAPABILITIES.md) 和 [结果](docs/example/RESULTS.md)。
