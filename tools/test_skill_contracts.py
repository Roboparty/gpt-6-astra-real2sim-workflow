"""Run observable positive/negative tests in a fresh directory; no model/Blender needed."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--skills', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
cases = []
started = time.monotonic()

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

room = load('room', a.skills/'blender-roomkit/scripts/roomkit.py')
ref = load('ref', a.skills/'pi3x-scene-reference/scripts/reference.py')
refine = load('refine', a.skills/'real2sim-local-refine/scripts/refine.py')

def check(name, fn, reject=False):
    try:
        value = fn()
        if reject:
            raise AssertionError('Expected rejection but input was accepted')
        cases.append({'case': name, 'passed': True})
        return value
    except (ValueError, KeyError, FileExistsError) as e:
        cases.append({'case': name, 'passed': reject, 'retained_error': str(e)})
    except Exception as e:
        cases.append({'case': name, 'passed': False, 'error': repr(e)})

def require(condition):
    assert condition

def write(name, value):
    path = a.output/name
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    return path

scene = json.loads((a.skills/'blender-roomkit/assets/room.json').read_text())
check('roomkit_valid_all_recipes', lambda: room.validate(scene))
for name, mutate in [
    ('negative_dimension', lambda x: x['parts'][0]['size'].__setitem__(0, -1)),
    ('nan_dimension', lambda x: x['parts'][0]['size'].__setitem__(1, float('nan'))),
    ('duplicate_part', lambda x: x['parts'].append(copy.deepcopy(x['parts'][0]))),
    ('implicit_prior', lambda x: x['parts'][0].__setitem__('prior_status', 'measured')),
    ('unimplemented_cloth', lambda x: x.__setitem__('dynamics', {'cloth': True})),
    ('reserved_collision_id', lambda x: x['parts'][0].__setitem__('id', 'floor__collision')),
    ('unsupported_recipe', lambda x: x['parts'][0].__setitem__('kind', 'neural_room')),
]:
    value = copy.deepcopy(scene); mutate(value)
    check('roomkit_reject_' + name, lambda v=value: room.validate(v), True)

for i in range(3):
    Image.fromarray(np.full((4, 4, 3), i*50, dtype=np.uint8)).save(a.output/f'f{i}.png')
config = {'preprocessing': {'resize': 'none', 'crop': 'none', 'color': 'RGB', 'output_size_wh': [4, 4]},
          'frames': [{'id': f'f{i}', 'path': f'f{i}.png', 'pts_seconds': i*.1, 'role': 'fit' if i<2 else 'heldout'} for i in range(3)]}
config_path = write('frame-config.json', config)
manifest = check('pi3x_freeze_ordered_frames', lambda: ref.freeze(config, a.output))
manifest_path = write('frozen-input.json', manifest)
points = np.zeros((1, 2, 4, 4, 3), dtype=np.float32)
points[..., 2] = 1
arrays = {'points': points.copy(), 'local_points': points.copy(),
          'conf': np.zeros((1, 2, 4, 4, 1), dtype=np.float32),
          'camera_poses': np.broadcast_to(np.eye(4, dtype=np.float32), (1, 2, 4, 4)).copy()}
npz_path = a.output/'synthetic.npz'; np.savez(npz_path, **arrays)
provenance = {k: manifest[k] for k in ('code_revision', 'weight_revision', 'weight_sha256', 'preprocessing')}
provenance.update(input_sha256=ref.sha(manifest_path), npz_sha256=ref.sha(npz_path), frame_ids=['f0','f1'], kind='synthetic_contract')
write('provenance.json', provenance)
result = check('pi3x_consume_valid_synthetic', lambda: ref.consume(manifest_path, npz_path, provenance, .5))
write('reference-receipt.json', result)
check('pi3x_never_claim_synthetic_inference', lambda: require(result['inference']=='not_run' and result['geometry_accuracy']=='unverified'))
check('pi3x_raw_zero_logit_sigmoid_half', lambda: require(result['retained_fraction_by_frame']==[1.0,1.0]))
rotated={k:v.copy() for k,v in arrays.items()}
rotated['camera_poses'][0,1,:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]]
rotated['camera_poses'][0,1,:3,3]=[1,2,3]
rotated['points'][0,1]=rotated['local_points'][0,1] @ rotated['camera_poses'][0,1,:3,:3].T + [1,2,3]
rotated_file=a.output/'rotated.npz'; np.savez(rotated_file,**rotated)
rotated_prov=copy.deepcopy(provenance);rotated_prov['npz_sha256']=ref.sha(rotated_file)
check('pi3x_nonidentity_c2w_convention',lambda:ref.consume(manifest_path,rotated_file,rotated_prov,.5))
for name, mutate in [
    ('heldout_leakage', lambda x: x.__setitem__('frame_ids', ['f0','f2'])),
    ('wrong_frame_order', lambda x: x.__setitem__('frame_ids', ['f1','f0'])),
    ('wrong_revision', lambda x: x.__setitem__('code_revision', '0'*40)),
    ('preprocess_drift', lambda x: x.__setitem__('preprocessing', {'resize':'changed'})),
    ('output_hash_drift', lambda x: x.__setitem__('npz_sha256', '0'*64)),
    ('backend_without_receipt', lambda x: x.__setitem__('kind', 'backend_output')),
]:
    value=copy.deepcopy(provenance); mutate(value)
    check('pi3x_reject_'+name, lambda v=value: ref.consume(manifest_path,npz_path,v,.5), True)
for name, mutate in [
    ('nan_point', lambda x: x['points'].__setitem__((0,0,0,0,0), np.nan)),
    ('non_rotation', lambda x: x['camera_poses'].__setitem__((0,0,0,0), 2)),
    ('world_point_inconsistency', lambda x: x['points'].__setitem__((0,0,0,0,0), 1)),
    ('missing_conf_axis', lambda x: x.__setitem__('conf', x['conf'][...,0])),
]:
    arr={k:v.copy() for k,v in arrays.items()}; mutate(arr)
    file=a.output/(name+'.npz'); np.savez(file, **arr)
    prov=copy.deepcopy(provenance); prov['npz_sha256']=ref.sha(file)
    check('pi3x_reject_'+name, lambda f=file,v=prov: ref.consume(manifest_path,f,v,.5), True)
check('pi3x_reject_nan_threshold', lambda: ref.consume(manifest_path,npz_path,provenance,float('nan')), True)
duplicate=copy.deepcopy(config); duplicate['frames'][1]['path']='f0.png'
check('pi3x_reject_duplicate_frame_bytes', lambda: ref.freeze(duplicate,a.output),True)
original=(a.output/'f0.png').read_bytes(); (a.output/'f0.png').write_bytes(b'changed')
check('pi3x_reject_frame_hash_drift', lambda: ref.consume(manifest_path,npz_path,provenance,.5),True)
(a.output/'f0.png').write_bytes(original)

src=np.zeros((8,8,3),dtype=np.uint8); old=src.copy(); old[:4]=100
new=src.copy(); new[4:]=50
for name,arr in [('source',src),('baseline',old),('candidate',new)]:
    Image.fromarray(arr).save(a.output/(name+'.png'))
view={'id':'front','role':'fit','source_camera_sha256':'a'*64,'candidate_camera_sha256':'a'*64,'baseline_camera_sha256':'a'*64,
      **{k:{'path':k+'.png','sha256':ref.sha(a.output/(k+'.png'))} for k in ('source','baseline','candidate')},
      'regions':[{'id':'target','xyxy':[0,0,8,4],'part_ids':['duvet']},{'id':'other','xyxy':[0,4,8,8],'part_ids':['pillow']}]}
heldout=copy.deepcopy(view); heldout.update(id='side',role='heldout')
protocol={'schema':'real2sim-roi/1','views':[view,heldout]}
write('roi-protocol.json',protocol)
diag=check('refine_diagnose_fixed_regions',lambda:refine.diagnose(protocol,a.output))
write('roi-report.json',diag)
check('refine_retains_non_target_regression',lambda:require(diag['regions'][0]['delta']<0 and diag['regions'][1]['worsened']))
check('refine_keeps_heldout_out_of_edit_priority',lambda:require(all(r['role']=='fit' for r in diag['edit_priority_fit_only'])))
check('refine_does_not_promote_from_mae',lambda:require(diag['acceptance']=='not_determined'))
for name, mutate in [
    ('camera_drift',lambda x:x['views'][0].__setitem__('candidate_camera_sha256','b'*64)),
    ('baseline_camera_drift',lambda x:x['views'][0].__setitem__('baseline_camera_sha256','b'*64)),
    ('source_hash_drift',lambda x:x['views'][0]['source'].__setitem__('sha256','0'*64)),
    ('outside_roi',lambda x:x['views'][0]['regions'][0].__setitem__('xyxy',[0,0,90,90])),
    ('empty_denominator',lambda x:x['views'][0].__setitem__('regions',[])),
]:
    value=copy.deepcopy(protocol); mutate(value)
    check('refine_reject_'+name,lambda v=value:refine.diagnose(v,a.output),True)
base_path=write('roomkit-base.json',scene)
change={'schema':'real2sim-part-change/1','scene_sha256':ref.sha(base_path),'part_id':'duvet','mode':'geometry',
        'reason':'assumed fixture fold correction','source_region':'front/target','set':{'fold_amplitude':.015}}
change_path=write('one-change.json',change)
candidate=check('refine_edit_one_part',lambda:refine.edit(scene,change))
check('refine_preserves_other_parts',lambda:require(all(x==y for x,y in zip(scene['parts'],candidate['parts']) if x['id']!='duvet')))
check('refine_preserves_original_scene',lambda:require(scene['parts'][2]['fold_amplitude']==.025))
material=copy.deepcopy(change);material.update(mode='material',set={'color':[.2,.3,.4],'roughness':.7})
material_candidate=check('refine_material_only_edit',lambda:refine.edit(scene,material))
check('refine_material_preserves_geometry',lambda:require(all(material_candidate['parts'][2][k]==scene['parts'][2][k] for k in ('size','position','rotation','fold_amplitude'))))
light=copy.deepcopy(change);light.update(mode='lighting',set={'energy':100})
check('refine_reject_implicit_lighting_adapter',lambda:refine.edit(scene,light),True)
mixed=copy.deepcopy(change); mixed['set']['color']=[1,0,0]
check('refine_reject_mixed_material_geometry',lambda:refine.edit(scene,mixed),True)
bad=copy.deepcopy(change); bad['set']['fold_amplitude']=float('inf')
check('refine_reject_infinite_parameter',lambda:refine.edit(scene,bad),True)

def cli(script,args,expected=0):
    r=subprocess.run([sys.executable,str(script),*map(str,args)],capture_output=True,text=True)
    (a.output/('cli-'+str(len(cases))+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    assert (r.returncode==0) == (expected==0), r.stderr

ref_script=a.skills/'pi3x-scene-reference/scripts/reference.py'
edit_script=a.skills/'real2sim-local-refine/scripts/refine.py'
check('pi3x_freeze_cli',lambda:cli(ref_script,['freeze',config_path,a.output/'cli-frozen.json']))
check('pi3x_refuse_output_overwrite',lambda:cli(ref_script,['freeze',config_path,a.output/'cli-frozen.json'],1))
check('pi3x_consume_cli',lambda:cli(ref_script,['consume',manifest_path,npz_path,a.output/'provenance.json',a.output/'cli-reference.json']))
check('refine_diagnose_cli',lambda:cli(edit_script,['diagnose',a.output/'roi-protocol.json',a.output/'cli-roi.json']))
check('refine_edit_cli',lambda:cli(edit_script,['edit',base_path,change_path,a.output/'cli-candidate.json']))
bad=copy.deepcopy(change);bad['scene_sha256']='0'*64
write('bad-change.json',bad)
check('refine_cli_reject_stale_base',lambda:cli(edit_script,['edit',base_path,a.output/'bad-change.json',a.output/'must-not-exist.json'],1))
report={'passed':sum(c['passed'] for c in cases),'total':len(cases),'wall_seconds':time.monotonic()-started,
        'scope':'synthetic contracts and CLI; no model inference or real geometry accuracy','cases':cases}
write('results.json',report)
print(json.dumps(report,indent=2))
sys.exit(0 if report['passed']==report['total'] else 1)
