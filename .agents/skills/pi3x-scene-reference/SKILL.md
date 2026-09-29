---
name: pi3x-scene-reference
description: Freeze ordered image frames and pinned Pi3X versions, then validate and consume camera, point-map and confidence references with explicit scale uncertainty. Use for Pi3X scene-reference preparation and output contracts, not claiming inference readiness or geometry accuracy from installation.
---

# Pi3X scene reference

Read [the contract](references/contract.md) for schema, coordinates, versions and license boundaries. This skill supplies a tested freeze/consume adapter; it does not install dependencies or launch inference. It changes workflow consistency, not GPT-6 model weights.

Native generation integration: `scene_reference` runs after preprocessing and passes its actual status/output receipt to observation and calibration packets. `required: true` stops with `needs_input` when disabled/blocked; optional blocked references retain their reason while the original calibration path continues. Consume mode verifies accepted frame membership and forbids heldout feedback. See [generation flow](../../../docs/GENERATION_SKILLS.md).

1. Freeze exact ordered original frames, source presentation timestamps, fit/heldout roles and preprocessing before reconstruction. Run `python scripts/reference.py freeze frame-config.json frozen-input.json`. Existing files are never overwritten. Do not regenerate a frozen manifest merely to bless changed frames.
2. Track **environment readiness**, **successful inference**, and **geometric accuracy** as separate evidence fields. Read [current blockers](references/status.md) before touching existing research runtimes. Hash-verified weights do not prove imports, loading or forward execution.
3. When an independently authorized backend output already exists, bind its NPZ hash, input-manifest hash, source/weight revisions, actual ordered fit frame IDs and exact preprocessing in a provenance JSON. Run `python scripts/reference.py consume frozen-input.json predictions.npz provenance.json receipt.json --threshold 0.5`. Preserve raw arrays and failures remotely. Contract success is not inference verification.
4. Use camera/point references to propose a scene initialization. Retain scale uncertainty, unseen/occluded geometry as unknown, and low-confidence regions in the denominator. Cross-check against known dimensions and independent views before geometric claims. Reuse [RoomKit](../blender-roomkit/SKILL.md) for parts and [Real2Sim refinement](../real2sim-local-refine/SKILL.md) for source-local corrections.

If asked to generate references while the runtime is blocked, deliver the frozen inputs and the exact blocker. Do not silently resume dependency installation, spend a research camera trial, reset a budget or substitute fabricated output. A future inference authorization must include a separate versioned preparation budget when necessary, frozen inference protocol, live external GPU-work check and retained run logs. Large weights and output stay remote.

See [validation](references/validation.md) for positive/negative adapter tests and the explicitly absent inference result.
