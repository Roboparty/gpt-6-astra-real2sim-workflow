"""Regression contracts against a retained native smoke case; no new Blender/model run."""
import argparse
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow,atomic_json
from r2s.contracts import ContractError
from r2s.profiles import stages_for, LEGACY
from r2s.generation_skills import execute,prepare_model,bindings,config

p=argparse.ArgumentParser();p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);rows=[]

def check(name,fn,reject=False):
    try:fn()
    except (ValueError,KeyError) as e:
        assert reject,(name,str(e));rows.append({'case':name,'passed':True,'retained_error':str(e)});return
    assert not reject,name+' failed to reject'
    rows.append({'case':name,'passed':True})

def require(v):assert v

workflow=Workflow(a.smoke/'case');cfg=copy.deepcopy(workflow.config)
check('legacy_dag_unchanged_without_optin',lambda:require(stages_for({})==list(LEGACY)))
check('quality_dag_unchanged_without_optin',lambda:require(not any('feedback' in n or n=='scene_reference' for n,_,_ in stages_for({'workflow_profile':'quality_v2'}))))
bad=copy.deepcopy(cfg);bad['workflow_profile']='legacy_v1'
check('legacy_rejects_silent_optin',lambda:stages_for(bad),True)
bad=copy.deepcopy(cfg);bad['generation_skills']['reference']['mode']='install-and-run'
check('cannot_enable_unbudgeted_inference_mode',lambda:config(bad),True)
graph={n:deps for n,deps,_ in stages_for(cfg)}
check('calibration_receives_reference',lambda:require('scene_reference' in graph['agent_calibrate_room']))
check('both_review_phases_receive_feedback',lambda:require('local_geometry_feedback' in graph['agent_review_geometry'] and 'local_appearance_feedback' in graph['agent_review']))
check('frozen_roi_is_upstream_artifact',lambda:require('agent_calibrate_room' in graph['local_geometry_feedback']))

packet=json.loads((a.smoke/'case/runs/local_geometry_feedback/0001/packet.json').read_text())
frozen=json.loads(Path(cfg['generation_skills']['local_protocol']).read_text())
def run_case(label,protocol,mod=None):
    out=a.output/label;out.mkdir();path=out/'local_protocol.json';atomic_json(path,protocol)
    value=copy.deepcopy(packet);value['generation_skills']['local_protocol']=str(path)
    if mod:mod(value)
    return execute(value,out)

check('native_feedback_positive',lambda:run_case('valid',frozen))
for label,edit in [
    ('heldout',lambda d:d['views'][0].update(role='heldout')),
    ('unaccepted_source',lambda d:d['views'][0]['source'].update(sha256='0'*64)),
    ('camera_drift',lambda d:d['views'][0].update(camera_sha256='0'*64)),
    ('negative_camera_index',lambda d:d['views'][0].update(camera_index=-1)),
    ('unknown_part',lambda d:d['views'][0]['regions'][0].update(part_ids=['invented'])),
]:
    bad=copy.deepcopy(frozen);edit(bad)
    check('feedback_reject_'+label,lambda l=label,d=bad:run_case(l,d),True)
check('appearance_stage_executes_same_bound_adapter',lambda:run_case('appearance',frozen,lambda d:d.update(stage='local_appearance_feedback')))

# No external protocol: consume exactly the calibration stage artifact.
out=a.output/'accepted_protocol';out.mkdir();path=out/'local_protocol.json';atomic_json(path,frozen)
value=copy.deepcopy(packet);value['generation_skills'].pop('local_protocol')
value['input_artifacts']['agent_calibrate_room']=[{'path':str(path),'sha256':'declared_by_core'}]
check('accepted_calibration_roi_consumed',lambda:execute(value,out))
value=copy.deepcopy(packet);value['generation_skills'].pop('local_protocol');value['input_artifacts']['agent_calibrate_room']=[]
out=a.output/'missing_protocol';out.mkdir()
check('missing_protocol_halts_without_fake_report',lambda:require(execute(value,out)['status']=='needs_input'))

before=bindings(cfg,'ingest');changed=copy.deepcopy(cfg);changed['generation_skills']['local_protocol']=str(a.output/'future_roi.json')
check('roi_config_change_does_not_restart_ingest',lambda:require(bindings(changed,'ingest')==before))
check('roi_config_change_invalidates_feedback',lambda:require(bindings(changed,'local_geometry_feedback')!=bindings(cfg,'local_geometry_feedback')))

value=json.loads((a.smoke/'consumed_reference/runs/scene_reference/0001/packet.json').read_text())
value['formal_test']=True;out=a.output/'formal_synthetic';out.mkdir()
check('formal_case_rejects_synthetic_reference',lambda:require(execute(value,out)['status']=='needs_input'))
check('formal_rejection_keeps_inference_unverified',lambda:require(json.loads((out/'reference_status.json').read_text())['inference']=='not_verified'))

# The model acceptance path cannot evade a spent refinement budget.
workflow.refining=True;workflow.config['refinement']={'max_seconds':1};workflow.state['refinement']={'elapsed_seconds':1}
attempt=a.smoke/'case/runs/agent_model/0001'
response=json.loads((attempt/'response-authored.json').read_text())
check('roomkit_refuses_exhausted_refinement_budget',lambda:prepare_model(workflow,attempt,response),True)

atomic_json(a.output/'results.json',{'status':'passed','total':len(rows),'tests':rows,'scope':'Native integration contracts, no new model or Blender invocation'})
print(json.dumps({'status':'passed','tests':len(rows)}))
