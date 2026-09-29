"""Two frozen vent-material ablations with all four same-image groups retained.

Run in Blender with -- NEW_OUTPUT REGISTERED_PROTOCOL. No optimization or GPU.
"""
import json
import os
from pathlib import Path
import sys
import time

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_appearance_candidate import file_sha, object_snapshot, digest
from apply_bedding_color_candidate import geometry_fingerprint, scene_settings
from apply_duvet_shell_candidate import modifier_properties, run_logged, write_json

REPO = Path(__file__).resolve().parents[1]
PYTHON = '/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python'
sys.path.insert(0, str(REPO/'workflow/r2s'))
from blender_metadata import synchronize, measure


def modifiers(scene):
    return {o.name: [modifier_properties(m) for m in o.modifiers] for o in scene.objects}


def main():
    output, protocol_path = map(Path, sys.argv[sys.argv.index('--')+1:])
    output.mkdir(parents=True, exist_ok=False)
    p = json.loads(protocol_path.read_text())
    if p['schema'] != 'real2sim.shell-vent-factorial/1':
        raise ValueError('Unexpected protocol')
    if p['intervention']['linear_rgb'] != [.36, .36, .36] or p['intervention']['roughness'] != .85:
        raise ValueError('Parameters must match the previously registered vent proposal')
    receipt = {'status': 'started', 'protocol_sha256': file_sha(protocol_path),
               'script_sha256': file_sha(__file__), 'conditions': [], 'gpu_hours': 0,
               'paid_api_requests': 0, 'scope': p['scope']}
    for label, data in p['inputs'].items():
        for field in ('model', 'scene', 'render'):
            if file_sha(data[field]) != data[field+'_sha256']:
                raise ValueError('Immutable input mismatch: '+label+'/'+field)
    if file_sha(p['source_path']) != p['source_sha256']:
        raise ValueError('Source mismatch')
    images = ['baseline='+p['inputs']['baseline']['render'],
              'shell_only='+p['inputs']['shell_only']['render']]
    try:
        for label, parent in [('vent_only', 'baseline'), ('shell_vent', 'shell_only')]:
            started = time.monotonic()
            directory = output/label
            directory.mkdir()
            row = {'condition': label, 'parent': parent, 'status': 'started'}
            receipt['conditions'].append(row)
            write_json(output/'receipt.json', receipt)
            data = p['inputs'][parent]
            bpy.ops.wm.open_mainfile(filepath=data['model'])
            scene = bpy.context.scene
            spec = json.loads(Path(data['scene']).read_text())
            if any(o.rigid_body or o.rigid_body_constraint or any(m.type in {'CLOTH', 'SOFT_BODY'} for m in o.modifiers) for o in scene.objects):
                raise ValueError('Optional dynamics must be absent')
            before, geo, settings, mods = object_snapshot(scene), geometry_fingerprint(scene), scene_settings(scene), modifiers(scene)
            bounds = measure(spec)
            targets = set(p['intervention']['targets'])
            if targets != {'vent_slot_'+str(i) for i in range(15)}:
                raise ValueError('Exact 15 vent targets required')
            for name in sorted(targets):
                obj = scene.objects[name]
                if len(obj.data.materials) != 1 or obj.data.materials[0] is None:
                    raise ValueError('Unexpected vent material layout')
                obj.data = obj.data.copy()
                material = obj.data.materials[0].copy()
                obj.data.materials[0] = material
                shader = material.node_tree.nodes.get('Principled BSDF')
                if shader is None or shader.inputs['Base Color'].is_linked or shader.inputs['Roughness'].is_linked:
                    raise ValueError('Unexpected linked vent shader')
                shader.inputs['Base Color'].default_value = (.36, .36, .36, 1.)
                shader.inputs['Roughness'].default_value = .85
            bpy.context.view_layer.update()
            after = object_snapshot(scene)
            if geo != geometry_fingerprint(scene) or bounds != measure(spec) or mods != modifiers(scene) or settings != scene_settings(scene):
                raise ValueError('Geometry/modifier/camera/light invariance failed')
            for name in before:
                if before[name]['matrix_world'] != after[name]['matrix_world'] or before[name]['dimensions'] != after[name]['dimensions']:
                    raise ValueError('Transform changed: '+name)
                if name not in targets and before[name]['materials'] != after[name]['materials']:
                    raise ValueError('Non-target material changed: '+name)
            structure_hash = digest(spec['structure'])
            metadata = synchronize(spec, update=True)
            assert digest(spec['structure']) == structure_hash
            write_json(directory/'scene.json', spec)
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
            scene.render.filepath = str(directory/'render.png')
            bpy.ops.wm.save_as_mainfile(filepath=str(directory/'model.blend'))
            bpy.ops.render.render(write_still=True)
            audit_script = REPO/'workflow/r2s/blender_structure.py'
            run_logged([bpy.app.binary_path, '-b', str(directory/'model.blend'), '-t', '2', '--python-exit-code', '12',
                        '-P', str(audit_script), '--', str(directory/'scene.json'), str(directory)], directory, 'structure',
                       dict(os.environ, R2S_STRUCTURE_NO_RENDER='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2'))
            audit = json.loads((directory/'structural_audit.json').read_text())
            counts = {'assemblies': len(audit['assemblies']),
                      'joints': sum(len(a['joints_checked']) for a in audit['assemblies']),
                      'component_pairs': len(audit['component_pair_checks']),
                      'cross_assembly_pairs': len(audit['interassembly_checks'])}
            assert counts == p['structure_denominators'], counts
            ambiguous = sum(bool(x.get('requires_visual_intersection_review')) for x in audit['component_pair_checks'])
            row.update(status='completed', wall_seconds=time.monotonic()-started, invariance_pass=True,
                       input_model_sha256=data['model_sha256'], input_scene_sha256=data['scene_sha256'],
                       geometry_sha256=digest(geo), structure_sha256=structure_hash, metadata=metadata,
                       denominators=counts, structural_status=audit['status'], structural_failures=audit['failures'],
                       ambiguous_intersections=ambiguous, structural_evaluator_sha256=file_sha(audit_script),
                       output_hashes={f:file_sha(directory/f) for f in ('model.blend', 'scene.json', 'render.png', 'structural_audit.json')})
            if row['wall_seconds'] > p['budget']['cpu_wall_seconds_per_new_condition']:
                raise TimeoutError('Per-condition wall budget exceeded; stop before next condition')
            images.append(label+'='+str(directory/'render.png'))
            write_json(output/'receipt.json', receipt)
        score_args = [PYTHON, str(REPO/'tools/score_frozen_regions.py'), '--protocol', str(protocol_path), '--source', p['source_path']]
        for image in images:
            score_args += ['--image', image]
        run_logged(score_args+['--output', str(output/'appearance.json')], output, 'appearance')
        scores = json.loads((output/'appearance.json').read_text())
        m = {r['group']:r['metrics'] for r in scores['groups']}
        combined = receipt['conditions'][1]
        receipt.update(status='completed', appearance=scores,
                       combined_development_gate=(combined['structural_status']=='passed' and not combined['structural_failures'] and
                           combined['ambiguous_intersections']==0 and all(m['shell_vent'][k]['rgb_mae'] < m['baseline'][k]['rgb_mae'] for k in p['appearance_regions_xyxy'])),
                       full_visual_acceptance=False)
        for data in p['inputs'].values():
            assert all(file_sha(data[f]) == data[f+'_sha256'] for f in ('model','scene','render'))
        assert file_sha(protocol_path) == receipt['protocol_sha256']
    except Exception as exc:
        receipt.update(status='failed', error=repr(exc))
        raise
    finally:
        write_json(output/'receipt.json', receipt)
    print('SHELL_VENT_FACTORIAL_COMPLETE', receipt['combined_development_gate'])


if __name__ == '__main__':
    main()
