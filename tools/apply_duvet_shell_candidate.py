"""One registered Solidify offset correction; no anchor, thickness or threshold search.

blender -b -t 2 --python-exit-code 12 -P tools/apply_duvet_shell_candidate.py
        -- /remote/new-output /remote/DUVET_SHELL_PROTOCOL_20260929.json
"""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_appearance_candidate import file_sha, object_snapshot, digest
from apply_bedding_color_candidate import geometry_fingerprint, scene_settings


ROOT = Path('/home/wqz/real2sim_capability_20260929')
REPO = ROOT/'repo'
PYTHON = '/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python'
SOURCE = Path('/home/wqz/real2sim_whole_scene_20260926/input/01_bedroom.jpg')
BASELINE_IMAGE = ROOT/'runs/combined_comparison_001/baseline/render.png'
ROI_PROTOCOL = REPO/'docs/research/COMBINED_PROTOCOL_20260929.json'
BASE_HASH = 'e140b8ae0f133a87cbaa77e576ea164512e57c3bd9a56552841f8596b9126e51'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def modifier_properties(modifier):
    result = {}
    for prop in modifier.bl_rna.properties:
        if prop.identifier == 'rna_type' or prop.is_readonly or prop.type in {'POINTER', 'COLLECTION'}:
            continue
        value = getattr(modifier, prop.identifier)
        result[prop.identifier] = list(value) if getattr(prop, 'is_array', False) else value
    return result


