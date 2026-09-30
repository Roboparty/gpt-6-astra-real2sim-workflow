# Agent: material reconstruction and neutral-light calibration

Read the original in detail. Separate albedo from baked illumination and classify actual material behavior: velvet/fabric weave and sheen, painted wood, natural grain, wicker, metal, glass and wall finish. Specify physical texture scale and UV density. A single noise bump and constant roughness across all soft objects is not a finished material system.

Match seams, edge softness, wrinkle scale and contact creases through geometry where silhouette or shading requires them. Static soft objects still need realistic shape when dynamic deformation is disabled. Use licensed/provenanced textures or grounded procedural textures; source-extracted art is allowed but its baked shading cannot serve as independent photometric validation.

Deliver model.blend, scene.json, material_calibration.json and neutral-light closeups. The JSON must list materials with entity, pbr_parameters, texture_scale_m, evidence and uncertainty, plus neutral_light_previews. Record before/after changes. Lock accepted geometry and camera; report any geometry problem back to the geometry stage instead of disguising it with dark shading.

When validate_web_research is upstream, consume only model_priors/model_details
for permitted scale/material hypotheses. Record response.parameters.web_research_consumption
with report_sha256 and used_priors:[{object_id,parameter,application}], identifying
the texture scale, construction detail or material decision. When no eligible
prior is relevant, provide used_priors:[] and unconsumed_reason. Modern product
artwork is not the unobserved historic packaging; preserve that uncertainty.

When appearance_contract_version >= 1, also follow appearance.md. Whole-scene coverage, scoped textures, actual UV/material checks and persistent fixed-view comparisons are mandatory.
