"""One preregistered, uniform bedding color correction; geometry and illumination stay fixed.

blender -b -t 2 --python-exit-code 12 -P tools/apply_bedding_color_candidate.py
        -- /remote/new-output /remote/registered-protocol.json

The protocol must exist before running. Fit constants are fixed here; this script
does not optimize, retry colors, add photographic textures, or bake a shadow map.
"""
import json
from pathlib import Path
import shutil
import sys
import time
import hashlib
import subprocess

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_appearance_candidate import file_sha, object_snapshot, digest


BASE = Path('/home/wqz/real2sim_capability_20260929/runs/combined_001')
SOURCE = Path('/home/wqz/real2sim_whole_scene_20260926/input/01_bedroom.jpg')
POLYGON = [[700, 800], [980, 740], [1060, 772], [826, 882]]
SOURCE_SIZE = [1702, 1276]
TARGETS = ['bed_duvet', 'bed_pillow']
ANALYSIS_PYTHON = '/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python'


def polygon_medians(path):
    """Use the existing server analysis runtime; no photograph enters Blender datablocks."""
    code = '''
import sys,json
import numpy as np
import PIL
from PIL import Image,ImageDraw
path=sys.argv[1]; polygon=json.loads(sys.argv[2])
with Image.open(path) as im:
 original_size=list(im.size)
 if original_size not in ([1702,1276],[851,638]): raise ValueError('Unexpected input raster')
 rgb=np.asarray(im.convert('RGB').resize((851,638),Image.Resampling.LANCZOS),dtype=np.float64)/255.
mask=Image.new('L',(851,638)); ImageDraw.Draw(mask).polygon([(x*.5,y*.5) for x,y in polygon],fill=255)
valid=np.asarray(mask)>0
linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
median=np.median(linear[valid],axis=0)
if valid.sum()<100 or not np.isfinite(median).all() or np.any(median<=1e-6): raise ValueError('Invalid bedding median')
print(json.dumps({'original_image_size':original_size,'image_size':[851,638],
 'polygon_native_xy':[[x*.5,y*.5] for x,y in polygon],'valid_pixels':int(valid.sum()),
 'linear_rgb_median':median.tolist(),'resize':'Pillow LANCZOS, fixed 851x638',
 'polygon_rasterization':'Pillow ImageDraw polygon filled, source coordinates scaled 0.5',
 'pillow_version':PIL.__version__,'numpy_version':np.__version__}))
'''
    result = subprocess.run([ANALYSIS_PYTHON, '-c', code, str(path), json.dumps(POLYGON)],
                            text=True, capture_output=True, check=True)
    return {**json.loads(result.stdout), 'path': str(path), 'sha256': file_sha(path),
            'interpretation': 'Assumed sRGB EOTF of displayed pixels, not recovered scene radiance or measured albedo.'}


def geometry_fingerprint(scene):
    records = {}
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        sha = hashlib.sha256()
        coords = np.empty(len(mesh.vertices)*3, dtype=np.float32)
        mesh.vertices.foreach_get('co', coords)
        sha.update(coords.tobytes())
        indices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', indices)
        sha.update(indices.tobytes())
        for field in ('loop_start', 'loop_total', 'material_index'):
            values = np.empty(len(mesh.polygons), dtype=np.int32)
            mesh.polygons.foreach_get(field, values)
            sha.update(values.tobytes())
        for uv in mesh.uv_layers:
            values = np.empty(len(uv.data)*2, dtype=np.float32)
            uv.data.foreach_get('uv', values)
            sha.update(uv.name.encode())
            sha.update(values.tobytes())
        records[obj.name] = sha.hexdigest()
    return records


def scene_settings(scene):
    camera = scene.camera
    return {'camera': {'name': camera.name, 'matrix': [float(value) for row in camera.matrix_world for value in row],
                       'lens': camera.data.lens, 'shift': [camera.data.shift_x, camera.data.shift_y]},
            'lights': {obj.name: {'matrix': [float(value) for row in obj.matrix_world for value in row],
                                  'type': obj.data.type, 'energy': obj.data.energy, 'color': list(obj.data.color)}
                       for obj in scene.objects if obj.type == 'LIGHT'},
            'world': scene.world.name if scene.world else None,
            'view_transform': scene.view_settings.view_transform, 'exposure': scene.view_settings.exposure,
            'gamma': scene.view_settings.gamma, 'look': scene.view_settings.look,
            'render': {'engine': scene.render.engine, 'samples': scene.cycles.samples,
                       'denoise': scene.cycles.use_denoising, 'adaptive': scene.cycles.use_adaptive_sampling,
                       'seed': scene.cycles.seed, 'resolution': [scene.render.resolution_x, scene.render.resolution_y,
                                                               scene.render.resolution_percentage]}}


