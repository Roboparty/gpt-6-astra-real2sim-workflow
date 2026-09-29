"""Blender controlled-rig format diagnostics; no material acceptance threshold.

CLI: -- --protocol JSON --export-dir DIR --output NEWDIR
Protocol: source_model/source_model_sha256, source_scene/source_scene_sha256,
render:{width:851,height:638,samples:8,seed:0,threads:2}.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.interchange import capture_scene, compare_snapshots, sha
from r2s.interchange import canonical_owner


def properties(value):
    result = {}
    for prop in value.bl_rna.properties:
        if prop.identifier == 'rna_type' or prop.is_readonly or prop.type in {'POINTER', 'COLLECTION'}:
            continue
        item = getattr(value, prop.identifier)
        result[prop.identifier] = list(item) if getattr(prop, 'is_array', False) else sorted(item) if isinstance(item, set) else item
    return result


def datablock(value):
    if value is None:
        return None
    tree = getattr(value, 'node_tree', None)
    return {'properties': properties(value), 'nodes': [] if tree is None else
            [{'properties': properties(node), 'inputs': [properties(socket) for socket in node.inputs],
              'image': node.image.name if getattr(node, 'image', None) else None} for node in tree.nodes],
            'links': [] if tree is None else [[link.from_node.name, link.from_socket.identifier,
                                             link.to_node.name, link.to_socket.identifier] for link in tree.links]}


def rig_state(scene, rig):
    return {'objects': {obj.name: {'type': obj.type, 'matrix_world': [list(row) for row in obj.matrix_world],
                                  'data': datablock(obj.data), 'hide_render': obj.hide_render} for obj in rig},
            'camera': scene.camera.name, 'dof': properties(scene.camera.data.dof),
            'dof_focus': scene.camera.data.dof.focus_object.name if scene.camera.data.dof.focus_object else None,
            'world': datablock(scene.world), 'view': properties(scene.view_settings),
            'display': properties(scene.display_settings), 'pixel_aspect': [scene.render.pixel_aspect_x, scene.render.pixel_aspect_y],
            'film_transparent': scene.render.film_transparent, 'dither': scene.render.dither_intensity}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def ablate_floor_normal(scene, spec, recipe):
    """A binary diagnostic only; no new physical normal estimate is created."""
    if recipe != {'entity':'floor','formats':['glb','usdc'],
                  'operation':'disconnect_only_Principled_BSDF_Normal_input',
                  'expected_material':'carpet_greytaupe','target_material_count':1}:
        raise ValueError('Unregistered normal ablation')
    ids={o['id'] for o in spec['objects']}
    targets=[o for o in scene.objects if o.type=='MESH' and canonical_owner(o,ids)=='floor']
    materials={slot.material for o in targets for slot in o.material_slots if slot.material}
    if len(materials)!=1:raise ValueError('Expected one floor material')
    mat=next(iter(materials))
    import re
    if not re.fullmatch(r'carpet_greytaupe(?:\.\d{3})?',mat.name) or not mat.use_nodes:raise ValueError('Unexpected floor material')
    others={m.name:datablock(m) for m in __import__('bpy').data.materials if m!=mat}
    other_slots={o.name:[slot.material.name if slot.material else None for slot in o.material_slots]
                 for o in scene.objects if o.type=='MESH' and o not in targets}
    before=datablock(mat);copied=mat.copy();copied.name=mat.name+'_normal_ablation'
    shaders=[n for n in copied.node_tree.nodes if n.bl_idname=='ShaderNodeBsdfPrincipled']
    if len(shaders)!=1 or len(shaders[0].inputs['Normal'].links)!=1:raise ValueError('Expected one linked Principled Normal')
    link=shaders[0].inputs['Normal'].links[0]
    removed=[link.from_node.name,link.from_socket.identifier,link.to_node.name,link.to_socket.identifier]
    copied.node_tree.links.remove(link)
    after=datablock(copied);normalized=json.loads(json.dumps(after))
    normalized['properties']['name']=before['properties']['name']
    expected=json.loads(json.dumps(before));expected['links'].remove(removed)
    if normalized!=expected:raise ValueError('Floor material changed beyond the Normal connection')
    for obj in targets:
        for slot in obj.material_slots:
            if slot.material==mat:slot.link='OBJECT';slot.material=copied
    for obj in scene.objects:
        if obj.type=='MESH' and obj not in targets:
            if other_slots[obj.name]!=[slot.material.name if slot.material else None for slot in obj.material_slots]:raise ValueError('Non-floor material assignment changed')
    if any(datablock(__import__('bpy').data.materials[name])!=value for name,value in others.items()):raise ValueError('Non-floor material graph changed')
    if datablock(mat)!=before:raise ValueError('Original shared material was edited')
    return {'removed_link':removed,'imported_material_name':mat.name,'target_objects':[o.name for o in targets],
            'material_before':before,'material_after':after,'non_floor_materials_unchanged':True,
            'scope':'Normal connection removed on private imported floor material; no physical normal repair'}


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'export-dir', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True, exist_ok=False)
    p = json.loads(args.protocol.read_text(encoding='utf-8-sig')); settings = p['render']
    report = {'status': 'started', 'protocol_sha256': sha(args.protocol), 'script_sha256': sha(__file__),
              'geometry_evaluator_sha256': sha(Path(__file__).resolve().parents[1]/'workflow/r2s/interchange.py'),
              'blender': bpy.app.version_string, 'expected_groups': ['native', 'glb', 'usdc'], 'groups': [],
              'scope': 'Controlled original camera/world/light rig; whole-format appearance diagnostic, not isolated shader causality or real reconstruction accuracy. Geometry gate checks ownership/parts/AABBs, not full surface equivalence. Exported cameras/lights are deliberately removed: this is not their interchange acceptance. No material/image-quality pass threshold.'}
    inputs = {key: Path(p[key]).resolve() for key in ('source_model', 'source_scene')}
    report['inputs'] = {key: {'path': str(path), 'expected_sha256': p[key+'_sha256']} for key, path in inputs.items()}
    write(args.output/'receipt.json', report)
    for group in report['expected_groups']:
        started = time.monotonic(); out = args.output/group; out.mkdir()
        row = {'group': group, 'status': 'failed'}; report['groups'].append(row)
        try:
            if settings != {'width': 851, 'height': 638, 'samples': 8, 'seed': 0, 'threads': 2,
                            'device': 'CPU', 'adaptive': False, 'denoise': True}:
                raise ValueError('This diagnostic requires the frozen 851x638/8-sample/seed0/2-thread recipe')
            if any(sha(path) != p[key+'_sha256'] for key, path in inputs.items()):
                raise ValueError('Frozen source bytes changed')
            spec = json.loads(inputs['source_scene'].read_text(encoding='utf-8-sig'))
            w, h = spec['camera']['image_size']
            if w*settings['height'] != h*settings['width']:
                raise ValueError('Render aspect differs from source JSON; do not silently alter projection')
            bpy.ops.wm.open_mainfile(filepath=str(inputs['source_model']))
            scene = bpy.context.scene; camera = scene.camera; world = scene.world
            if camera is None or camera.type != 'CAMERA':
                raise ValueError('Original active camera is missing')
            rig = [camera]+[obj for obj in scene.objects if obj.type == 'LIGHT']
            if any(obj.parent is not None for obj in rig):
                raise ValueError('This exact-rig diagnostic requires unparented camera/lights; do not decompose their transforms')
            if any(obj.constraints or obj.animation_data or obj.data.animation_data or
                   (getattr(obj.data, 'node_tree', None) and obj.data.node_tree.animation_data) for obj in rig):
                raise ValueError('Camera/light constraints, animation or drivers cannot be safely retained')
            if world and (world.animation_data or (world.node_tree and world.node_tree.animation_data)):
                raise ValueError('Animated world cannot be safely retained')
            if camera.data.dof.focus_object and camera.data.dof.focus_object not in rig:
                raise ValueError('DOF focus object would be removed; refuse camera change')
            if scene.view_settings.use_curve_mapping:
                raise ValueError('Custom color-management curves unsupported by this controlled-rig adapter')
            reference = capture_scene(spec); before = rig_state(scene, rig)
            matrices = {obj: obj.matrix_world.copy() for obj in rig}
            color = {key: getattr(scene.view_settings, key) for key in ('view_transform', 'look', 'exposure', 'gamma', 'use_curve_mapping')}
            display = scene.display_settings.display_device; frame = scene.frame_current
            if group != 'native':
                path = args.export_dir/('scene.'+group); row['export_sha256'] = sha(path)
                for obj in list(bpy.data.objects):
                    if obj not in rig: bpy.data.objects.remove(obj, do_unlink=True)
                # USD imports dome lighting into the ACTIVE World datablock.
                # Keep the original inactive and untouched, rather than restoring
                # a pointer to a World whose node graph was already mutated.
                scene.world = bpy.data.worlds.new('diagnostic_import_scratch_world')
                if group == 'glb': bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
                else: bpy.ops.wm.usd_import(filepath=str(path.resolve()))
                extra_rig = [obj for obj in scene.objects if obj not in rig and obj.type in {'CAMERA', 'LIGHT'}]
                for obj in list(scene.objects):
                    if obj.parent in extra_rig:
                        matrix = obj.matrix_world.copy(); obj.parent = None; obj.matrix_world = matrix
                row['removed_imported_rig'] = [obj.name for obj in extra_rig]
                for obj in extra_rig: bpy.data.objects.remove(obj, do_unlink=True)
                scene.world = world; scene.camera = camera; scene.frame_set(frame)
                scene.display_settings.display_device = display
                for key, value in color.items(): setattr(scene.view_settings, key, value)
                if sha(path) != row['export_sha256']: raise ValueError('Export bytes changed during import')
            actual = capture_scene(spec, reference['camera_identity'], reference['projection_context']['pixel_aspect'])
            if group!='native' and p.get('floor_normal_ablation'):
                row['normal_ablation']=ablate_floor_normal(scene,spec,p['floor_normal_ablation'])
                if capture_scene(spec,reference['camera_identity'],reference['projection_context']['pixel_aspect'])!=actual:
                    raise ValueError('Material ablation changed captured geometry/camera')
            after = rig_state(scene, rig); row['rig_before'] = before; row['rig_after'] = after
            row['rig_preserved'] = before == after
            geometry = compare_snapshots(reference, actual); write(out/'geometry.json', geometry)
            row['geometry_sha256'] = sha(out/'geometry.json'); row['geometry_status'] = geometry['status']
            if not row['rig_preserved']:
                raise ValueError('Controlled rig changed')
            if geometry['status'] != 'passed' and not p.get('render_failed_geometry_as_diagnostic',False):
                raise ValueError('Independent geometry gate failed; diagnostic override not registered')
            row['appearance_attribution'] = 'format diagnostic only; geometry also failed' if geometry['status'] != 'passed' else 'format diagnostic; full surface/material causality not established'
            scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = settings['samples']
            scene.cycles.seed = settings['seed']; scene.cycles.use_adaptive_sampling = False; scene.cycles.use_denoising = True
            scene.render.threads_mode = 'FIXED'; scene.render.threads = settings['threads']
            scene.render.resolution_x = settings['width']; scene.render.resolution_y = settings['height']; scene.render.resolution_percentage = 100
            scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'
            scene.render.filepath = str((out/'render.png').resolve()); bpy.ops.render.render(write_still=True)
            if rig_state(scene, rig) != before: raise ValueError('Rig changed during rendering')
            row.update(status='rendered' if geometry['status']=='passed' else 'rendered_geometry_failed', render_sha256=sha(out/'render.png'), render_settings=dict(settings, device='CPU', adaptive=False, denoise=True))
        except Exception as error:
            row['status'] = 'failed'; row['error'] = repr(error)
        row['wall_seconds'] = time.monotonic()-started; write(args.output/'receipt.json', report)
    report['sources_unchanged'] = all(path.is_file() and sha(path) == p[key+'_sha256'] for key, path in inputs.items())
    report['status'] = 'rendered_diagnostic' if report['sources_unchanged'] and all(row['status'] in {'rendered','rendered_geometry_failed'} for row in report['groups']) else 'failed'
    report['geometry_acceptance'] = all(row.get('geometry_status')=='passed' for row in report['groups'])
    if sha(args.protocol) != report['protocol_sha256']: report['status'] = 'failed'; report['protocol_changed'] = True
    write(args.output/'receipt.json', report); print(json.dumps({'status': report['status'], 'groups': [{k: row.get(k) for k in ('group', 'status', 'error')} for row in report['groups']]}))
    if report['status'] == 'failed': raise RuntimeError('Controlled appearance diagnostic failed; all groups retained')


if __name__ == '__main__':
    main()
