# Unified native generation integration — 2026-09-29

The research branch through `1be6116` and generation-skills branch `a08fdcf`
were merged in an isolated working tree, preserving their common ancestor
`37976c0` and frozen baseline `f0e61696`. The remote main was checked at
`f0e61696`. This document records a validated integration candidate; it does not
itself establish that main has been updated.

The native `quality_v2` flow now includes executable reference consumption,
RoomKit construction during model acceptance, and geometry/appearance feedback
feeding the existing review and revision stages. These are opt-in for a case;
legacy cases retain their existing flow. See [the actual entrypoint and
configuration](../GENERATION_SKILLS.md). No separate paid model call, automatic
Pi3X setup, or inference launch was added.

## Fixes required by integration review

1. `accept()` now rejects executable stages. A required blocked reference or
   missing local-feedback input cannot be manually marked complete via the
   public Agent acceptance command; fix input and retry the actual worker.
2. Current Agent execution time is deducted before RoomKit launch. For example,
   with 60 seconds remaining and 55 spent in the Agent, the builder receives at
   most five seconds. Existing accumulated budgets remain intact.
3. RoomKit's per-part box policies now become canonical collision recipes;
   hidden authoring helper meshes are removed from the generated model rather
   than leaking into visual export. Fixed lamps carry the correct explicit
   empty-room tags. Entire entities with `collision: none`, conflicting existing
   proxies, and mismatched empty-room lamp names fail explicitly. These are
   narrow backend limitations, not silently altered physics requests.
4. Backend Pi3X provenance requires an existing hash-bound receipt and log, with
   input/output/version/frame/preprocessing bindings and successful forward and
   checkpoint-load declarations. Missing or inconsistent records block the
   native stage; their bytes also invalidate cache. Consistent self-reported
   records cannot independently authenticate that a model ran. No real Pi3X
   forward is established by these tests.

## Actual verification of the merged code

All **12 runner groups passed**, with **59.617924 seconds** of measured combined
wall time. Tests ran sequentially on the existing 4090-1 Python/Blender runtime,
with CUDA disabled and two CPU threads. The source snapshot includes exact
hashes; current executable Python bytes were checked against those hashes after
the run. Report/contract documentation was expanded afterward without changing
the evaluated code.

| Verification | Result |
|---|---|
| Skill contracts/CLIs | 49 cases passed |
| Native input → reference → RoomKit → render → feedback → review | 29 cases passed; actual Blender 4.5.3 CPU |
| Generation binding/rejection contracts | 21 cases passed |
| Required worker acceptance and shared-time regression | 6 cases passed; actual blocked workflow plus controlled clock/launch mock |
| Pi3X receipt/provenance/cache checks | 36 cases passed; all synthetic contract data |
| Existing research suite | 14/14 scripts passed, including refinement, structure, geometry feedback, shell/openings, physical priors and optional dynamics |
| RoomKit canonical export and engine | Two actual positive fixtures and three rejection fixtures passed; Blender export and MuJoCo static probes executed |
| Explicit empty room | Actual existing Blender fixture passed |
| Single-part / single-assembly / pose bindings / visible annotations | Existing separate regressions passed |

RoomKit positive fixtures include a translated, rotated sofa and an explicit
empty room with a fixed lamp. Exported visual entities exclude authoring collision
helpers; compiled collision positions/dimensions match the intended canonical
boxes. The original native smoke's lamp policy was made explicitly `box` rather
than relying on the old silently ignored `none` setting. This does not relax an
acceptance gate; unsupported all-none policies now have their own rejection test.

[Runner summary](evidence/unified_generation_20260929/summary.json),
[source snapshot](evidence/unified_generation_20260929/source_manifest.json),
[native flow](evidence/unified_generation_20260929/native_flow.json),
[canonical export](evidence/unified_generation_20260929/canonical_export.json),
[receipt checks](evidence/unified_generation_20260929/pi3x_receipt_binding.json),
[accept/budget tests](evidence/unified_generation_20260929/accept_budget.json), and
[research regressions](evidence/unified_generation_20260929/research_regressions.json).

Complete models, fixtures and logs remain remote under
`/home/wqz/real2sim_capability_20260929/runs/unified_validation_001`. The earlier
skills-delivery attempts, failures and costs remain in their original separate
[validation record](../generation-skills/VALIDATION.md). The receipt test's first
local invocation lacked `cv2` and stopped before running cases; no dependency was
installed locally. Its successful runtime is the existing remote environment.
Unknown setup, review and orchestration costs remain unknown.

## Research and release boundaries

This verifies integration behavior and several actual engine paths using explicit
synthetic fixtures. It is not a newly reconstructed physical task success,
independent multiscene accuracy result, or SOTA evidence. Pi3X preparation remains
blocked at its previously exhausted 1,800-second budget. Camera attempts stay
6/8, appearance proposals 4/8, combined proposals 2/8; no GPU hours or paid API
requests were added. Optional hinges/cloth/soft bodies remain explicit.

All original branches, failed attempts, scene files and the 36-observation
annotation denominator are retained. Full-scene visual acceptance and the
three-video common-initialization benchmark remain unfinished.