def apply_color(scene, multiplier):
    actions = []
    for name in TARGETS:
        obj = scene.objects.get(name)
        if obj is None or obj.type != 'MESH' or len(obj.material_slots) != 1:
            raise ValueError('Expected exact bedding mesh with one material: ' + name)
        source_material = obj.material_slots[0].material
        if source_material is None or source_material.node_tree.nodes.get('Bedding Color Fit'):
            raise ValueError('Missing material or correction already applied: ' + name)
        copied = source_material.copy()
        copied.name = source_material.name + '_color_fit_prior'
        shader = copied.node_tree.nodes.get('Principled BSDF')
        if shader is None:
            raise ValueError('Expected existing Principled BSDF: ' + name)
        socket = shader.inputs['Base Color']
        existing_links = list(socket.links)
        if len(existing_links) > 1:
            raise ValueError('Unexpected multi-linked base color')
        multiply = copied.node_tree.nodes.new('ShaderNodeMixRGB')
        multiply.name = 'Bedding Color Fit'
        multiply.label = 'Uniform RGB multiplier: assumed fit-prior'
        multiply.blend_type = 'MULTIPLY'
        multiply.use_clamp = False
        multiply.inputs[0].default_value = 1.
        multiply.inputs[2].default_value = (*[float(value) for value in multiplier], 1.)
        previous = None
        if existing_links:
            previous = existing_links[0].from_node.name
            copied.node_tree.links.new(existing_links[0].from_socket, multiply.inputs[1])
            copied.node_tree.links.remove(existing_links[0])
        else:
            multiply.inputs[1].default_value = socket.default_value
        copied.node_tree.links.new(multiply.outputs[0], socket)
        # An object material override leaves shared mesh datablocks completely unchanged.
        obj.material_slots[0].link = 'OBJECT'
        obj.material_slots[0].material = copied
        actions.append({'object': name, 'original_material': source_material.name, 'new_material': copied.name,
                        'previous_base_color_node': previous, 'multiplier': [float(value) for value in multiplier],
                        'condition': 'assumed/fit-prior', 'spatially_uniform': True})
    return actions


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if len(args) != 2:
        raise ValueError('Expected -- NEW_OUTPUT_DIR REGISTERED_PROTOCOL.json')
    output, protocol_path = (Path(value).resolve() for value in args)
    protocol = json.loads(protocol_path.read_text(encoding='utf-8-sig'))
    if (protocol.get('schema') != 'real2sim.bedding-color-fit/1' or
            protocol.get('fit_polygon_source_pixels') != POLYGON or protocol.get('target_objects') != TARGETS or
            protocol.get('fit_raster') != [851, 638] or protocol.get('expected_candidate_count') != 1):
        raise ValueError('The preregistered protocol differs from this fixed proposal')
    output.mkdir(parents=True, exist_ok=True)
    if (output/'receipt.json').exists() or (output/'model.blend').exists():
        raise ValueError('Use a new output directory; retain every earlier attempt')
    started = time.monotonic()
    receipt = {'schema': 'real2sim.bedding-color-candidate/1', 'status': 'started',
               'protocol_path': str(protocol_path), 'protocol_sha256': file_sha(protocol_path),
               'script_sha256': file_sha(__file__),
               'snapshot_helper_sha256': file_sha(Path(__file__).with_name('apply_appearance_candidate.py')),
               'input_blend_sha256': file_sha(BASE/'model.blend'), 'input_scene_sha256': file_sha(BASE/'scene.json'),
               'input_render_sha256': file_sha(BASE/'ordinary_render.png'), 'source_sha256': file_sha(SOURCE),
               'polygon_source_xy': POLYGON, 'proposal_count': 1, 'condition': 'assumed/fit-prior',
               'clamp_per_channel': [.6, 1.1], 'photo_textures_added': False,
               'limitations': ['Display-referred medians and frozen lighting do not identify physical reflectance.',
                              'The same uniform correction is assumed for duvet and pillow; no per-pixel shadow baking.']}
    if receipt['source_sha256'] != protocol['source_sha256']:
        raise ValueError('Source bytes differ from preregistered hash')
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2))
    try:
        bpy.ops.wm.open_mainfile(filepath=str(BASE/'model.blend'))
        scene = bpy.context.scene
        settings_before = scene_settings(scene)
        expected_render = {'engine': 'CYCLES', 'samples': 8, 'denoise': True, 'adaptive': False,
                           'seed': 0, 'resolution': [1702, 1276, 50]}
        if settings_before['render'] != expected_render:
            raise ValueError('Combined baseline render settings do not match the frozen comparison settings')
        object_before = object_snapshot(scene)
        geometry_before = geometry_fingerprint(scene)
        image_ids_before = sorted(image.name for image in bpy.data.images)
        receipt['source_statistics'] = polygon_medians(SOURCE)
        receipt['baseline_statistics'] = polygon_medians(BASE/'ordinary_render.png')
        source_median = np.asarray(receipt['source_statistics']['linear_rgb_median'])
        base_median = np.asarray(receipt['baseline_statistics']['linear_rgb_median'])
        ratio = source_median / base_median
        multiplier = np.clip(ratio, .6, 1.1)
        receipt.update(unclamped_multiplier=ratio.tolist(), applied_multiplier=multiplier.tolist(),
                       clamp_applied=(ratio != multiplier).tolist())
        receipt['actions'] = apply_color(scene, multiplier)
        bpy.context.view_layer.update()
        object_after = object_snapshot(scene)
        geometry_after = geometry_fingerprint(scene)
        settings_after = scene_settings(scene)
        changed_geometry = [name for name in geometry_before if geometry_before[name] != geometry_after.get(name)]
        changed_transforms = [name for name in object_before if any(object_before[name][field] != object_after[name][field]
                                                                  for field in ('matrix_world', 'dimensions'))]
        unrelated = [name for name in object_before if name not in TARGETS and object_before[name] != object_after[name]]
        if changed_geometry or changed_transforms or unrelated or settings_before != settings_after:
            raise ValueError('Frozen-state violation: ' + str([changed_geometry, changed_transforms, unrelated]))
        if sorted(image.name for image in bpy.data.images) != image_ids_before:
            raise ValueError('Analysis image leaked into the editable model')
        receipt['audit'] = {'status': 'passed', 'object_count': len(object_before),
                            'mesh_count': len(geometry_before), 'non_target_count': len(object_before)-len(TARGETS),
                            'all_geometry_unchanged': True, 'all_transforms_and_dimensions_unchanged': True,
                            'non_target_materials_unchanged': True, 'camera_lights_render_settings_unchanged': True,
                            'geometry_before_sha256': digest(geometry_before), 'geometry_after_sha256': digest(geometry_after),
                            'settings_sha256': digest(settings_after)}
        # CPU/thread/output location do not change the registered image formation settings.
        scene.cycles.device = 'CPU'
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 2
        scene.render.filepath = str(output/'ordinary_render.png')
        shutil.copyfile(BASE/'scene.json', output/'scene.json')
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
        receipt['output_blend_sha256'] = file_sha(output/'model.blend')
        receipt['output_scene_sha256'] = file_sha(output/'scene.json')
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2))
        bpy.ops.render.render(write_still=True)
        receipt['candidate_statistics'] = polygon_medians(output/'ordinary_render.png')
        candidate_median = np.asarray(receipt['candidate_statistics']['linear_rgb_median'])
        receipt['fit_polygon_diagnostic'] = {
            'before_mean_absolute_linear_median_error': float(np.mean(np.abs(base_median-source_median))),
            'after_mean_absolute_linear_median_error': float(np.mean(np.abs(candidate_median-source_median))),
            'scope': 'In-sample fitting polygon diagnostic only; the separate frozen ROI is on the same image and is not independent or held-out evidence.'}
        if file_sha(BASE/'model.blend') != receipt['input_blend_sha256'] or file_sha(BASE/'scene.json') != receipt['input_scene_sha256']:
            raise ValueError('Baseline input changed while rendering')
        if file_sha(protocol_path) != receipt['protocol_sha256'] or file_sha(SOURCE) != receipt['source_statistics']['sha256']:
            raise ValueError('Protocol or source photograph changed while rendering')
        receipt.update(status='rendered', wall_seconds=time.monotonic()-started)
    except Exception as exc:
        receipt.update(status='failed', error=repr(exc), wall_seconds=time.monotonic()-started)
        raise
    finally:
        (output/'receipt.json').write_text(json.dumps(receipt, indent=2))
    print('BEDDING_COLOR_CANDIDATE_COMPLETE', json.dumps({'output': str(output), 'status': receipt['status'],
                                                        'multiplier': receipt['applied_multiplier'],
                                                        'diagnostic': receipt['fit_polygon_diagnostic']}))


if __name__ == '__main__':
    main()
