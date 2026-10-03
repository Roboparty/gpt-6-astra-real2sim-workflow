# Source-constrained ETH3D repair

This experiment repairs the OURS candidate from [the frozen comparison](../eth3d_workflow_comparison_20261003/README.md). Read [protocol.json](protocol.json) before using its results. The eight previously heldout images are now an exposed-test diagnostic, not a new independent test.

Selected candidates are `geometry_v4` (SHA `506982c1…5542`) and `texture_v4` (SHA `f36a6b79…bb2f`). Both remain **LIMITED**. The actual native geometry review is `changes_requested`; the texture audit retains 75 soft-world errors across 45 objects. Code tests and improved scores do not override either result.

- `geometry/`: actual shell and component repair recipes; preserves editable objects, cameras and original source annotations.
- `texture/`: source-photo surface projection and texture diagnostics. Unsupported texels retain original material appearance. Photo-derived colour includes captured illumination and is not intrinsic albedo.
- [Report](../../docs/research/ETH3D_REPAIR_20261003.md) and [evidence](../../docs/research/evidence/eth3d_repair_20261003/).

Large `.blend` files, packed atlases, source photos, predicted depth, laser data and full structural audits stay on the remote machines. Evidence receipts identify their exact paths and hashes. A stable/frozen candidate may still fail native acceptance; rejected candidates and diagnostics must not be promoted by the existence of render or score files.

## Frozen-candidate evaluation

Run the same Blender evaluator used for the original comparison, once per immutable model. It rejects a model whose hash differs from its freeze receipt and requires a new output directory:

```bash
blender -b --python tools/evaluate_agent_scene_blender.py -- \
  --model /remote/models/VARIANT.blend \
  --freeze /remote/freeze/VARIANT.json \
  --truth /remote/eth3d/benchmark_v1/evaluation \
  --out /remote/evaluation/VARIANT
```

Aggregate without changing any candidate or ground-truth domain. `depth_math.py` must be the pinned AWSM source identified in the original comparison report; it is not reimplemented here.

```bash
PYTHONPATH=workflow python tools/summarize_eth3d_repair.py \
  --root /remote/evaluation \
  --truth /remote/eth3d/benchmark_v1/evaluation \
  --depth-code /remote/pinned/depth_math.py \
  --variants baseline geometry_v4 texture_v4 \
  --out /remote/repair_metrics.json

python tools/prepare_eth3d_repair_appearance.py \
  --root /remote/evaluation \
  --variants baseline geometry_v4 texture_v4 \
  --out /remote/appearance_pairs
```

Use `tools/score_lpips_pairs.py --help` for the actual pretrained LPIPS runtime and weight-receipt arguments. Pair manifests bind image bytes by SHA-256. The preview includes fixed views; the full sheet retains all eight exposed-test views.

The nonrectangular room declares `bounds_only` and `mesh_only`. Native MJCF export intentionally refuses a rectangular fallback. Mesh topology checks do not establish dynamics or physical-task success.

The texture [delivery receipt](texture/evidence/final_v4/final_delivery_receipt.json), [remote replay commands](texture/evidence/final_v4/replay_commands.json), [allowed-source hashes](texture/evidence/allowed_sources.json) and [code validation receipt](texture/evidence/per_node_regression_receipt.json) preserve the actual implementation and runtime boundaries. The appearance tests are readable under `texture/evidence/source/`; no model or texture archive is included in Git.
