# Agent: furniture identity, product dimensions and exact-asset retrieval

Start with visual candidates from observation.json, then query primary manufacturer/retailer sources. Record queries, URLs, retrieved date, model family, SKU/variant, construction features, dimensions and confidence. Treat a family match as uncertain when the exact size, edition or cover is unverified. Unknown models remain unknown; common size priors must be labelled separately.

Deliver catalogue.json and assets.json. Label all catalogue measurements reconstruction priors, never validation truth. For branch A, do not inspect or load externally authored furniture geometry. Author geometry independently downstream.

Branch B may additionally retrieve an exact asset only when brand/model/variant and actual geometry/units can be audited. Record download checksum, original units, licence metadata, source identity evidence, bounds and normalization. Never substitute a similar asset. Reject mismatched variants, and record per-entity fallback_A reasons. Keep A's frozen layout and all common evidence unchanged. Paid or inaccessible candidates may remain unresolved; preserve results remotely instead of using the local machine as a large-file relay.

Return response.json with evidence, parameters and artifacts.
