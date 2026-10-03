Post-freeze v4 numerical audit: confirmed, exposed-test diagnostic only

All three variants retain 44 views and 90,875 GT-valid positions (74,079 mapping + 16,796 originally heldout). Raw model hashes, freeze receipts and the shared truth hash match. The old baseline is the same preserved evaluation directory, and all 13 baseline LPIPS values match the earlier result exactly.

| Metric | Baseline | Geometry v4 | Texture v4 |
|---|---:|---:|---:|
| Symmetric surface mean, m | 1.962896220 | 0.482278404 | 0.482278404 |
| Exposed-view macro AbsRel | 0.064378209 | 0.051575025 | 0.051575025 |
| Exposed-view LPIPS | 0.556238588 | 0.552137464 | 0.411260270 |

Every geometry mean and F-score reproduced exactly after a new full-cloud KD query. Depth macro arithmetic differs from the recorded float32 implementation by at most about1.1e-8. The geometry and texture versions have byte-identical rendered-depth, laser-to-model and100000-point surface-sample arrays, so the texture result does not hide a geometric change.

All39LPIPS pair identities/hashes, original-source resized pixels, saved-render pixels and split means passed independent checks. All39PNG files were reencoded for the pair package, but their actual pixels are identical to the evaluator renders. The two installed weight hashes were rechecked; LPIPS forward inference was not rerun.

Coverage caveat: missing predictions rise from6to48 in mapping views and0to3 in exposed views. Exposed macro30m-penalty MAE still improves from0.428542m to0.360547m. Conditional AbsRel must not be quoted without this information.

These are post-freeze diagnostics on a previously exposed test set. They do not establish new generalization, physical albedo, lighting recovery, native material acceptance or successful delivery. The source-only LIMITED findings and75soft-world failures remain in force. Nothing was sent back to the authors or changed after scoring.

Detailed arithmetic and hash evidence are in postfreeze_independent_summary.json and the referenced audit files.
