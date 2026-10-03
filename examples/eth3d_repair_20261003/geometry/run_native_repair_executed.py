import pathlib,json,sys,shutil,hashlib,cv2
cv2.setNumThreads(2)
R=pathlib.Path('/home/wqz/real2sim_agent_repair_20261003/geometry');B=pathlib.Path('/home/wqz/real2sim_agent_compare_20261003/OURS');C=R/'native_case';C.mkdir(exist_ok=True);V=R/'candidate_v3'
sys.path.insert(0,str(R/'code/workflow'));from r2s.core import Workflow;from r2s.camera import workflow_constraints
cfg=json.loads((B/'native_case/case.json').read_text());cfg['id']='eth3d_ours_geometry_repair_20261003';cfg['repair_of_model_sha256']='4d53b2a7fa076a6892592e555f33b55b07476dc2f6dab58651ab146fc1acdf85'
for stage in ['build_geometry','build_render','export','validate','report']:
 cfg['stages'][stage]['parameters']['threads']=8;cfg['stages'][stage]['timeout_seconds']=3000
cfg['stages']['build_geometry']['parameters']['inspection_resolution']=[384,384]
(C/'case.json').write_text(json.dumps(cfg,indent=2));w=Workflow(C)
def enter(stage):
 print(w.run(stage),flush=True);return pathlib.Path(w.state['stages'][stage]['directory'])
def accept(stage,files,why,params=None):
 D=pathlib.Path(w.state['stages'][stage]['directory']);r=dict(status='complete',artifacts=files,evidence=['Allowed36 original RGB/fixedK,T/DA3; source repair receipts; no GT geometry or heldout inputs'],reasoning_summary=why,parameters=params or {},issues=[]);(D/'response.json').write_text(json.dumps(r,indent=2));print(stage,w.accept(stage,D/'response.json'),flush=True)
D=enter('agent_observe');old=B/'native_case/runs/agent_observe/0001'
for f in ['observation.json','furniture_observation.json']:shutil.copyfile(old/f,D/f)
for f in ['topology_plan.json','repair_measurements.json','bin_multiview_tracks.json','bin_foot_seeded_tracks.json']:shutil.copyfile(R/f,D/f)
accept('agent_observe',['observation.json','furniture_observation.json','topology_plan.json','repair_measurements.json','bin_multiview_tracks.json','bin_foot_seeded_tracks.json'],'Repair reuses authorized source observations with unchanged labels/thresholds. Added source-bound regional topology and successful/failed multiview tracking; no failed tracking called evidence.')
D=enter('agent_identify');shutil.copyfile(B/'native_case/runs/agent_identify/0001/identity.json',D/'identity.json');accept('agent_identify',['identity.json'],'Existing generic semantic categories retained; no manufacturer model or external assets inferred.')
D=enter('agent_calibrate');constraints=workflow_constraints(w);(D/'calibration.json').write_text(json.dumps(dict(cameras=constraints['cameras'],camera_constraints_sha256=constraints['sha256'],model_from_input=constraints['model_from_input'],locked=True,scope='Same supplied reference camera diagnostic gauge, no source camera changes'),indent=2));accept('agent_calibrate',['calibration.json'],'All36 camera constraints unchanged under the same one rigid gauge.',dict(camera_constraints_sha256=constraints['sha256']))
D=enter('agent_calibrate_room');S=json.loads((V/'scene.json').read_text());surfaces=[]
for name in ['wall_front','wall_back','wall_left','wall_right','floor','ceiling']:
 surfaces.append(dict(id=name,visibility='partial',status='fitted',plane={'segments':[b for b in S['room']['boundary_segments'] if b['shell']==name]} if name.startswith('wall') else {'z':0 if name=='floor' else 4.68,'footprint_regions':S['room']['topology_regions']},evidence=['topology_plan.json','repair_measurements.json'],image_constraints=['RGB-selected planes and room/corridor boundaries; source20terminal;8/9object tracks'],residuals={'source_measurements':'quantiles and tracking residuals retained in repair_measurements.json/bin_multiview_tracks.json'},uncertainty='Only visible portions fitted; cage rear depth and hidden joins are explicit assumptions, not certified reconstruction'))
(D/'room_calibration.json').write_text(json.dumps(dict(surfaces=surfaces,openings_and_columns_reviewed=True,nonrectangular_topology=True,unknown_completions=S['room']['unknown_completions'],collision='mesh_only; canonical rectangle fallback refused'),indent=2));shutil.copyfile(R/'topology_plan.json',D/'topology_plan.json');shutil.copyfile(R/'repair_measurements.json',D/'repair_measurements.json');accept('agent_calibrate_room',['room_calibration.json','topology_plan.json','repair_measurements.json'],'Replaced the rectangular envelope by actual source-supported union geometry. Bounds remain metadata only; legacy physical collision route refuses fallback.',dict(camera_constraints_sha256=constraints['sha256']))
D=enter('agent_model');files=['model.blend','scene.json','geometry_changes.json','source_rebuild_evidence.json','collision_mesh_coverage.json','topology.json']
for f in files:shutil.copyfile(V/f,D/f)
shutil.copyfile(old/'furniture_observation.json',D/'furniture_observation.json');files.append('furniture_observation.json');shutil.copyfile(R/'repair_geometry.py',D/'repair_geometry.py');files.append('repair_geometry.py')
accept('agent_model',files,'Constructed the actual editable union shell and measured component repairs; direct NO_RENDER audit passed but is not native/visual acceptance. This run now executes the full native build and retains all source and structure views.',dict(camera_constraints_sha256=constraints['sha256'],model_version=S['model_version']))
print(w.run('agent_review_geometry'),flush=True)
