from pathlib import Path
import ast,copy,hashlib,json,sys,types
import numpy as np
from PIL import Image
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r/'workflow'));out=r/'output'
class ContractError(ValueError):pass
stub=types.ModuleType('r2s.contracts');stub.ContractError=ContractError;sys.modules['r2s.contracts']=stub
from r2s.structure import review_contract,file_sha
from r2s.camera import load_observations,check_scene_cameras
scene=json.loads((r/'scene.json').read_text());audit=json.loads((out/'structural_audit.json').read_text());projection=json.loads((r/'projection_check.json').read_text());result={'blender_projection':projection,'structural_status':audit['status'],'structural_failure_count':len(audit['failures']),'tests':[]}
def report(name,passed,**extra):result['tests'].append(dict(name=name,passed=bool(passed),**extra))
assert audit['status']=='passed'
for i,camera in enumerate(scene['cameras']):
 W,H=camera['image_size'];yy,xx=np.indices((H,W));rgb=np.stack((xx%256,yy%256,np.full((H,W),50+100*i)),axis=-1).astype('uint8');p=r/f'original{i}.png';Image.fromarray(rgb).save(p)
 camera.update(input_index=i,processed_path=str(p),processed_sha256=file_sha(p),source_sha256=file_sha(p))
scene['camera']=scene['cameras'][0]
(r/'scene.json').write_text(json.dumps(scene,indent=2))
# Apply the exact worker source-view crop block with only infrastructure functions injected.
worker=(r/'workflow/r2s/stage_worker.py').read_text();tree=ast.parse(worker)
node=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and ast.unparse(n.test)=="audit.get('source_views')")
code=compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(r/'workflow/r2s/stage_worker.py'),'exec')
packet=dict(camera_constraints={'cameras':scene['cameras']},original_input_allowlist=[c['processed_path'] for c in scene['cameras']])
def atomic_json(p,x):Path(p).write_text(json.dumps(x,indent=2))
env=dict(audit=audit,packet=packet,scene=r/'scene.json',out=out,Path=Path,json=json,Image=Image,file_sha=file_sha,ContractError=ContractError,atomic_json=atomic_json)
exec(code,env)
for view in audit['source_views']:
 camera=next(c for c in scene['cameras'] if c['frame_id']==view['frame_id']);xy=view['crop_xyxy'];actual=np.array(Image.open(out/view['original_crop']));expected=np.array(Image.open(camera['processed_path']).crop(xy));render_size=Image.open(out/view['render']).size
 report('matched_crop_'+view['frame_id'],np.array_equal(actual,expected) and render_size==tuple(expected.shape[1::-1]),crop=xy,render_size=render_size,original_size=list(expected.shape[1::-1]))
report('assembly_camera_default',all(x['resolved_frame_id']=='viewA' and x['error_px']<.001 for x in audit['assemblies'][0]['source_landmarks']))
report('landmark_camera_override',all(x['resolved_frame_id']=='viewB' and x['error_px']<.001 for x in audit['assemblies'][1]['source_landmarks']))
# Hash drift must be caught by the actual cropping block.
badpacket=copy.deepcopy(packet);badpacket['camera_constraints']['cameras'][1]['processed_sha256']='0'*64
try:exec(code,dict(env,packet=badpacket,audit=copy.deepcopy(audit)))
except ContractError:report('worker_hash_drift_guard',True)
else:report('worker_hash_drift_guard',False)
try:exec(code,dict(env,packet=dict(packet,camera_constraints=None),audit=copy.deepcopy(audit)))
except Exception as e:report('worker_null_constraints_legacy_fallback',False,error=type(e).__name__+': '+str(e))
else:report('worker_null_constraints_legacy_fallback',True)
# Bind the synthetic camera provenance augmentation to the synthetic audit.
atomic_json(r/'scene.json',scene);audit['source_scene_sha256']=file_sha(r/'scene.json');atomic_json(out/'structural_audit.json',audit)
binding=dict(model_sha256=audit['source_model_sha256'],scene_sha256=audit['source_scene_sha256'],structural_audit_sha256=file_sha(out/'structural_audit.json'))
review=dict(geometry_freeze_sha256=binding['model_sha256'],model_version=scene['model_version'],per_object=[dict(entity=a['entity'],status='pass',findings=['Synthetic fixture'],evidence=a['isolated_views']) for a in audit['assemblies']])
artifacts=[p.name for p in out.iterdir() if p.is_file()]
review_contract(out,review,artifacts,scene,binding);report('review_baseline',True)
def negative(name,modify):
 mutated=copy.deepcopy(audit);modify(mutated);atomic_json(out/'structural_audit.json',mutated);b=dict(binding,structural_audit_sha256=file_sha(out/'structural_audit.json'))
 try:review_contract(out,review,artifacts,scene,b)
 except ContractError as e:report(name,True,error=str(e))
 else:report(name,False,error='accepted invalid binding')
