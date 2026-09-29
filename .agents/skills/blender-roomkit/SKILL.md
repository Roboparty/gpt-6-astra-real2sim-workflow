---
name: blender-roomkit
description: Author decomposed static rooms and furniture in Blender with explicit dimension priors, collision proxies, bedding folds, upholstery, toys and shoe components. Use for editable component modeling or RoomKit batch generation, not learned reconstruction or physical qualification.
---

# Blender RoomKit

Use this skill to turn a component inventory into an editable Blender scene. This is a local workflow skill with an original small batch backend, not an installed third-party RoomKit product. It improves workflow consistency; it does not change GPT-6 model weights.

In the repository's native `quality_v2` generation flow, enable `generation_skills` with `tools/enable_generation.py`. The `agent_model` stage may submit `roomkit_parts.json` plus canonical `scene.json` and accepted observation/structure evidence. `Workflow.accept` executes the RoomKit backend and generates `model.blend`; existing structural/render/review stages then run. Do not include shell parts in this native manifest: the adapter builds all six surfaces and declared openings from canonical `room`. See [generation integration](../../../docs/GENERATION_SKILLS.md). Standalone fixture commands below are for isolated part authoring only.

Read [the part contract and modeling recipes](references/parts.md) before authoring. Preserve stable assembly/part IDs. Separate wall segments, furniture carcasses, doors, shelves, feet, mattresses, covers, pillows and accessories. Use metres and explicit assumed dimension/source records. An image alone cannot establish hidden dimensions or contact parameters.

Run `scripts/roomkit.py` through Blender with a fresh output directory:

```sh
blender -b -t 2 --python-exit-code 12 -P /path/blender-roomkit/scripts/roomkit.py -- /path/parts.json /new/output
```

It creates `scene.blend` and `receipt.json`. The backend starts an empty scene, supports box/cushion/ellipsoid/static folded-sheet recipes, independent materials and optional per-part world-AABB proxies. It does not load or rewrite a previous scene. Do not substitute this limited builder for an existing detailed scene: use an isolated copy and that scene's established authoring tool instead.

For local changes compose with [real2sim-local-refine](../real2sim-local-refine/SKILL.md). For learned camera/point references compose with [pi3x-scene-reference](../pi3x-scene-reference/SKILL.md); those outputs are uncertain references, not measured truth.

Before promotion, inspect source and other fixed views; check evaluated geometry and proxy bounds after modifiers/export. A box proxy may overfill curved or concave objects: split collision parts, preserve openings, and test support/contact in the target engine. A generated proxy is not a passed physics test. Static wrinkles are not cloth dynamics. Hinges, cloth and volumetric soft bodies require explicit optional engine work; this builder rejects activation.

Read [backend evaluation](references/backend.md) if interactive Blender MCP is requested. The default is the existing batch runtime; no MCP server installation, model API, asset-service request or dependency installation is implied. Check live runtime availability. On shared hosts use small CPU runs and fresh paths; do not touch another research run, budget or process. Full scenes remain remote, small receipts/previews may be local.

Verified scope and actual tests are linked from [validation](references/validation.md).
