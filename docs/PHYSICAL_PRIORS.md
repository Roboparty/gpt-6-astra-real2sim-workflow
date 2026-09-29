# Traceable physical priors

`public_contract/physical_priors.json` contains small, auditable reference values. It is an initialization library, not a claim of measured properties for an object reconstructed from a photograph. The resolver always marks a scene assignment `parameter_provenance: assumed`, even when a library value is a published manufacturer reference. This matches the existing dynamics provenance vocabulary.

## Reference values

| ID | Density kg/m³ | Scope and evidence |
|---|---:|---|
| `wood_generic_12pct` | 560; range 336–784 | [USDA Wood Handbook, Table 4-6a](https://www.fpl.fs.usda.gov/documnts/fplgtr/fplgtr282/fpl_gtr282.pdf): selected specific gravity 0.50 at 12% moisture; range covers table gravity 0.30–0.70 at that moisture. It does not span every species. |
| `mdf_laminated_15_19mm` | 700; range 670–730 | [EGGER laminated MDF EPD, §2.3](https://www.egger.com/get_download/971cb671-dc55-4134-910f-df1cf4795572/Environmental_product_declaration_Eurodekor_MDF.pdf): midpoint of the gross density interval for 15–19 mm board. EN 323 is the density test method, not a universal prescribed density. |
| `glass_soda_lime` | 2500; range unknown | [Pilkington ATS-129, p.2](https://www.pilkington.com/-/media/pilkington/site-content/usa/window-manufacturers/technical-bulletins/ats-129---properties-of-soda-lime-silica-float-glass.pdf): soda-lime float glass. No uncertainty range is invented. |

Sources were checked 2026-09-29. The library records whether evidence came from full source text or an indexed extract of the primary document. The EGGER server uses a content type the web reader could not parse; its numerical table was available in the primary-source search index. Wood-table values likewise came from the primary PDF search extract. Pilkington and MuJoCo were read as full source text. Failed or partial retrieval is not silently called full verification.

Density applies to material volume. For a hollow cabinet, sum the actual panel volumes or use a verified material mesh; the cabinet's whole bounding box includes air. A missing volume yields `estimated_mass_kg: null`. Even when supplied, mass is only an estimate, and the report does not inject it into a simulator. A string claiming a valid volume basis is provenance, not independent mesh-volume verification.

## Contact and optical parameters are separate

`mujoco_default_v1` returns `friction: [1, 0.005, 0.0001]`, with units `[dimensionless, m, m]`, and `condim: 3`. These are [MuJoCo defaults](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-geom), not standard friction values for wood, glass or a particular contact pair. The final two numbers describe torsional and rolling friction; [their units are length](https://mujoco.readthedocs.io/en/stable/computation/index.html#contact). With `condim=3`, only sliding friction participates. The included sliding values `[0.3, 0.6, 1.0]` are project sensitivity-test points, not a measured confidence interval. Run the full frozen test set at each point; do not choose per-case best friction.

An MJCF explicit `<pair>` needs **five** entries: for an isotropic geom triple `[s,t,r]`, emit `[s,s,t,r,r]`. Check pair names against actual collidable geoms and read back runtime `pair_friction`/`pair_dim`. A declaration alone does not establish that the intended pair collides. Pair conditions must identify assumptions about surface state and measurement gaps. Existing legacy friction values should not change silently; apply this preset through an explicit new run configuration and retain the old comparator.

Optical roughness uses the [Blender Principled BSDF](https://docs.blender.org/manual/en/5.0/render/shader_nodes/shader/principled.html) model and has no numeric mapping to friction. Its initial values and ranges in this library are project choices. Glass IOR 1.523 references ATS-129 at 0.5893 µm; using it for unidentified scene glass is still an assumption. Finishing, paint and coatings require separate appearance decisions. Appearance validators remain authoritative; this library does not bypass them.

## Scene sidecar configuration and interface

```python
from r2s.physical_priors import validate_physical_priors

report = validate_physical_priors({
    "materials": [{
        "entity": "cabinet", "component": "left_panel",
        "material_id": "mdf_laminated_15_19mm",
        "assignment_basis": "Unidentified panel; documented MDF analogue",
        "volume_m3": 0.02, "volume_basis": "component_dimensions"
    }],
    "contacts": [{
        "geom_pair": ["cabinet_foot", "floor"],
        "preset": "mujoco_default_v1",
        "conditions": "Dry assumed; coating, load and wear unmeasured"
    }],
    "completions": [{
        "entity": "cabinet", "regions": ["back"],
        "basis": "symmetry", "evidence": ["front_reference.png"],
        "assumption": "Rear panel follows the visible side frame",
        "observed": False
    }]
}, entity_ids={"cabinet"})
```

`load_library()` provides all presets and the exact-byte SHA256. `material_prior(id)` and `contact_prior(preset)` return independent dictionaries. `validate_physical_priors(config, entity_ids=None)` validates and returns a report with the library hash and used source records; it does not mutate the scene. Contact entries expose simulator values at `report['contacts'][i]['prior']['friction']` and `['condim']`. The caller checks the existence of referenced evidence files and geom names because those artifact scopes are not available to this pure resolver. Store the sidecar next to exported artifacts and bind its hash in the experiment record.

Unknown fields, duplicate assignments/pairs/completed regions, invalid entities, nonfinite or nonpositive volumes, unspecified conditions and completion falsely marked observed are rejected. `material_id` is explicit: no material is guessed from an entity name. Empty configuration is valid, preserves unknowns and leaves the legacy pipeline unchanged.

## Optional hinges and flexible objects

Keep the existing `physics` switches: `hinges`, `cloth`, `soft_bodies`. All default to `false` in `r2s.profiles.physics_options`. `cloth` and `soft_bodies` together cover optional flexibility; a separate fourth toggle is unnecessary. Static export remains the frozen reference. Enabled features require explicit segmented moving parts, joint axes/limits, rest shapes and numerical simulation checks through the existing dynamics path. No automatic hinge or soft-body generation comes from a density/PBR preset. No unverified modulus or damping values are introduced here.

For an unobserved backside use `symmetry`, `catalogue`, or `conservative_closure`, with region, evidence and an explicit completion assumption. A catalogue is only an analogue unless exact product identity is established. Missing backsides have no universal standard dimension. These completions can improve watertightness and plausibility but stay outside observed-geometry accuracy claims.

## Verification

Run `python tools/test_physical_priors.py`. The lightweight test checks numerical source data, units, immutable output, retained unknown mass and rejected malformed/provenance-breaking inputs. It requires only the standard library. It does not claim physical task success, renderer quality, measured real-world accuracy or SOTA.
