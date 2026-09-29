# Explicit empty-furniture structural route — 2026-09-29

One implementation candidate now supports **zero furniture assemblies with a complete room shell and fixed luminaires** through canonical scene validation, an actual Blender structural audit/source-view render, bound structural review, and geometry-only export. This is a synthetic workflow regression, not a real-image reconstruction result, complete delivery acceptance, robot task, or SOTA comparison.

## Explicit declaration and retained gates

Use `structure.schema="real2sim.assembly/1"`, `scope="empty_room"`, and `assemblies=[]`. `shell_objects` is a unique nonempty list of shell mesh names; `fixed_luminaire_objects` lists fixed lamp meshes. The lists are disjoint. The semantic `scene.objects` must cover these names exactly once with `structural_role` equal to `room_shell` or `fixed_luminaire`. The Blender mesh has the same name and matching `geometry_role`. Furniture/part tags are forbidden on these objects.

This deliberately narrow path requires one mesh per semantic object. It retains the existing canonical scene requirement for luminaires and the exporter's requirement for all six enclosure surfaces. Zero assemblies without the explicit scope are rejected. Nonempty assembly ownership, joint measurement, landmark, support, and cross-assembly coverage gates remain unchanged.

The empty-room evaluator checks every geometry object, including hidden objects, against the inventory. It rejects unlisted geometry, hidden shell geometry, wrong roles, furniture/part tags, non-mesh geometry, empty/nonfinite meshes, collection/dupli instances, and evaluated instances including Geometry Nodes instances even when `object.instance_type == 'NONE'`. This is inventory/representation validation; it cannot independently determine that an author-tagged mesh visually depicts a wall rather than furniture.

The renderer records the full camera frame as `source_crop_xyxy` so the existing stage worker can produce its original-image comparison crop. Structural review still requires the current model/scene/audit hashes, exact per-object rows, an explicit passing `checks.empty_room` finding, and hash-bound `furniture_source_view.png`. A measurement-only `R2S_STRUCTURE_NO_RENDER=1` audit cannot satisfy review.

## Actual run and failure retention

Remote root: `4090-1:/home/wqz/real2sim_capability_20260929`.

- `runs/empty_room_001.log`: retained deployment failure. Script was initially copied outside `repo`, so import failed before fixture generation. No model acceptance or positive evaluation occurred. No candidate logic was changed to repair this; the same code was deployed under `repo`.
- `runs/empty_room_002`: one actual positive fixture with six closed box shell meshes and one fixed ceiling lamp. Blender 4.5.3 used CPU with two threads; no GPU inference or separately billed API.
- Canonical scene validation: 7 objects, 6 enclosure surfaces, 1 luminaire; passed.
- Structural audit and bound source-view review: 0 furniture assemblies and 0 furniture component/interassembly pairs; passed.
- Existing geometry-only exporter: all 7 entities exported and all 6 required enclosure surfaces retained; passed.
- Seven negative checks passed: implicit zero-assembly scope, omitted semantic object, wrong semantic role, missing explicit review, no-render review, actual hidden undeclared furniture, and actual Geometry Nodes instances.
- Existing single-part contract suite: 31 checks passed. Existing single-assembly suite: 21 checks passed. These are contract regressions, not additional physical experiments.

The complete positive-plus-negative Blender driver measured **3.656214235 seconds CPU wall time**. Failed initial import and contract-regression CPU wall times were not instrumented separately and remain unknown; they are not recorded as zero. The enclosing first deployment/SSH tool call took 3.9093817 seconds (includes transfer overhead); the enclosing regression/SSH tool call took 1.0571052 seconds. One implementation candidate and one actual positive fixture were used; negative mutations do not replace or remove the positive denominator. Cumulative GPU usage added: 0 hours. Large/Blender artifacts remain remote.

## Evidence and limits

[Summary with source and implementation hashes](evidence/empty_room_20260929/summary.json), [actual structural audit](evidence/empty_room_20260929/structural_audit.json), [initial deployment failure](evidence/empty_room_20260929/deployment_failure.log), [single-part regression](evidence/empty_room_20260929/single_part_regression.txt), [single-assembly regression](evidence/empty_room_20260929/single_assembly_regression.txt).

This run did not execute the entire agent pipeline, GLB/USD interchange export, MuJoCo simulation, shell collision/opening acceptance, real-image fitting, or human visual reconstruction review. Their existing gates remain required. Multi-mesh semantic shell/lamp ownership, non-mesh shell geometry, and any generated instancing are deliberately unsupported in this narrow path. No physical accuracy, zero-shot generalization, or scene-level success claim follows from this synthetic fixture.
