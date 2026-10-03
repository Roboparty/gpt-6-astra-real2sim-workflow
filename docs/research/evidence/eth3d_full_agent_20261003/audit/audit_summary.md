Independent frozen-result audit: PASS, with scope caveats

Both raw model hashes, freeze receipts and shared truth-grid hash match. All 44 views and all 90,875 GT-valid positions are retained: 74,079 mapping and 16,796 heldout. This is 10.76% of the 844,800 grid positions. No model or mask was changed.

Depth arithmetic reproduces the published equal-view macro means within 1.3e-8. These are not pooled-pixel values. OURS misses 6 mapping / 0 heldout predictions; AWSM misses 906 / 329. Missing values retain the declared 30m penalty. Macro heldout AbsRel: OURS 6.4378%, AWSM 4.6490%; pooled alternatives: 5.7443% / 4.1725%. Both are recorded, not swapped.

Geometry was independently requeried against all 24,898,515 laser points for both 100,000-point model samples (45.6s total). Every published mean, P95, precision, recall and F-score matches exactly. An independent forward-G model-space BVH query also reproduces depth masks and laser-to-mesh distances to floating-point tolerance. Both area samples regenerate byte-for-byte. No coordinate or arithmetic bug was found.

All 26 LPIPS pair identities and byte hashes pass, every resized source image reproduces from the original, and all 8 heldout frames per method are retained. Recorded LPIPS means reproduce exactly: mapping OURS 0.5088648021 / AWSM 0.5709672451; heldout 0.5562385879 / 0.5792867318. The network forward pass was not rerun in this audit.

Why OURS can have 3.81394m whole-model distance with 6.44% heldout depth AbsRel:
- Floor, ceiling and four large shell walls account for 79.060% of sampled surface and 95.308% of total model-to-laser distance. Their contribution to the overall mean is 3.634989m.
- Other objects contribute 4.692% of the distance, or 0.178955m to the overall mean; their conditional mean is 0.854607m.
- The whole-model metric includes unsupported completion, hidden/back/exterior faces and large areas absent from the sparse depth domain. It is therefore not the same question as visible-depth agreement.
- This does NOT prove every unmatched surface is harmless completion. Wrong extents/layout and scan coverage gaps are not fully disentangled. Only 2.737% of samples are outside every camera frustum; being inside a frustum is not proof of visibility or laser support. No post-hoc crop or mask is justified.

Appearance retains authored materials/lights; geometry treats visible mesh faces as opaque. Existing FAILED_NATIVE / LIMITED outcomes remain. This audit supports source-bound metric statements, not a visual-only winner or delivery acceptance.

Detailed evidence: audit_summary.json, depth_recomputed.json, *_geometry_recomputed.json, *_blender_requery.json, *_surface_attribution.json, lpips_integrity.json.
