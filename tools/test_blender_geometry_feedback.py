"""Blender integration oracle: front occlusion, missing entity, and immutable blend bytes.

blender -b -P tools/test_blender_geometry_feedback.py -- NEW_OUTPUT_DIRECTORY
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

import bpy
import numpy as np


def png(path, array):
    height, width = array.shape
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + array[row].tobytes() for row in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


root = Path(sys.argv[sys.argv.index('--')+1]).resolve()
root.mkdir(parents=True, exist_ok=True)
renderer_path = Path(__file__).resolve().parents[1] / 'workflow/r2s/blender_geometry_feedback.py'
module_spec = importlib.util.spec_from_file_location('geometry_feedback_renderer', renderer_path)
renderer = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(renderer)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
# A 1m square at depth2 with focal40 projects to 20px x20px. A nearer half-width
# occluder covers its left half, leaving the analytic 10px x20px visible region.
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 2))
target = bpy.context.object
target.name = 'target'
target['entity_id'] = 'target'
bpy.ops.mesh.primitive_plane_add(size=1, location=(-.125, 0, 1))
occluder = bpy.context.object
occluder.name = 'unlisted_occluder'
occluder.scale = (.25, .5, 1)
bpy.ops.wm.save_as_mainfile(filepath=str(root / 'input.blend'))
model_before = renderer.file_record(root / 'input.blend')
source = np.full((64, 64), 96, np.uint8)
mask = np.zeros((64, 64), np.uint8)
mask[22:42, 32:42] = 255
png(root / 'source.png', source)
png(root / 'visible-target.png', mask)
record = renderer.file_record
camera = {'image_size': [64, 64], 'position': [0, 0, 0],
          'rotation_world_to_cv': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
          'focal_px': 40, 'principal_point': [32, 32]}
protocol = {'schema': 'real2sim.geometry-feedback-protocol/1.0',
            'thresholds': {'minimum_iou': .85, 'maximum_boundary_mean_px': 1., 'maximum_landmark_error_px': 1.},
            'views': [{'id': 'test', 'role': 'fit', 'camera': camera, 'source': record(root / 'source.png'),
                       'objects': [{'id': name, 'mask': record(root / 'visible-target.png')} for name in ('target', 'missing_entity')]}]}
(root / 'protocol.json').write_text(json.dumps(protocol))
(root / 'scene.json').write_text(json.dumps({'objects': [{'id': 'target'}],
    'reconstruction_source_sha256': [record(root / 'source.png')['sha256']]}))
sys.argv = ['blender', '--', str(root / 'scene.json'), str(root / 'protocol.json'), str(root / 'render')]
renderer.main()
candidate = json.loads((root / 'render/candidate.json').read_text())
counts = {}
for obj in candidate['views'][0]['objects']:
    image = bpy.data.images.load(obj['mask']['path'], check_existing=False)
    values = np.asarray(image.pixels[:]).reshape(64, 64, 4)[:, :, 0]
    assert set(np.unique(values).tolist()) <= {0., 1.}, 'Mask is not binary'
    counts[obj['id']] = int((values > .5).sum())
    if obj['id'] == 'target':
        # 400px means the occluder was removed; 200px is correct. Allow 1px raster edges.
        assert 171 <= counts['target'] <= 231, counts
        yy, xx = np.where(values > .5)
        assert int(xx.min()) >= 31 and int(xx.max()) <= 42, (xx.min(), xx.max())
    else:
        assert counts[obj['id']] == 0, counts
assert model_before == record(root / 'input.blend'), 'Renderer modified original blend bytes'
assert candidate['views'][0]['camera_readback']['maximum_projection_error_px'] < .01
evidence = {'status': 'passed', 'visible_pixel_counts': counts, 'input_blend_unchanged': True,
            'interpretation': 'Synthetic renderer integration only; actual visible masks preserve an unlisted occluder.'}
(root / 'blender-integration.json').write_text(json.dumps(evidence, indent=2))
print('GEOMETRY_FEEDBACK_BLENDER_TEST_OK', json.dumps(evidence))
