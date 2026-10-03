# Frozen shared DA3 geometry reference

Only the 36 mapping PNG images enumerated in frames.json and registered input K/T were read. Registered cameras provide a diagnostic pose-conditioned input and metric gauge; they are not depth truth. No heldout photographs, laser geometry, benchmark scores, previous predictions or previous models are used.

The single configuration is frozen_config.json: DA3-GIANT, Hugging Face revision 7cd62ae9315b9dff094d2d300e4ad012640607dd, four-view windows with stride 2 in manifest order, process resolution 392 upper_bound_resize, input-pose scale alignment enabled. Select the observation with highest local centrality and earliest window on ties. No quality-based window replacement, configuration sweep or depth tuning occurs.

Official standalone source at 3d835ec1a5802d64a8b8b15f817a1ab54809bfe4 replaces the external AWSM protocol's unavailable VIPE-vendored DA3 code. All 133 files in the downloaded source were compared with the commit-pinned archive. Existing runtime is read-only; added dependencies live under this new reference_prep/dependencies directory. GS exports and GS rendering are unused.

Input frames.K is integer-centre. frames.K_raster is corner-origin. DA3's preprocessing multiplies focal lengths and principal points by image resize factors, and its normalized image coordinates use half-pixel centres. Therefore K_raster is supplied. API output is saved as K_depth_raster; K_depth subtracts 0.5 from both principal-point coordinates and is used with integer array u/v. Width/height scales are checked per frame. Images are expected to be 392x266 but actual saved shapes govern.

Each shared/frames/NNN.npz contains depth_z_m (optical Z, camera metres), valid_mask (finite positive, non-sky), raw confidence, confidence_valid_mask, sky, K_depth, K_depth_raster, supplied T_world_camera (OpenCV C2W in canonical metres/Z-up), input_world_to_camera, processed_rgb, sample_index and window_index. Invalid depths and nonfinite confidence are stored as zero and excluded by the corresponding masks. Confidence is not a calibrated probability and no threshold was applied.

Backprojection: X_camera = depth_z_m[v,u] * inv(K_depth) @ [u,v,1]. Then X_world = T_world_camera @ [X_camera,1]. Apply valid_mask. Per-window camera-only Umeyama depth divisors are in windows/wNN.json. These are learned geometry estimates and should not be treated as physical or benchmark acceptance.

shared/manifest.json hashes every selected NPZ and copied metadata. validation.json checks schema, finite values, original input camera equality, inverse transforms, resize and half-pixel conventions, and selected file hashes. Frozen output can be copied byte-for-byte to each independent author's input scope.
