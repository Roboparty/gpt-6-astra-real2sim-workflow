# Independent whole-scene reconstruction: convergence evaluation

2026-09-26. **Verdict: needs_revision.** The current editable candidate is retained; strict visual acceptance and static simulation acceptance are not complete. The user's final direction was to converge and evaluate promptly, so further appearance refinement stopped after the third shaded review.

This is a case-specific authored reconstruction, not a general photo-to-scene model. It used the authorized original photograph and newly estimated parameters, without consuming old bedroom/V5/ArtVIP geometry, fitted parameters, or construction scripts. Shared generic workflow code was reused. Original and manufacturer photos are deliberately absent from this repository snapshot.

## Actual results

| Check | Result | Meaning |
|---|---|---|
| Structural and surface contracts | Passed | Full visible furniture geometry coverage, declared structures and surface evidence were checked. |
| Appearance/material contract | Passed | Texture scope, UV declarations and locked lighting-stage materials were checked; this is not a visual-similarity pass. |
| Final visual review 0003 | Changes requested | Whole-scene, whole-object, local surface, neutral and three persistent fixed views inspected. |
| Blender/GLB/USD export | Passed | Files actually written and retained remotely. |
| Actual Blender/GLB/USD re-import | Passed | 15 semantic entities and 48 declared furniture parts retained; maximum world-bound discrepancy 1.20e-7 m, camera matrix discrepancy below 1e-4. Packed or delivery-local image references verified. |
| Static engine check | **Failed** | Rear-wall collider face differs by 25 mm from the canonical room boundary. No tolerance was relaxed. |
| Independent physical accuracy | Unverified | No held-out measurements or novel real photographs were supplied. |

The rear-wall error is consistent with the exporter constructing a collision box from an entity AABB that includes protruding trim. The observed ray hit the correct rear-wall body at 0.02500004 m where 0.05 m was expected. The 6 mm tolerance correctly rejected it. The generated MJCF is a diagnostic artifact and must not be described as simulation-ready. The engine had loaded it and advanced the floor probe before reaching this failed enclosure check; no successful overall simulation audit was produced.

USD re-import initially failed only camera name lookup: the importer collapsed the source camera to `Camera_001`. The preserved explicit `frame_id` uniquely identified the same camera. The lookup was corrected and rerun without changing the geometry or camera tolerance. Initial and retry evidence remains remote.

## Remaining visual issues

- Bed textiles are too smooth and regular; pillow/duvet bunching and fine botanical pattern differ from the original.
- Headboard toys and shoes remain simplified repeated forms with insufficient shape/color variety.
- The nonmetallic reflecting board now reflects real scene geometry, but highlight concentration and reflected contrast differ from the source.
- Lower exterior vegetation and exposed rails improve the previous candidate, but the outside layout remains schematic.
- The vent is too dark and visually dominant.

Room layout, main furniture roles, source framing and complete room structure are plausible. This does not justify a high-fidelity or photorealistic reconstruction claim. Unobserved geometry, material parameters and illumination remain inferred.

Selected light trial: `lighting_rect_70`, exposure 0, AgX, world strength 4, sun energy 3. Across six source-image regions its mean absolute log luminance ratio was 0.08336 (55 W: 0.11537; 40 W: 0.23636). These are in-sample fitting diagnostics, not percentages of reconstruction accuracy. Materials and geometry were held fixed during light trials.

Initial 14-point camera fitting had median 7.03 px and maximum 16.61 px reprojection residual. A subsequent six-point local bed fit used the fixed camera and retained the 2 m longitudinal-rail prior. These are training/fitting observations. The final export audit contains **zero** `fit_landmarks`, so it does not provide a fresh final aggregate reprojection score. This coverage gap is recorded explicitly in `evaluation.json`.

## Workflow state and artifacts

The full static `quality_v2` graph contains 16 stages. Twelve stages through `build_render` succeeded; `agent_review` is `changes_requested`; formal `export`, `validate`, and `report` remain unexecuted. No freeze was created. Separate diagnostic export/reload checks did not override the visual gate or alter stage success records. Dynamics for hinges, cloth and soft bodies were disabled.

Remote root: `4090-1:/home/wqz/real2sim_whole_scene_20260926`.

- Current model: `case/runs/agent_model/0017/`.
- Current material/light: `agent_materials/0012`, `agent_calibrate_lighting/0008` under `case/runs/`.
- Complete final render/evidence: `case/runs/build_render/0003/`.
- Rejected final review: `case/runs/agent_review/0003/`.
- Candidate deliverables: `delivery_candidate/export/scene.blend`, `scene.glb`, `scene.usdc`, plus USD `textures/`, semantic OBJ `meshes/`, `scene.json`, diagnostic `scene.xml`, and `source_view_high.png` (3404 x 2552).
- Check reports: `delivery_candidate/diagnostic_status.json`, `delivery_candidate/export/reload_validation.json`, `delivery_candidate/static_engine.log`.
- Authoring scripts, rejected trials, protocol, hashes and all earlier evidence remain in this isolated remote run. Large artifacts were not relayed through the local computer.

Blender is the authoritative appearance/editing artifact. GLB/USD preserve image maps and supported PBR inputs, but procedural shaders may be approximated. Passing geometric re-import does not certify matching renderer appearance. Keep the USD file together with its textures.

Input SHA256: `5068deec1cba1e6a167209adca5fb77e4d931db06ed6a3812b9a2b8252d8c866` (1702 x 1276). User scale prior: bed rail 2.0 m. Wardrobe identity was a conditional IKEA BRUKSVARA 90556047 visual candidate, not label-confirmed; shoe cabinet identity remained unknown. Base repository commit: `9314d6c270b1abf378ef0fbb77b93ad1465f7c1a`.

## Code and resumption

`authoring/` contains the final case-specific builders, fitting inputs and review/diagnostic helpers. They use the above isolated root and expect the retained Workflow state, source photo and evidence. They are an audit/reconstruction snapshot, not a one-command independent package. Do not run bootstrap or overwrite accepted stage outputs in the retained case.

If later resumed: first repair the rear-wall collision recipe without moving the visual scene or loosening the ray test. Then prioritize irregular textile folds and distinct source accessory shapes. Use the Workflow revision API from the rejected review; retain the best candidate, fixed three-view protocol and failed attempts. Rebuild and re-review dependent stages. Formal export/validate/report/freeze requires a real visual pass.

Generic regression checks passed during this run: viewpoint world-AABB tests, neutral clay rendering, visible structural-part coverage (negative and positive cases), appearance contract and worker tests, refinement regression protection, surface contracts (13 cases), and enclosure-ray occlusion/missing-wall tests. The synthetic enclosure-ray regression passes while this case's actual enclosure check fails; both outcomes are retained, not conflated.
