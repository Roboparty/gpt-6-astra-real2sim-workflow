# Whole-scene appearance contract (version 1)

Applies when `packet.refinement.limits.appearance_contract_version >= 1`. Observe the full original, then complete objects/regions, then local details. Every local edit must return to full-object and full-scene review. Technical completeness is not visual fidelity.

## Observation

In `observation.json`, deliver `appearance_source` and the existing `appearance_targets`. Every target crop covers the **entire visible object or coherent architectural region**, not an isolated texture patch. Add `whole_object:true`, `soft_surface:true|false`, and `appearance:{palette,pattern_layout,direction,scale_evidence,uncertainty}` with concrete source-grounded descriptions. A bed can include its bedding and small accessories; architecture can be subdivided into floor, ceiling, walls, openings, etc. Use stable canonical scene entity IDs.

Add `scene_appearance:{global_palette,light_distribution,contrast_hierarchy,uncertainties,coverage}`. `coverage` has exactly `architecture`, `openings`, `furniture`, `soft_objects`, `reflective_surfaces`, `lighting`, `exterior`. Each entry is `{entities:[target IDs]}` or `{entities:[],absent_reason:"specific reason"}`. A target may have several roles. Every target must have a role. Inspect the full image to find missing regions; do not mark a visible floor/window/board absent merely to avoid its review. Hidden surfaces remain labelled hypotheses; completeness does not establish their accuracy.

## Materials

Use the accepted whole-object colour and macro pattern distribution before choosing fine texture. A local sample constrains only its observed support by default. Shadows, folds, reflected windows, dirt and occlusion must not become global albedo motifs. Treat macro albedo, microscopic weave/roughness, geometric folds and illumination separately.

When the complete pattern is unobservable, an original-wide, licensed, generated or grounded procedural texture is permitted. Preserve observed palette, motif scale, distribution and direction; keep unsupported completion restrained and labelled. This is inferred appearance, not measured albedo. Do not copy prior V5 scene assets into an independent reconstruction.

Extend `material_calibration.json` with `appearance_source_sha256` and `observation_sha256`. Cover every observed target and every actual visible material assignment, including hidden-shell materials. Each material row retains `entity`, `texture_scale_m`, `evidence`, `uncertainty`, and adds:

```json
{
  "entity": "bed",
  "material_names": ["cotton"],
  "objects": ["quilt"],
  "soft_surface": true,
  "material_class": "dielectric",
  "parameter_basis": "Matte cotton prior; original has no metallic highlights",
  "pbr_parameters": {"cotton": {"Roughness": 0.93, "Metallic": 0.0}},
  "layers": {
    "macro_pattern": "Sparse pale botanical print across the complete duvet; inferred completion",
    "microstructure": "UV-mapped fine weave, independently scaled",
    "folds": "Broad asymmetric drape in geometry; not baked into the colour map",
    "illumination": "No source shadows baked into albedo; residual ambiguity recorded"
  },
  "whole_object_evidence": ["whole_duvet_source.png", "whole_duvet_neutral.png"],
  "texture_scope": {
    "source_kind": "generated",
    "application": "whole_object",
    "mapping": "uv",
    "uv_map": "FabricUV",
    "uncertain_completion": "Unseen print arrangement is inferred with restrained contrast"
  }
}
```

`material_class`: `dielectric|metal|mixed|emissive`. Actual shaders must use one active Principled BSDF. Report actual `Roughness` and `Metallic` per bound material, or `"linked"` for connected inputs. Glass, paint, cloth and ordinary wall finishes are dielectrics: do not make them metallic to force a highlight. Mixed materials require a concrete explanation. Distinct material names/objects may use separate rows for one entity. Unobserved entities require `inferred_surface_reason`. Object ownership uses `entity_id`, then `furniture_id`, then object name. No visible assignment may be omitted.

