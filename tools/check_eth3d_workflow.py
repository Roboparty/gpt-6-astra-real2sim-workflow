"""Exercise the native workflow with all frozen real photographs and supplied cameras."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.camera import workflow_constraints,check_scene_cameras
from r2s.core import Workflow
from r2s.media import file_hash


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--case',type=Path,required=True);a=p.parse_args()
    a.case.mkdir(parents=True,exist_ok=False);cfg=json.loads((a.input/'case.json').read_text())
    for i,record in enumerate(cfg['inputs']):record['path']=str(a.input/'rgb'/f'{i:03d}.png')
    cfg['camera_observations']['path']=str(a.input/'cameras.json')
    cfg['camera_observations']['sha256']=file_hash(a.input/'cameras.json')
    (a.case/'case.json').write_text(json.dumps(cfg,indent=2));started=time.monotonic();workflow=Workflow(a.case)
    status=workflow.run(until='preprocess');assert status['status']=='completed_until'
    constraints=workflow_constraints(workflow);assert len(constraints['cameras'])==36
    assert workflow.execute('agent_observe')=='awaiting_agent'
    packet=Path(workflow.state['stages']['agent_observe']['directory'])/'packet.json'
    assert json.loads(packet.read_text())['camera_constraints']==constraints
    check_scene_cameras(dict(camera=constraints['cameras'][0],cameras=constraints['cameras']),constraints)
    result=dict(status='passed',real_images=36,accepted_cameras=36,preprocess_cache_valid=workflow.valid('preprocess'),
                camera_constraints_sha256=constraints['sha256'],agent_packet=str(packet),wall_seconds=time.monotonic()-started,
                scope='Native ingest/preprocess/Agent packet and camera lock; not full modelling, review, export or task acceptance')
    (a.case/'camera_integration_receipt.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