negative('review_wrong_resolved_frame',lambda a:a['assemblies'][1]['source_landmarks'][0].update(resolved_frame_id='viewA'))
negative('review_wrong_source_hash',lambda a:a['source_views'][1].update(source_sha256='0'*64))
negative('review_missing_crop_hash',lambda a:a['evidence_hashes'].pop(a['source_views'][1]['original_crop']))
negative('review_missing_source_views',lambda a:a.pop('source_views'))
atomic_json(out/'structural_audit.json',audit)
# Two-camera rigid gauge invariance and rejects.
entries=[]
for i,c in enumerate(scene['cameras']):
 T=np.eye(4);T[:3,:3]=np.array(c['rotation_world_to_cv']).T;T[:3,3]=c['position'];K=[[c['focal_px'],0,c['principal_point'][0]],[0,c['focal_y_px'],c['principal_point'][1]],[0,0,1]]
 entries.append(dict(frame_id=c['frame_id'],input_index=i,source_sha256=c['source_sha256'],image_size=c['image_size'],role='reconstruction',K=K,T_world_camera=T.tolist(),pose_source='measured',evidence=['synthetic'],distortion_model='none'))
mp=r/'input_cameras.json';atomic_json(mp,dict(schema='real2sim.camera-observations/1',units='m',up_axis='Z',camera_frame='opencv',pixel_coordinates='integer_centers',frames=entries))
G=np.array([[0,-1,0,3],[1,0,0,-2],[0,0,1,.2],[0,0,0,1.]])
cfg=dict(mode='multi',camera_observations=dict(path=str(mp),sha256=file_sha(mp),model_from_input=G.tolist()))
sources=[dict(sha256=c['source_sha256'],image_size=c['image_size']) for c in scene['cameras']];bundle=load_observations(cfg,sources)
errs=[]
for before,after in zip(scene['cameras'],bundle['cameras']):
 point=np.array([0,0,.5]);transformed=(G@np.r_[point,1])[:3];q0=np.array(before['rotation_world_to_cv'])@(point-before['position']);q1=np.array(after['rotation_world_to_cv'])@(transformed-after['position']);errs.append(float(np.max(abs(q0-q1))))
report('two_camera_single_rigid_gauge',max(errs)<1e-10,max_camera_coordinate_error=max(errs))
for name,bad in [('scale',np.diag([2,1,1,1.])),('reflection',np.diag([-1,1,1,1.])),('shear',np.array([[1,.2,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1.]]))]:
 cfg['camera_observations']['model_from_input']=bad.tolist()
 try:load_observations(cfg,sources)
 except ValueError:report('reject_'+name,True)
 else:report('reject_'+name,False)
result['code_hashes']={p.name:file_sha(p) for p in sorted((r/'workflow/r2s').glob('*.py'))};atomic_json(r/'review_result.json',result);print(json.dumps(result,indent=2))