def run_logged(argv, output, name, environment=None):
    write_json(output/(name+'-command.json'), {'argv': argv, 'R2S_STRUCTURE_NO_RENDER': (environment or {}).get('R2S_STRUCTURE_NO_RENDER')})
    completed = subprocess.run(argv, text=True, capture_output=True, env=environment, timeout=900)
    (output/(name+'.log')).write_text(completed.stdout+'\n'+completed.stderr, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError(name+' subprocess failed: '+str(completed.returncode))


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if len(args) != 2:
        raise ValueError('Expected -- NEW_OUTPUT REGISTERED_PROTOCOL.json')
    output, protocol_path = (Path(value).resolve() for value in args)
    protocol = json.loads(protocol_path.read_text(encoding='utf-8-sig'))
    intervention = protocol['intervention']
    expected = {'object': 'bed_duvet', 'modifier': 'cloth_thickness', 'property': 'offset',
                'before': -1, 'after': 1, 'thickness_m_unchanged': .009}
    if protocol.get('schema') != 'real2sim.duvet-shell-orientation/1' or intervention != expected or protocol.get('expected_candidates') != 1:
        raise ValueError('Protocol differs from the single registered shell orientation proposal')
    input_model, input_scene = Path(protocol['input_model']), Path(protocol['input_scene'])
    output.mkdir(parents=True, exist_ok=True)
    if (output/'receipt.json').exists() or (output/'model.blend').exists():
        raise ValueError('Preserve previous results; new output directory required')
    started = time.monotonic()
    receipt = {'schema': 'real2sim.duvet-shell-candidate/1', 'status': 'started',
               'protocol_sha256': file_sha(protocol_path), 'script_sha256': file_sha(__file__),
               'input_model': str(input_model), 'input_model_sha256': file_sha(input_model),
               'input_scene': str(input_scene), 'input_scene_sha256': file_sha(input_scene),
               'baseline_render_sha256': file_sha(BASELINE_IMAGE), 'source_sha256': file_sha(SOURCE),
               'intervention': intervention, 'candidate_count': 1,
               'physical_features': {'hinges': False, 'cloth': False, 'soft_bodies': False},
               'parameter_provenance': 'Existing assumed static 9mm textile thickness; shell orientation test, not cloth-physics calibration'}
    write_json(output/'receipt.json', receipt)
    try:
        if receipt['input_model_sha256'] != BASE_HASH or protocol['input_model_sha256'] != BASE_HASH:
            raise ValueError('Input must be the immutable original independent scene, not a combined candidate')
        bpy.ops.wm.open_mainfile(filepath=str(input_model))
        scene = bpy.context.scene
        spec = json.loads(input_scene.read_text())
        structure_before = digest(spec['structure'])
        joint_count = sum(len(assembly['joints']) for assembly in spec['structure']['assemblies'])
        if joint_count != 49:
            raise ValueError('The original complete 49-joint denominator must remain intact')
        if any(obj.rigid_body or obj.rigid_body_constraint or any(mod.type in {'CLOTH','SOFT_BODY'} for mod in obj.modifiers)
               for obj in scene.objects):
            raise ValueError('Optional dynamics must be absent from this static trial')
        target = scene.objects['bed_duvet']
        modifier = target.modifiers['cloth_thickness']
        if modifier.type != 'SOLIDIFY' or modifier.offset != -1 or not math.isclose(modifier.thickness, .009, abs_tol=1e-8):
            raise ValueError('Input cloth shell differs from registered precondition')
        objects_before = object_snapshot(scene)
        geometry_before = geometry_fingerprint(scene)
        settings_before = scene_settings(scene)
        modifier_before = modifier_properties(modifier)
        modifier.offset = 1.
        bpy.context.view_layer.update()
        modifier_after = modifier_properties(modifier)
        changes = {key: [value, modifier_after[key]] for key,value in modifier_before.items() if modifier_after[key] != value}
        if changes != {'offset': [-1., 1.]}:
            raise ValueError('More than the registered modifier offset changed: '+str(changes))
        objects_after = object_snapshot(scene)
        geometry_after = geometry_fingerprint(scene)
        transforms = [name for name in objects_before if objects_before[name]['matrix_world'] != objects_after[name]['matrix_world']]
        materials = [name for name in objects_before if objects_before[name]['materials'] != objects_after[name]['materials']]
        unrelated_dimensions = [name for name in objects_before if name != target.name and objects_before[name]['dimensions'] != objects_after[name]['dimensions']]
        if transforms or materials or unrelated_dimensions or geometry_before != geometry_after or settings_before != scene_settings(scene):
            raise ValueError('Held-constant audit failed: '+str([transforms, materials, unrelated_dimensions]))
        # Synchronize only actual evaluated AABB metadata, preserving structure and every other field.
        sys.path.insert(0, str(REPO/'workflow/r2s'))
        from blender_metadata import measure
        bounds = measure(spec)
        original_spec = copy.deepcopy(spec)
        aabb_updates = []
        for obj in spec['objects']:
            lo, hi = bounds[obj['id']]
            previous = {'position': obj['position'], 'dimensions': obj['dimensions']}
            actual = {'position': [(a+b)/2 for a,b in zip(lo,hi)], 'dimensions': [b-a for a,b in zip(lo,hi)]}
            if previous != actual:
                aabb_updates.append({'id': obj['id'], 'before': previous, 'after': actual})
            obj.update(actual)
        erased = copy.deepcopy(spec)
        for original, edited in zip(original_spec['objects'], erased['objects']):
            edited['position'], edited['dimensions'] = original['position'], original['dimensions']
        if erased != original_spec or digest(spec['structure']) != structure_before:
            raise ValueError('Scene changed beyond permitted AABB metadata')
        receipt['audit'] = {'status': 'passed', 'object_count': len(objects_before),
                            'base_mesh_and_uv_before_sha256': digest(geometry_before),
                            'base_mesh_and_uv_after_sha256': digest(geometry_after),
                            'all_transforms_unchanged': True, 'all_materials_unchanged': True,
                            'camera_lights_unchanged': True, 'only_modifier_change': changes,
                            'thickness_m_before': modifier_before['thickness'], 'thickness_m_after': modifier_after['thickness'],
                            'structure_before_sha256': structure_before, 'structure_after_sha256': digest(spec['structure']),
                            'joint_count_before': joint_count, 'joint_count_after': joint_count,
                            'aabb_metadata_updates': aabb_updates,
                            'target_evaluated_dimensions_before': objects_before[target.name]['dimensions'],
                            'target_evaluated_dimensions_after': objects_after[target.name]['dimensions']}
        write_json(output/'scene.json', spec)
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 8
        scene.cycles.seed = 0
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.use_denoising = True
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = 2
        scene.render.resolution_x = 1702
        scene.render.resolution_y = 1276
        scene.render.resolution_percentage = 50
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(output/'ordinary_render.png')
        receipt['render_settings'] = scene_settings(scene)
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
        receipt['output_model_sha256'] = file_sha(output/'model.blend')
        receipt['output_scene_sha256'] = file_sha(output/'scene.json')
        write_json(output/'receipt.json', receipt)
        bpy.ops.render.render(write_still=True)
        receipt['output_render_sha256'] = file_sha(output/'ordinary_render.png')
        environment = os.environ.copy()
        environment['R2S_STRUCTURE_NO_RENDER'] = '1'
        structure_script = REPO/'workflow/r2s/blender_structure.py'
        receipt['structural_evaluator_sha256'] = file_sha(structure_script)
        run_logged([bpy.app.binary_path, '-b', str(output/'model.blend'), '-t', '2', '--python-exit-code', '12',
                    '-P', str(structure_script), '--', str(output/'scene.json'), str(output)], output, 'structure', environment)
        structural = json.loads((output/'structural_audit.json').read_text())
        measured_joint_count = sum(len(assembly['joints_checked']) for assembly in structural['assemblies'])
        receipt['structural_result'] = {'status': structural['status'], 'joints_checked': measured_joint_count,
                                        'passed_joints': sum(joint['status']=='pass' for assembly in structural['assemblies'] for joint in assembly['joints_checked']),
                                        'failures': structural['failures'], 'audit_sha256': file_sha(output/'structural_audit.json')}
        if measured_joint_count != 49:
            raise ValueError('Structural evaluator did not retain all 49 joints')
        score_script = REPO/'tools/score_frozen_regions.py'
        run_logged([PYTHON, str(score_script), '--protocol', str(ROI_PROTOCOL), '--source', str(SOURCE),
                    '--image', 'unchanged_baseline='+str(BASELINE_IMAGE),
                    '--image', 'duvet_shell_only='+str(output/'ordinary_render.png'),
                    '--output', str(output/'appearance_metrics.json')], output, 'appearance_score')
        receipt['appearance_metrics'] = json.loads((output/'appearance_metrics.json').read_text())
        if file_sha(input_model) != BASE_HASH or file_sha(input_scene) != receipt['input_scene_sha256'] or file_sha(protocol_path) != receipt['protocol_sha256']:
            raise ValueError('Immutable input or protocol changed during trial')
        receipt.update(status='completed', structural_acceptance=structural['status'], wall_seconds=time.monotonic()-started)
    except Exception as exc:
        receipt.update(status='failed', error=repr(exc), wall_seconds=time.monotonic()-started)
        raise
    finally:
        write_json(output/'receipt.json', receipt)
    print('DUVET_SHELL_CANDIDATE_COMPLETE', json.dumps({'output': str(output), 'status':receipt['status'],
                                                     'structural_result': receipt['structural_result']}))


if __name__ == '__main__':
    main()
