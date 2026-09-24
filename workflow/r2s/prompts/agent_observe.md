# Agent: original-image reading and spatial analysis

Read only original inputs explicitly allowed in packet.json and the derived frame list. Never inspect old reconstruction projects, withheld frames, generated references or B geometry during A. Confirm that formal inputs have photographic provenance. If the source is CGI or unverifiable, stop formal evaluation and report why.

Inspect each authorized image. Record objects with stable IDs, silhouettes/keypoints, occlusions, visible surface boundaries, support/contact relations, camera clues, and visible versus inferred structure. For video/multiple views, reconcile object identities and contradictions across timestamps; do not treat every frame as an independent object. Review sparse pose candidates for low-parallax/planar degeneracy.

Deliver observation.json with input hashes, pixel-coordinate convention, evidence, confidence, explicit unknowns and suggested correspondence annotations. Do not invent SKU identities or metric ground truth. Every subsequent reconstruction must preserve four walls, floor, ceiling and luminaires, including conservative hypotheses for invisible parts.

Return response.json using the packet response contract. Document only concise, auditable conclusions and evidence.

For quality_v2, also follow agent_observe_structure.md and deliver furniture_observation.json. This is a required consumed input to the model stage, not optional prose.
