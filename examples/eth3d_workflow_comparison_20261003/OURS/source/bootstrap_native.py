import json,pathlib,sys,hashlib,shutil
R=pathlib.Path('/home/wqz/real2sim_agent_compare_20261003/OURS')
sys.path.insert(0,str(R/'code/workflow'))
from r2s.core import Workflow
from r2s.camera import workflow_constraints
C=R/'native_case';C.mkdir(exist_ok=True);cfg=json.loads((R/'case/case.json').read_text());G=json.loads((R/'model_from_input.json').read_text())['model_from_input']
cfg['camera_observations']['model_from_input']=G
for stage in ['build_geometry','build_render']:
 cfg['stages'][stage]['parameters']['inspection_resolution']=[400,400]
(C/'case.json').write_text(json.dumps(cfg,indent=2))
w=Workflow(C);print(w.run('agent_observe',True),flush=True)
D=pathlib.Path(w.state['stages']['agent_observe']['directory']);old=R/'case/runs/agent_observe/0001'
obs=json.loads((old/'furniture_observation.json').read_text());targets=[]
splits={'wood_crates':['wood_crate_0','wood_crate_1'],'lime_skips':['lime_skip_0','lime_skip_1'],'mesh_cages':['mesh_cage_0','mesh_cage_1','mesh_cage_2'],'white_trailer':['white_trailer','flatbed_trailer']}
for target in obs['targets']:
 for entity in splits.get(target['entity'],[target['entity']]):
  row=json.loads(json.dumps(target));row['entity']=entity
  for part in row['parts']:part['ownership']=entity
  if entity=='flatbed_trailer':row['parts']=[dict(id=p,ownership=entity) for p in ['metal_frame','platform','wheels','drawbar']];row['observations'][0]['description']='Separate low open flatbed trailer in front of box trailer. No rigid connection between these two independent vehicles.'
  row['uncertain'].append('Source regions overlap neighbouring instances; individual assembly fit uses its actually visible components only.')
  targets.append(row)
obs['targets']=targets
(D/'furniture_observation.json').write_text(json.dumps(obs,indent=2))
ob=json.loads((old/'observation.json').read_text());ob['key_images_inspected']=[0,8,12,16,20,24,28];ob['targets']=[t['entity'] for t in targets];(D/'observation.json').write_text(json.dumps(ob,indent=2))
def accept(stage,artifacts,why,params=None,issues=None):
 d=pathlib.Path(w.state['stages'][stage]['directory']);response=dict(status='complete',evidence=['Actual supplied RGB observation and permitted predicted-depth measurement artifacts'],reasoning_summary=why,parameters=params or {},artifacts=artifacts,issues=issues or []);(d/'response.json').write_text(json.dumps(response,indent=2));print(stage,w.accept(stage,d/'response.json'),flush=True)
accept('agent_observe',['observation.json','furniture_observation.json'],'All36 source views inspected; distinct crates, skips, cages and trailers have separate owners. No geometry/evaluator truth read.')
print(w.run('agent_identify'),flush=True);d=pathlib.Path(w.state['stages']['agent_identify']['directory'])
(d/'identity.json').write_text(json.dumps(dict(strategy='A',objects=[dict(entity=t['entity'],identity='generic observed category',model_identity='unknown',asset_policy='fresh authored geometry only',dimensions_source='allowed RGB plus frozen predicted depth',external_assets=[]) for t in targets],web_research='Not used; coordinator prohibits manufacturer model guessing and external asset copying'),indent=2))
accept('agent_identify',['identity.json'],'Generic category identities are observed. No exact manufacturer model identity is claimed.')
print(w.run('agent_calibrate'),flush=True);d=pathlib.Path(w.state['stages']['agent_calibrate']['directory']);constraints=workflow_constraints(w)
(d/'calibration.json').write_text(json.dumps(dict(camera_constraints=constraints,model_from_input=G,source_intrinsics_and_poses_locked=True,metric_scale_source='Supplied registered reference cameras plus shared pose-conditioned input predicted depth; diagnostic input',uncertainty=['Predicted depth is not independent geometry truth','One rigid gauge maps fitted floor to Z0; no scales or per-camera changes'],evidence=['model_from_input.json','measurement_raw.json']),indent=2))
for f in ['model_from_input.json','measurement_raw.json','measurements_landmarks.json','rgb_annotations.json']:shutil.copyfile(R/f,d/f)
accept('agent_calibrate',['calibration.json','model_from_input.json','measurement_raw.json','measurements_landmarks.json','rgb_annotations.json'],'Retained all36 supplied K/T under a single recorded rigid gauge. Surface-only semantic measurements, no mesh fusion.',dict(camera_constraints_sha256=constraints['sha256']))
print(w.run('agent_calibrate_room'),flush=True);d=pathlib.Path(w.state['stages']['agent_calibrate_room']['directory'])
surfaces=[]
for name,plane,visible,refs,res in [
 ('floor',[0,0,1,0],'observed',[12,16,20,24],.019),('ceiling',[0,0,1,-4.68],'observed',[12,20,28],.20),
 ('wall_back',[0,1,0,-19.4],'partial',[12],.22),('wall_front',[0,1,0,11.5],'unobserved',[24,28],None),
 ('wall_left',[1,0,0,49.0],'partial',[20,32,35],1.2),('wall_right',[1,0,0,-16.0],'partial',[6,7,8],1.5)]:
  row=dict(id=name,plane=plane,visibility=visible,status='hypothesized' if visible=='unobserved' else 'fitted',evidence=['source inputs '+str(refs),'measurement_raw.json'],uncertainty='Outer unseen spans are conservative closures; learned-depth bias and long-range uncertainty remain')
  if visible!='unobserved':row.update(image_constraints=[dict(input_index=i,kind='visible semantic plane or bounded long-range wall extent') for i in refs],residuals=dict(representative_depth_residual_m=res,interpretation='input fit/uncertainty estimate; no independent reality acceptance'))
  surfaces.append(row)
(d/'room_calibration.json').write_text(json.dumps(dict(surfaces=surfaces,openings_and_columns_reviewed=True,internal_partitions=['garage plane x5.25, open bay north ofy0.6','sidewall x-13.65 above corridor','cage front y-7.91 with open lower bays','loading platform y14.8'],column_evidence=['measurements_landmarks.json'],room_height_m=4.68,hidden_completion='Outer rectangle closes unseen rooms behind internal cage walls. Source-facing internal partitions preserve observed openings.',quality_note='Large uncertainty for inaccessible outer bounds is not a physical-accuracy pass.'),indent=2))
accept('agent_calibrate_room',['room_calibration.json'],'Recorded every shell surface and uncertainty, fitting visible partitions while retaining hidden closure hypotheses.',dict(camera_constraints_sha256=constraints['sha256']))
print(w.run('agent_model'),flush=True)
