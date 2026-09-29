"""Run the registered two new vent-material conditions; retain all four groups.

Blender: -b -t 2 --python-exit-code 12 -P this.py -- protocol.json NEW_OUTPUT
Only remote CPU rendering; prior baseline/shell renders remain immutable.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_appearance_candidate import file_sha, object_snapshot, digest
from apply_bedding_color_candidate import geometry_fingerprint, scene_settings

REPO = Path(__file__).resolve().parents[1]
EVALUATORS = REPO.parent/'frozen_r2s_dd51a20/workflow/r2s'
PYTHON = '/home/wqz/real2sim_fresh_20260921/runtime/venv/bin/python'
sys.path.insert(0, str(REPO/'workflow/r2s'))
from blender_metadata import synchronize


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def command(argv, directory, name, extra=None):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', R2S_CPU='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    env.update(extra or {})
    with (directory/(name+'.log')).open('w') as log:
        p = subprocess.run(argv, stdout=log, stderr=log, env=env, timeout=300)
    if p.returncode:
        raise RuntimeError(name+' failed; see retained log')


def main():
    protocol_path, out = map(Path, sys.argv[sys.argv.index('--')+1:])
    protocol = json.loads(protocol_path.read_text())
    assert protocol['schema'] == 'real2sim.shell-vent-factorial/1'
    assert protocol['expected_groups'] == ['baseline','shell_only','vent_only','shell_vent']
    assert file_sha(protocol['source_path']) == protocol['source_sha256']
    for data in protocol['inputs'].values():
        for key in ('model','scene','render'):
            assert file_sha(data[key]) == data[key+'_sha256']
    out.mkdir(parents=True, exist_ok=False)
    report = {'protocol_sha256':file_sha(protocol_path),'script_sha256':file_sha(__file__),
              'expected_groups':protocol['expected_groups'],'new_conditions':[],
              'scope':protocol['scope'],'gpu_hours':0,'paid_api_requests':0}
    report['evaluator_files_sha256'] = {p.name:file_sha(p) for p in EVALUATORS.glob('*.py')}
    images = {key:data['render'] for key,data in protocol['inputs'].items()}
    for label, parent in [('vent_only','baseline'),('shell_vent','shell_only')]:
        row = {'group':label,'parent':parent,'status':'started'}
        report['new_conditions'].append(row)
        directory = out/label; directory.mkdir(); started = time.monotonic()
        try:
            data = protocol['inputs'][parent]
            bpy.ops.wm.open_mainfile(filepath=data['model'])
            scene = bpy.context.scene
            before = object_snapshot(scene); geometry = geometry_fingerprint(scene); settings = scene_settings(scene)
            assert not any(o.rigid_body or o.rigid_body_constraint or any(m.type in {'CLOTH','SOFT_BODY'} for m in o.modifiers) for o in scene.objects)
            targets = protocol['intervention']['targets']
            assert targets == ['vent_slot_'+str(i) for i in range(15)]
            for name in targets:
                obj = scene.objects[name]
                assert len(obj.material_slots)==1 and obj.type=='MESH'
                obj.data = obj.data.copy()
                mat = obj.material_slots[0].material.copy(); mat.name = name+'_factorial_neutral'
                obj.data.materials[0] = mat
                shader = mat.node_tree.nodes['Principled BSDF']
                assert not shader.inputs['Base Color'].is_linked and not shader.inputs['Roughness'].is_linked
                shader.inputs['Base Color'].default_value = (*protocol['intervention']['linear_rgb'],1)
                shader.inputs['Roughness'].default_value = protocol['intervention']['roughness']
            bpy.context.view_layer.update(); after = object_snapshot(scene)
            assert geometry == geometry_fingerprint(scene) and settings == scene_settings(scene)
            for name in before:
                assert before[name]['matrix_world']==after[name]['matrix_world'] and before[name]['dimensions']==after[name]['dimensions']
                if name not in targets: assert before[name]['materials']==after[name]['materials']
            spec = json.loads(Path(data['scene']).read_text()); structure_hash = digest(spec['structure'])
            row['metadata'] = synchronize(spec, update=True)
            assert digest(spec['structure']) == structure_hash
            row['held_constants_verified'] = True
            row['raw_mesh_uv_sha256'] = digest(geometry)
            row['structure_sha256'] = structure_hash
            write(directory/'scene.json',spec)
            scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8
            scene.cycles.seed=0;scene.cycles.use_adaptive_sampling=False;scene.cycles.use_denoising=True
            scene.render.threads_mode='FIXED';scene.render.threads=2
            scene.render.resolution_x=1702;scene.render.resolution_y=1276;scene.render.resolution_percentage=50
            scene.render.image_settings.file_format='PNG';scene.render.filepath=str(directory/'ordinary_render.png')
            row['effective_render_settings']=scene_settings(scene)
            bpy.ops.wm.save_as_mainfile(filepath=str(directory/'model.blend'))
            bpy.ops.render.render(write_still=True)
            images[label]=str(directory/'ordinary_render.png')
            row['model_sha256']=file_sha(directory/'model.blend')
            row['scene_sha256']=file_sha(directory/'scene.json')
            row['render_sha256']=file_sha(images[label])
            command([bpy.app.binary_path,'-b',str(directory/'model.blend'),'-t','2','--python-exit-code','12',
                     '-P',str(EVALUATORS/'blender_structure.py'),'--',str(directory/'scene.json'),str(directory)],
                    directory,'structure',{'R2S_STRUCTURE_NO_RENDER':'1'})
            audit=json.loads((directory/'structural_audit.json').read_text())
            counts={'assemblies':len(audit['assemblies']),'joints':sum(len(a['joints_checked']) for a in audit['assemblies']),
                    'component_pairs':len(audit['component_pair_checks']),'cross_assembly_pairs':len(audit['interassembly_checks'])}
            assert counts==protocol['structure_denominators']
            row['structure']={'status':audit['status'],'denominators':counts,'failures':audit['failures'],
                              'ambiguous_intersections':sum(bool(p.get('requires_visual_intersection_review')) for p in audit['component_pair_checks']),
                              'sha256':file_sha(directory/'structural_audit.json')}
            # Same established opening annotation and static pipeline for both new conditions.
            static = directory/'static';static.mkdir()
            collision_spec=copy.deepcopy(spec)
            room=json.loads((REPO/'examples/independent_whole_scene_20260926/authoring/room.json').read_text())
            w=room['window'];collision_spec['room']['openings']=[{'wall':'wall_left','bounds':[w['y0'],w['y1'],w['bottom'],w['top']]}]
            write(static/'scene.json',collision_spec)
            command([bpy.app.binary_path,'-b',str(directory/'model.blend'),'-t','2','--python-exit-code','12',
                     '-P',str(EVALUATORS/'blender_export.py'),'--',str(static/'scene.json'),str(static),'--geometry-only'],static,'export')
            command([PYTHON,str(EVALUATORS/'simulation.py'),str(static/'scene.json'),str(static)],static,'simulation')
            row['static_audit']=json.loads((static/'simulation_audit.json').read_text())
            row['status']='evaluated'
        except Exception as exc:
            row.update(status='failed',error=repr(exc))
        row['wall_seconds']=time.monotonic()-started
        write(out/'report.json',report)
    if set(images)==set(protocol['expected_groups']):
        command([PYTHON,str(REPO/'tools/score_frozen_regions.py'),'--protocol',str(protocol_path),
                 '--source',protocol['source_path'],'--output',str(out/'appearance.json')]+
                [item for name in protocol['expected_groups'] for item in ('--image',name+'='+images[name])],out,'appearance')
        report['appearance']=json.loads((out/'appearance.json').read_text())
    report['immutable_inputs_unchanged']=all(file_sha(d[k])==d[k+'_sha256'] for d in protocol['inputs'].values() for k in ('model','scene','render'))
    assert report['evaluator_files_sha256']=={p.name:file_sha(p) for p in EVALUATORS.glob('*.py')}
    report['other_view_status']='No independent real view exists; whole-scene visual promotion remains unavailable'
    write(out/'report.json',report)
    print(json.dumps({'output':str(out),'conditions':[(r['group'],r['status'],r.get('error')) for r in report['new_conditions']]}))


if __name__=='__main__':main()
