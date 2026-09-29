"""Native Workflow smoke: input -> reference -> RoomKit -> render -> ROI -> review.

Synthetic agent responses only; never a real reconstruction or visual acceptance.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow, atomic_json
from r2s.contracts import digest, ContractError
from r2s.media import file_hash
from r2s.generation_skills import load

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--skills',type=Path,required=True);p.add_argument('--blender',required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);os.environ['R2S_CPU']='1';os.environ['CUDA_VISIBLE_DEVICES']=''
started=time.monotonic();results=[]

def record(name, condition):
    if not condition:raise AssertionError(name)
    results.append({'case':name,'passed':True})

def rejects(name,fn):
    try:fn()
    except (ValueError,KeyError,ContractError) as e:
        results.append({'case':name,'passed':True,'retained_error':str(e)});return
    raise AssertionError(name+' accepted invalid input')

source=a.output/'source.png';Image.fromarray(np.full((64,64,3),128,dtype=np.uint8)).save(source)
camera={'position':[0,-1.5,.6],'rotation_world_to_cv':[[1,0,0],[0,0,-1],[0,1,0]],'focal_px':45,'principal_point':[32,32],'image_size':[64,64]}
protocol={'schema':'real2sim-generation-roi/1','views':[{'id':'source','role':'fit','source':{'path':str(source),'sha256':file_hash(source)},'camera_index':0,'camera_sha256':digest(camera),'regions':[{'id':'cabinet_region','xyxy':[16,24,48,63],'part_ids':['cabinet_body']}]}]}
protocol_path=a.output/'local_protocol.json';atomic_json(protocol_path,protocol)
cfg={'id':'skill-integration-synthetic','mode':'single','formal_test':False,'workflow_profile':'quality_v2','inputs':[{'path':str(source)}],
     'provenance':{'kind':'synthetic_contract','status':'declared','evidence':['synthetic fixture; no real accuracy claim']},
     'generation_skills':{'skills_root':str(a.skills),'blender':a.blender,'local_protocol':str(protocol_path),
       'reference':{'mode':'blocked','required':False,'reason':'Pi3X preparation budget exhausted; no install or inference authorized'}},
     'stages':{'build_geometry':{'command':[sys.executable,'-m','r2s.stage_worker','{packet}'],'timeout_seconds':120,'parameters':{'blender':a.blender,'threads':2,'cuda_visible_devices':'','inspection_resolution':[128,128]}}}}
case=a.output/'case';case.mkdir();atomic_json(case/'case.json',cfg);w=Workflow(case)
record('native_run_reaches_observe',w.run()['stage']=='agent_observe')
record('blocked_reference_recorded_and_optional',w.state['stages']['scene_reference']['status']=='succeeded')
status=json.loads(Path(w.state['stages']['scene_reference']['outputs'][0]['path']).read_text())
record('blocked_reference_never_inference_success',status['inference']=='not_run' and status['environment']=='not_ready')
obs={'source_sha256':file_hash(source),'acceptance_before_fit':{'landmark_max_px':18},'targets':[{'entity':'cabinet','parts':['cabinet_body'],'constraints':['floor support'],'observations':[{'id':'front','visibility':'observed'}],'uncertain':['synthetic assumed dimensions']}]}

def accept(stage, artifacts, parameters=None):
    record('pending_'+stage,w.state['stages'][stage]['status']=='awaiting_agent')
    directory=Path(w.state['stages'][stage]['directory'])
    for name,data in artifacts.items():atomic_json(directory/name,data)
    response={'status':'complete','artifacts':list(artifacts),'evidence':['Explicit synthetic test response, not a real reconstruction decision'],
              'reasoning_summary':'Exercise native stage contracts with known fixture inputs.', 'parameters':parameters or {}}
    atomic_json(directory/'response-authored.json',response)
    record('accept_'+stage,w.accept(stage,directory/'response-authored.json'))

accept('agent_observe',{'furniture_observation.json':obs})
w.run();accept('agent_identify',{'identity.json':{'fixture':True,'status':'unknown'}})
w.run();accept('agent_calibrate',{'calibration.json':camera})
w.run();accept('agent_calibrate_room',{'room_calibration.json':{'surfaces':[{'id':n,'plane':[0,0,1,0],'evidence':['synthetic'],'visibility':'unobserved','status':'hypothesized','uncertainty':'not measured'} for n in ('floor','ceiling','wall_front','wall_back','wall_left','wall_right')],'openings_and_columns_reviewed':True}})
w.run()
scene={'schema_version':'real2sim.scene/1.0','units':'m','up_axis':'Z','branch':'A','model_version':1,
       'room':{'x_min':-2,'x_max':2,'y_min':-2,'y_max':2,'height':2.5,'thickness':.1,'preserve_full_shell':True},'camera':camera,
       'objects':[{'id':'cabinet','kind':'cabinet','position':[0,0,.25],'dimensions':[.5,.5,.5],'evidence':['synthetic'],'confidence':.1},
                  {'id':'lamp','kind':'lamp','position':[0,0,2.3],'dimensions':[.3,.3,.1],'evidence':['assumed fixture luminaire'],'confidence':.1}],
       'structure':{'schema':'real2sim.assembly/1','observation_sha256':digest({}), 'acceptance':{'landmark_median_px':9,'landmark_max_px':18},
        'assemblies':[{'entity':'cabinet','frame':{'yaw_rad':0},'parts':[{'id':'cabinet_body','object':'cabinet_body'}],'joints':[],
          'source_observation_ids':['front'],'floor_supports':[{'part':'cabinet_body','plane_z':0,'tolerance_m':.005}],
          'fit':{'landmarks':[{'id':'front','part':'cabinet_body','world':[0,-.25,.25],'uv':[32,44.6]}]}}]}}
parts={'schema':'roomkit/1','units':'m','parts':[
    {'id':'cabinet_body','assembly':'cabinet','kind':'box','size':[.5,.5,.5],'position':[0,0,.25],'rotation':[0,0,0],'prior_status':'assumed','prior_source':'synthetic fixture','collision':'box'},
    {'id':'lamp_mesh','assembly':'lamp','kind':'box','size':[.3,.3,.1],'position':[0,0,2.3],'rotation':[0,0,0],'prior_status':'assumed','prior_source':'synthetic fixture','collision':'box'}]}
directory=Path(w.state['stages']['agent_model']['directory']);atomic_json(directory/'furniture_observation.json',obs)
scene['structure']['observation_sha256']=file_hash(directory/'furniture_observation.json')
accept('agent_model',{'scene.json':scene,'furniture_observation.json':obs,'roomkit_parts.json':parts},{'model_version':1})
model_receipt=json.loads((directory/'roomkit_generation.json').read_text())
record('native_model_accept_actually_executes_roomkit',model_receipt['parts']==2 and len(model_receipt['shell_surfaces'])==6)
record('native_generated_model_is_declared',any(Path(x['path']).name=='model.blend' for x in w.state['stages']['agent_model']['outputs']))
record('native_build_and_local_feedback_run',w.run(until='local_geometry_feedback')['status']=='completed_until')
build=Path(w.state['stages']['build_geometry']['directory'])
audit=json.loads((build/'structural_audit.json').read_text())
record('existing_structural_audit_executed',audit['evaluated_visible_meshes'] and len(audit['assemblies'])==1)
feedback=Path(w.state['stages']['local_geometry_feedback']['directory'])
report=json.loads((feedback/'local_feedback.json').read_text())
record('native_rendered_pixels_consumed_by_refine',report['regions'][0]['part_ids']==['cabinet_body'] and report['candidate_model_sha256']==file_hash(build/'scene.blend'))
record('roi_never_auto_accepts',report['acceptance']=='not_determined')
record('next_native_stage_is_actual_review',w.run()['stage']=='agent_review_geometry')
review_packet=json.loads((Path(w.state['stages']['agent_review_geometry']['directory'])/'packet.json').read_text())
record('review_receives_local_feedback_and_skill_instructions','local_geometry_feedback' in review_packet['input_artifacts'] and 'refine' in review_packet['skill_instructions'])
record('complete_candidate_not_frozen',not (case/'runs/freeze.json').exists())
rejects('native_freeze_rejects_incomplete_visual_and_physics',w.freeze)
affected=w.revise('agent_model','synthetic geometry correction must invalidate downstream evidence')
record('geometry_revision_invalidates_roi_reviews_export',{'build_geometry','local_geometry_feedback','agent_review_geometry','agent_materials','agent_calibrate_lighting','local_appearance_feedback','agent_review','export','validate','report'}<=set(affected))

# Separate native cases exercise required blocker and actual synthetic consumption.
required=copy.deepcopy(cfg);required['generation_skills']['reference']['required']=True
required_case=a.output/'required_reference';required_case.mkdir();atomic_json(required_case/'case.json',required)
wr=Workflow(required_case);stop=wr.run()
record('required_reference_halts_native_flow',stop['status']=='needs_input' and stop['stage']=='scene_reference')
record('required_blocker_does_not_reach_modelling','agent_model' not in wr.state['stages'])

helper=load(cfg['generation_skills'],'reference','reference.py')
frozen=helper.freeze({'preprocessing':{'resize':'none','output_size_wh':[64,64]},'frames':[{'id':'source','role':'fit','pts_seconds':0,'path':str(source)}]},a.output)
manifest=a.output/'reference_input.json';atomic_json(manifest,frozen)
points=np.zeros((1,1,64,64,3),dtype=np.float32);points[...,2]=1
npz=a.output/'reference_synthetic.npz';np.savez(npz,points=points,local_points=points,conf=np.zeros((1,1,64,64,1),dtype=np.float32),camera_poses=np.eye(4,dtype=np.float32)[None,None])
prov={k:frozen[k] for k in ('code_revision','weight_revision','weight_sha256','preprocessing')};prov.update(input_sha256=file_hash(manifest),npz_sha256=file_hash(npz),frame_ids=['source'],kind='synthetic_contract')
prov_path=a.output/'reference_provenance.json';atomic_json(prov_path,prov)
consumed=copy.deepcopy(cfg);consumed['generation_skills']['reference']={'mode':'consume','manifest':str(manifest),'npz':str(npz),'provenance':str(prov_path)}
consume_case=a.output/'consumed_reference';consume_case.mkdir();atomic_json(consume_case/'case.json',consumed)
wc=Workflow(consume_case);record('native_reference_consumer_executes',wc.run()['stage']=='agent_observe')
ref_status=json.loads(Path(wc.state['stages']['scene_reference']['outputs'][0]['path']).read_text())
record('native_reference_keeps_synthetic_inference_not_run',ref_status['origin']=='synthetic_contract' and ref_status['inference']=='not_run')
fp=wc.fingerprint('scene_reference');npz.write_bytes(b'changed')
record('reference_bytes_drift_invalidates_cache',wc.fingerprint('scene_reference')!=fp and not wc.valid('scene_reference'))

atomic_json(a.output/'integration_results.json',{'status':'passed','tests':results,'total':len(results),'wall_seconds':time.monotonic()-started,
    'structural_status':audit['status'],'source_roi_mae':report['regions'][0]['candidate_srgb_mae'],
    'scope':'Synthetic native generation-to-review integration, no real visual acceptance, no Pi3X inference',
    'gpu_used':False,'paid_api_requests':0})
print(json.dumps({'status':'passed','tests':len(results),'wall_seconds':time.monotonic()-started,'structural_status':audit['status']}))
