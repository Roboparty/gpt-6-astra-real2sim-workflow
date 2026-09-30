# Source-backed dimensions and details

Enable `web_research` in a `quality_v2` case:

```json
{"workflow_profile":"quality_v2","web_research":{"enabled":true,"max_queries":8,"max_sources":12}}
```

The existing `agent_identify` performs the allowed web searches and archives its
evidence. `validate_web_research` is an executable stage before camera calibration,
room calibration, modelling and materials. No new search service or paid model is
called by the validator. Cases without this option retain their original DAG.

Use `real2sim.web-research/1` as documented in the identification prompt. Include
all snapshots as accepted stage artifacts. The gate checks bounded query/source
ledgers, HTTPS source metadata, contained UTF-8 snapshots, SHA256, accepted artifact
hashes, object identity scope, dimensional units and axes. Shipping dimensions,
unknown identities and unresolved distinct dimension candidates are retained but
excluded from `model_priors`. Text details retain their source and uncertainty;
semantic contradictions require agent review. Unknown numeric tolerance can be
explicitly null; modelling tolerances must be labelled as experiment assumptions.

Consumers must bind `response.parameters.web_research_consumption` to the report
hash and record each applied `(object_id, parameter, application)` or an explicit
reason for using none. This records auditable decisions, not proof that a model's
geometry or material is physically correct. Changing evidence bytes invalidates
the gate and its downstream cache. Source integrity does not establish claim
truth, product identity or photographed-instance dimensions.
