import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

out = Path(sys.argv[sys.argv.index('--') + 1])
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.render.resolution_percentage = 65
sc.camera = bpy.data.objects['source_camera']
sc.render.image_settings.file_format = 'PNG'
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(out / 'scene.blend'))
sc.render.filepath = str(out / 'source_view.png')
bpy.ops.render.render(write_still=True)
(out / 'render_manifest.json').write_text(json.dumps({'comparison_settings': {
    'resolution_percentage': 65, 'view_transform': sc.view_settings.view_transform,
    'look': sc.view_settings.look, 'exposure': sc.view_settings.exposure,
    'engine': 'CYCLES', 'samples': 24, 'diagnostic': 'fixed furniture camera v1'}}))
scene = json.loads((out / 'scene.json').read_text())
chair = next(a for a in scene['structure']['assemblies'] if a['entity'] == 'chair_near')
focus = Vector(chair['frame']['position']) + Vector((0, 0, .45))
bpy.ops.object.camera_add(location=focus + Vector((1.05, -.70, .75)))
camera = bpy.context.object
camera.rotation_euler = (focus - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.lens = 48
sc.camera = camera
sc.render.resolution_x = 800
sc.render.resolution_y = 800
sc.render.resolution_percentage = 100
sc.render.filepath = str(out / 'diagnostic_reverse.png')
bpy.ops.render.render(write_still=True)
