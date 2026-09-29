"""One preregistered static appearance proposal; no optimization or candidate selection.

Blender CLI: blender -b -t 2 --python-exit-code 12 -P tools/apply_appearance_candidate.py
             -- /remote/new-output [optional-input.blend]
The input scene.json must be beside the input blend. All model artifacts stay remote.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import bpy


BASE = Path('/home/wqz/real2sim_whole_scene_20260926/delivery_candidate/export/scene.blend')
PROPOSAL = {
    'id': 'static_duvet_folds_neutral_vent_v1',
    'parameter_provenance': 'assumed',
    'basis': 'Source-image visual estimate and engineering initialization; not measured cloth mechanics or paint reflectance',
    'shader_parameter_reference': 'https://docs.blender.org/manual/en/4.5/render/shader_nodes/shader/principled.html',
    'maximum_added_height_m': .022,
    'vent_linear_rgb': [.36, .36, .36],
    'vent_roughness': .85,
    'ridge_parameters': [
        [-.25, .32, .36, .035, .40, .018],
        [.12, .58, -.48, .026, .36, .015],
        [-.04, .86, .72, .045, .46, .022],
        [.32, .91, -.65, .024, .31, .016],
        [-.30, 1.11, -.25, .040, .35, .020],
        [.19, 1.21, .55, .033, .30, .014]],
    'interpretation': 'Single procedural geometry hypothesis from authorized baseline/source appearance; no source-photo pixels or parameter search.'}


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def material_signature(material):
    nodes, links = [], []
    if material.use_nodes:
        for node in material.node_tree.nodes:
            values = []
            for socket in node.inputs:
                if not hasattr(socket, 'default_value'):
                    continue
                value = socket.default_value
                if not isinstance(value, (str, float, int, bool)):
                    try:
                        value = list(value)
                    except TypeError:
                        value = str(value)
                values.append([socket.name, value])
            nodes.append([node.name, node.bl_idname, values,
                          node.image.name if hasattr(node, 'image') and node.image else None])
        links = [[link.from_node.name, link.from_socket.name, link.to_node.name, link.to_socket.name]
                 for link in material.node_tree.links]
    return digest({'name': material.name, 'diffuse': list(material.diffuse_color),
                   'nodes': nodes, 'links': links})


def object_snapshot(scene):
    materials = {material.name: material_signature(material) for material in bpy.data.materials}
    return {obj.name: {'matrix_world': [float(v) for row in obj.matrix_world for v in row],
                       'dimensions': list(obj.dimensions),
                       'materials': [[slot.material.name, materials[slot.material.name]] if slot.material else None
                                     for slot in obj.material_slots]}
            for obj in scene.objects}


def apply_candidate(scene):
    """Apply exactly PROPOSAL to the loaded input; returns actions and invariance audit."""
    duvet = scene.objects.get('bed_duvet')
    vents = [scene.objects.get('vent_slot_' + str(i)) for i in range(15)]
    if duvet is None or duvet.type != 'MESH' or any(obj is None for obj in vents):
        raise ValueError('Expected bed_duvet and all 15 exact vent_slot IDs are required')
    if duvet.get('appearance_proposal_applied'):
        raise ValueError('Proposal already applied; duplicate application would change the registered candidate')
    dynamic = [obj.name for obj in scene.objects if obj.rigid_body or obj.rigid_body_constraint or
               any(mod.type in {'CLOTH', 'SOFT_BODY'} for mod in obj.modifiers)]
    if dynamic:
        raise ValueError('Dynamic objects must be disabled before this static proposal: ' + str(dynamic))
    before = object_snapshot(scene)
    targets = {duvet.name} | {obj.name for obj in vents}
    # Separate datablocks prevent changing a pillow, window frame or other material user.
    duvet.data = duvet.data.copy()
    for index, material in enumerate(list(duvet.data.materials)):
        if material:
            copied = material.copy()
            copied.name = material.name + '_appearance_duvet'
            duvet.data.materials[index] = copied
    coordinates = [vertex.co.copy() for vertex in duvet.data.vertices]
    xhalf = max(abs(co.x) for co in coordinates)
    ymin, ymax = min(co.y for co in coordinates), max(co.y for co in coordinates)
    zmax = max(co.z for co in coordinates)
    changes = []
    for vertex, original in zip(duvet.data.vertices, coordinates):
        x, y, z = original
        # Freeze the perimeter and draped sides; keep the pillow/toy contact region unchanged.
        edge = max(0., 1 - (x / xhalf)**2)**2
        foot = min(1., max(0., (y-ymin)/.18))
        head = min(1., max(0., (1.42-y)/.22))
        top = min(1., max(0., (z-(zmax-.09))/.035))
        envelope = edge * foot * head * top
        value = 0.
        for cx, cy, angle, width, length, amplitude in PROPOSAL['ridge_parameters']:
            across = (x-cx)*math.cos(angle) + (y-cy)*math.sin(angle)
            along = -(x-cx)*math.sin(angle) + (y-cy)*math.cos(angle)
            across += .22*along*along
            value += amplitude * math.exp(-(across/width)**2 - (along/length)**4)
        value += .0035 * math.sin(21*x+8*y+1.2*math.sin(7*y))**4
        dz = min(PROPOSAL['maximum_added_height_m'], value*envelope)
        vertex.co.z += dz
        changes.append(dz)
    duvet.data.update()
    duvet['appearance_proposal_applied'] = PROPOSAL['id']
    for obj in vents:
        obj.data = obj.data.copy()
        if len(obj.data.materials) != 1 or obj.data.materials[0] is None:
            raise ValueError('Vent requires exactly one existing material: ' + obj.name)
        copied = obj.data.materials[0].copy()
        copied.name = obj.name + '_appearance_neutral'
        obj.data.materials[0] = copied
        shader = copied.node_tree.nodes.get('Principled BSDF') if copied.use_nodes else None
        if shader is None or shader.inputs['Base Color'].is_linked:
            raise ValueError('Unexpected vent shader; do not silently replace its node graph')
        shader.inputs['Base Color'].default_value = (*PROPOSAL['vent_linear_rgb'], 1.)
        shader.inputs['Roughness'].default_value = PROPOSAL['vent_roughness']
    bpy.context.view_layer.update()
    after = object_snapshot(scene)
    transform_changes = [name for name in before if before[name]['matrix_world'] != after[name]['matrix_world']]
    rigid_dimension_changes = [name for name in before if name != duvet.name and before[name]['dimensions'] != after[name]['dimensions']]
    unrelated_material_changes = [name for name in before if name not in targets and before[name]['materials'] != after[name]['materials']]
    if transform_changes or rigid_dimension_changes or unrelated_material_changes or set(before) != set(after):
        raise ValueError('Invariance check failed: ' + str([transform_changes, rigid_dimension_changes, unrelated_material_changes]))
    return {'proposal': PROPOSAL, 'modified_targets': sorted(targets),
            'duvet_vertices': len(changes), 'duvet_modified_vertices': sum(value > 1e-9 for value in changes),
            'duvet_added_height_max_m': max(changes), 'duvet_added_height_mean_m': sum(changes)/len(changes),
            'duvet_extent_before': before[duvet.name]['dimensions'], 'duvet_extent_after': after[duvet.name]['dimensions'],
            'audit': {'status': 'passed', 'object_count': len(before), 'non_target_count': len(before)-len(targets),
                      'all_object_transforms_unchanged': not transform_changes,
                      'rigid_dimensions_unchanged': not rigid_dimension_changes,
                      'non_target_materials_unchanged': not unrelated_material_changes,
                      'before_non_target_sha256': digest({k:v for k,v in before.items() if k not in targets}),
                      'after_non_target_sha256': digest({k:v for k,v in after.items() if k not in targets})}}


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if len(args) not in (1, 2):
        raise ValueError('Expected -- outputdir [inputblend]')
    output = Path(args[0]).resolve()
    input_blend = Path(args[1]).resolve() if len(args) == 2 else BASE
    input_scene = input_blend.with_name('scene.json')
    output.mkdir(parents=True, exist_ok=True)
    if (output/'model.blend').exists() or (output/'actions.json').exists():
        raise ValueError('New output directory required; retain earlier trial evidence')
    started = time.monotonic()
    metadata = {'schema': 'real2sim.appearance-candidate/1', 'status': 'started',
                'input_blend': str(input_blend), 'input_blend_sha256': file_sha(input_blend),
                'input_scene_sha256': file_sha(input_scene), 'script_sha256': file_sha(__file__),
                'physical_features': {'hinges': False, 'cloth': False, 'soft_bodies': False},
                'source_photo_textures_added': False, 'proposal_count': 1}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(input_blend))
        scene = bpy.context.scene
        metadata.update(apply_candidate(scene))
        metadata['camera'] = {'name': scene.camera.name, 'matrix_world': [float(v) for row in scene.camera.matrix_world for v in row],
                              'lens': scene.camera.data.lens, 'shift_x': scene.camera.data.shift_x, 'shift_y': scene.camera.data.shift_y}
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 8
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.seed = 0
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 2
        scene.render.resolution_x = 1702
        scene.render.resolution_y = 1276
        scene.render.resolution_percentage = 50
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(output/'ordinary_render.png')
        metadata['render_settings'] = {'samples': 8, 'denoise': True, 'adaptive_sampling': False,
            'seed': 0, 'threads': 2, 'device': 'CPU', 'source_resolution': [1702,1276],
            'resolution_percentage': 50, 'output_resolution': [851,638],
            'view_transform': scene.view_settings.view_transform, 'exposure': scene.view_settings.exposure}
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
        from r2s.blender_metadata import synchronize
        scene_record=json.loads(input_scene.read_text())
        metadata['metadata_sync']=synchronize(scene_record,update=True)
        (output/'scene.json').write_text(json.dumps(scene_record,indent=2))
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
        metadata['output_blend_sha256'] = file_sha(output/'model.blend')
        metadata['output_scene_sha256'] = file_sha(output/'scene.json')
        (output/'actions.json').write_text(json.dumps(metadata, indent=2))
        bpy.ops.render.render(write_still=True)
        if file_sha(input_blend) != metadata['input_blend_sha256'] or file_sha(input_scene) != metadata['input_scene_sha256']:
            raise ValueError('Input artifacts changed during the appearance proposal')
        metadata.update(status='rendered', render_sha256=file_sha(output/'ordinary_render.png'), wall_seconds=time.monotonic()-started)
    except Exception as exc:
        metadata.update(status='failed', error=repr(exc), wall_seconds=time.monotonic()-started)
        raise
    finally:
        (output/'actions.json').write_text(json.dumps(metadata, indent=2))
    print('APPEARANCE_CANDIDATE_COMPLETE', json.dumps({'output':str(output),'status':metadata['status'],'audit':metadata['audit']}))


if __name__ == '__main__':
    main()
