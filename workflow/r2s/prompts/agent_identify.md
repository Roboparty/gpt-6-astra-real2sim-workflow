# Agent: furniture identity, product dimensions and exact-asset retrieval

Start with visual candidates from observation.json, then query primary manufacturer/retailer sources. Record queries, URLs, retrieved date, model family, SKU/variant, construction features, dimensions and confidence. Treat a family match as uncertain when the exact size, edition or cover is unverified. Unknown models remain unknown; common size priors must be labelled separately.

Deliver catalogue.json and assets.json. Label all catalogue measurements reconstruction priors, never validation truth. For branch A, do not inspect or load externally authored furniture geometry. Author geometry independently downstream.

Branch B may additionally retrieve an exact asset only when brand/model/variant and actual geometry/units can be audited. Record download checksum, original units, licence metadata, source identity evidence, bounds and normalization. Never substitute a similar asset. Reject mismatched variants, and record per-entity fallback_A reasons. Keep A's frozen layout and all common evidence unchanged. Paid or inaccessible candidates may remain unresolved; preserve results remotely instead of using the local machine as a large-file relay.

Return response.json with evidence, parameters and artifacts.

## Optional executable web research chain

When packet.web_research is present, deliver web_research.json using schema
real2sim.web-research/1. Keep every attempted query in queries:[{id,query}], within
packet.web_research.max_queries/max_sources. Sources require id, HTTPS url, title,
publisher, timezone-qualified retrieved_at, type (manufacturer,
official_product_page, official_manual, standards_body or research_paper),
snapshot_path and snapshot_sha256. Archive small UTF-8 source excerpts with exact
claim locators; list every snapshot in response.artifacts. Do not treat a search
snippet as a fetched primary-source claim. A failed or inaccessible lookup remains
in the ledger and unresolved object record. Never install a search service or
launch a paid API implicitly.

Objects require object_id, identity_match (exact_product/family/category/unknown),
priors and unresolved. Each dimension prior requires parameter:"dimensions",
value:[three positive numbers], unit:mm/cm/m, axis_order:[a permutation of width,
depth,height], source_id, dimension_kind:object/shipping_package,
status:sourced_prior, claim_locator and uncertainty_fraction. Unknown tolerance
must be null with uncertainty_note; do not invent a publisher tolerance. Keep
conflicting values separately. Optional details records require parameter, value
(text), source_id, status:sourced_prior, claim_locator and uncertainty_note.
Distinguish source statements from inference about the pictured instance. Unknown
identity cannot transfer numeric or textual product claims into model priors.
The native validate_web_research stage checks archive integrity and eligibility;
it does not independently establish source truth or product identity.
