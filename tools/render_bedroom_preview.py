"""Render the corrected full-room numerical replay without changing its source file.

Blender -b doors_drawers_motion.blend --python this.py -- --output NEW_DIR
CPU Cycles preview; retains the complete enclosure and original source camera.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--samples', type=int, default=8)
parser.add_argument('--threads', type=int, default=4)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
source = Path(bpy.data.filepath)
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
scene = bpy.context.scene
for name in ['floor','ceiling','wall_back','wall_front','wall_left','wall_right']:
    assert bpy.data.objects.get(name) and not bpy.data.objects[name].hide_render, name
assert scene.camera.name == 'source_camera'
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
scene.cycles.samples = args.samples; scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'; scene.render.threads = args.threads
scene.render.resolution_x = 960; scene.render.resolution_y = 720
scene.render.resolution_percentage = 100; scene.render.use_persistent_data = True
scene.render.image_settings.file_format = 'PNG'
# Evaluate the 30 fps numerical replay at 12 fps, including the returned pose.
for index in range(97):
    time_frame = 1 + index * 2.5
    scene.frame_set(int(time_frame), subframe=time_frame % 1)
    scene.render.filepath = str(out / f'{index:04d}.png')
    bpy.ops.render.render(write_still=True)
assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
(out/'manifest.json').write_text(json.dumps(dict(
    source_model_sha256=source_sha, blender=bpy.app.version_string,
    frames=97, fps=12, resolution=[960,720], samples=args.samples,
    camera='fixed original source camera', full_enclosure_retained=True,
    method='Cycles renders of the complete corrected room; replay of actual MuJoCo trajectories. No camera cuts, generated frames or hidden walls.'), indent=2))
