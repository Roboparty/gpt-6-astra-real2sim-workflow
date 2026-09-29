"""Public accept must not bypass worker gates; Agent and builder share time budget."""
import argparse
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.core import Workflow
from r2s.contracts import ContractError
from r2s.generation_skills import prepare_model

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--smoke',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);rows=[]
workflow=Workflow(a.smoke/'required_reference')
assert workflow.state['stages']['scene_reference']['status']=='needs_input'
before=copy.deepcopy(workflow.state)
response=a.output/'fake-complete.json'
response.write_text(json.dumps({'status':'complete','artifacts':['reference_status.json']}))
for stage in ('scene_reference','local_geometry_feedback','local_appearance_feedback'):
    try:workflow.accept(stage,response)
    except ContractError:rows.append({'case':'cannot_manually_accept_'+stage,'passed':True})
    else:raise AssertionError('Executable gate bypassed: '+stage)
assert workflow.state==before
assert not workflow.valid('scene_reference')
rows.append({'case':'required_reference_remains_blocked_and_state_unchanged','passed':True})

workflow=Workflow(a.smoke/'case');workflow.refining=True
workflow.config['refinement']={'max_seconds':100}
workflow.state['refinement']={'elapsed_seconds':40}
workflow._active_work_started=100
attempt=a.smoke/'case/runs/agent_model/0001'
authored=json.loads((attempt/'response-authored.json').read_text())
class CapturedLaunch(Exception):pass
def capture(argv,cwd,env,timeout):
    assert timeout==5,timeout
    raise CapturedLaunch()
with patch('r2s.core.time.monotonic',return_value=155),patch('r2s.core.run_command',side_effect=capture) as runner:
    try:prepare_model(workflow,attempt,authored)
    except CapturedLaunch:pass
    else:raise AssertionError('Builder launch missing')
    assert runner.call_count==1
rows.append({'case':'55_second_agent_leaves_only_5_seconds_of_60_for_builder','passed':True})
with patch('r2s.core.time.monotonic',return_value=161),patch('r2s.core.run_command') as runner:
    try:prepare_model(workflow,attempt,authored)
    except ContractError:pass
    else:raise AssertionError('Expired stage launched builder')
    runner.assert_not_called()
rows.append({'case':'expired_active_stage_cannot_launch_roomkit','passed':True})
(a.output/'results.json').write_text(json.dumps({'status':'passed','tests':rows,'total':len(rows),
    'scope':'Actual blocked workflow accept checks plus mocked monotonic clock and builder; no real model API or extra Blender run'},indent=2))
print(json.dumps({'status':'passed','total':len(rows)}))