`source_kind`: `original|procedural|licensed|generated|constant`; `application`: `local|whole_object|tiled|constant`; `mapping`: `uv|object|world|none`. Only constant surfaces use `none`. Original-derived textures specify `sample_boxes` as integer xyxy boxes in the bound original. Extending an original sample to the whole object, or declaring any tiling, requires at least two non-overlapping `repetition_boxes` in that original plus `repetition_basis` explaining observed repetition and physical scale. A rectified map of the complete observed object (for example, planar artwork) may instead use source_extent:whole_object, with a single sample box covering the entire accepted target crop; this does not justify hidden-surface extrapolation. Two arbitrary crops do not constitute semantic proof. If there is insufficient evidence, keep the sample local or use labelled restrained completion; do not manufacture evidence or inflate confidence.

For image nodes use `EXTEND` or `CLIP` for local and whole-object maps; `REPEAT` needs a justified tiled declaration. The object list defines the allowed application support. Split/localize surfaces when necessary, rather than assigning a local sample to an entire assembly. Soft surfaces must have a named noncollapsed evaluated UV map and actual UV-driven textures, including their fine weave. Texture coordinates must move with the fabric. The executable auditor rejects world-position/Generated coordinates falsely declared as UV, missing maps, unsupported shader groups and unreviewed assignments. Currently complex shader groups require an explicit audit adapter; do not bypass the audit with a declaration.

Every material row declares `soft_surface:true|false`. Separate rigid wood and soft cloth rows within a mixed bed assembly; an observed soft target needs at least one soft material row. Actual Cloth/Soft Body modifiers cannot be declared rigid. Deliver actual `neutral_light_previews` and full-object evidence files. The renderer independently inspects actual nodes and assignments. A schema pass cannot prove correct pattern semantics, UV distortion quality, or separated physical reflectance.

## Lighting

Lock accepted material nodes and assignments. `lighting_calibration.json` adds `material_parameters_locked:true` and `whole_scene_checks:{light_distribution,shadow_direction,reflection_strength,contrast_hierarchy}` with concrete comparisons across the full image. Keep the exposure/albedo gauge recorded. If material interpretation is wrong, request a material-stage revision. Do not fix a bright board by arbitrarily increasing metalness, or fix a dark floor by painting in illumination. At final build, an executable snapshot of the accepted material-stage model is compared with the current actual scene; changes require material revision.

## Persistent comparisons and acceptance

The first executable build records `comparison_protocol.json`: three fixed cameras (`source`, `wide`, `reverse`), raster settings, colour transform, exposure, frame and samples. Later builds render those cameras unchanged as `comparison_source.png`, `comparison_wide.png`, `comparison_reverse.png`, alongside the current fitted source view and adaptive diagnostics. Preserve the initial world coordinate frame. Camera/room/observation revisions do not reset this protocol, the best candidate, or stagnation counters. A different original image belongs in a new case. Legacy cases explicitly using appearance version 0 retain the old protocol and are not new-contract passes.

Add `checks.global_composition` to `appearance_review.json`; final shaded review also adds `material_light_consistency`, `texture_scope`, `soft_shape`. Each is `{status:pass|revise,findings,evidence:[...]}` and must cite the full original and current full source render. The material_light_consistency check also cites the executable full-scene appearance_neutral.png; Agent-authored preview metadata alone is insufficient. Describe low-frequency light/colour distribution and region contrast before details. For soft shape inspect broad uneven folds, drape, supports and whole-object silhouette. Every per-object row adds `whole_object_findings` and `context_findings`. Final review binds `appearance_audit_sha256` to the executable audit; a failed shader/UV/material-lock audit blocks acceptance, but is still available for a rejected review.

The first global-composition review includes all three fixed views. Every subsequent `comparison.before` and `comparison.after` includes **all three** fixed images from the respective candidates, copied to separate names when needed; hash bindings distinguish them. A local improvement cannot justify global regression. Compare both candidates against the original, not just against each other. Missing scene regions or conspicuous repeated motifs/highlights remain blocking issues, not acceptable "single-image limitations". Unknown hidden details may remain explicitly uncertain.

Worse candidates stay rejected; `selected_candidate` continues to reference the saved best model. Preserve all attempts, return to the responsible stage, and re-render before export. Do not overwrite current dependency files with an old model. Budget/stagnation stops return best references with `needs_revision`; they are not completion. Observation revisions cannot silently drop an already reviewed target. Old incomplete candidates must be re-observed/re-rendered under this contract or tested in a fresh case, never relabelled as passing.
