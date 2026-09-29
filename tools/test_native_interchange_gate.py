"""Exercise native export/validate gates using cached real interchange fixtures.

The expensive export command is replayed by copying its unchanged real artifacts.
Strict Blender reload and native MuJoCo validation execute normally. No Agent or
reconstruction success is implied by synthetic stage packets.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

p=argparse.ArgumentParser(description=__doc__)
for key in ('fixture','source-model','source-scene','blender','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'workflow'))
a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic();rows=[]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
before={str(p):sha(p) for p in [a.source_model,a.source_scene]+list(a.fixture.glob('scene.*'))}
real_run=subprocess.run
os.environ.update(R2S_CPU='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')


def run_stage(label,stage,source,corrupt_export=False,should_fail=False):
    out=a.output/label;out.mkdir();packet={'case_id':'interchange_gate_fixture','stage':stage,'output_directory':str(out),
        'parameters':{'blender':str(a.blender),'threads':2,'cuda_visible_devices':''},
        'generation_skills':{'fixture':True},'workflow_profile':'quality_v2','physics_options':{},
        'input_artifacts':{'agent_model':[{'path':str(a.source_model)},{'path':str(a.source_scene)}]} if stage=='export' else {'export':[{'path':str(source/'geometry_audit.json')}]}}
    pp=out/'packet.json';pp.write_text(json.dumps(packet))
    def replay_export(argv,*args,**kwargs):
        if any(str(v).endswith('/blender_export.py') for v in argv):
            for item in a.fixture.iterdir():
                if item.name in {'strict_reload_validation.json','reload_validation.json','scene.json'}:continue
                dest=out/item.name
                if item.is_dir():shutil.copytree(item,dest)
                else:shutil.copyfile(item,dest)
            if corrupt_export:(out/'scene.glb').write_bytes(b'not a GLB')
            return subprocess.CompletedProcess(argv,0,'Replayed prior real export fixture; no new exporter execution.','')
        return real_run(argv,*args,**kwargs)
    error=None;t=time.monotonic()
    try:
        with patch.object(sys,'argv',['r2s.stage_worker',str(pp)]),patch('subprocess.run',side_effect=replay_export):
            runpy.run_module('r2s.stage_worker',run_name='__main__')
    except Exception as exc:error=repr(exc)
    assert bool(error)==should_fail,(label,error)
    assert (out/'response.json').exists()!=should_fail
    if not should_fail:
        assert json.loads((out/'response.json').read_text())['status']=='complete'
        if stage=='export':
            assert json.loads((out/'strict_reload_validation.json').read_text())['status']=='passed'
            assert (out/'export_blender.log').exists() and (out/'interchange_blender.log').exists()
        else:assert json.loads((out/'validation.json').read_text())['interchange']['status']=='passed'
    rows.append({'case':label,'passed':True,'expected_rejection':should_fail,'retained_error':error,'wall_seconds':time.monotonic()-t})
    return out


valid=run_stage('valid_export','export',a.fixture)
run_stage('valid_validate','validate',valid)
run_stage('bad_export','export',a.fixture,corrupt_export=True,should_fail=True)
for mutation in ('missing_receipt','changed_bytes','empty_records'):
    altered=a.output/(mutation+'_input');shutil.copytree(valid,altered)
    if mutation=='missing_receipt':(altered/'strict_reload_validation.json').unlink()
    elif mutation=='changed_bytes':
        with (altered/'scene.glb').open('ab') as f:f.write(b'changed after validation')
    else:
        path=altered/'strict_reload_validation.json';data=json.loads(path.read_text());data['records']=[];path.write_text(json.dumps(data))
    run_stage(mutation,'validate',altered,should_fail=True)
assert before=={p:sha(Path(p)) for p in before}
report={'status':'passed','cases':rows,'sources_unchanged':True,'wall_seconds':time.monotonic()-start,
        'scope':'Synthetic native stage packets with reused actual export fixtures. Blender re-import and MuJoCo validation run; no new full exporter execution or complete Agent workflow acceptance.',
        'implementation_sha256':{str(p.relative_to(repo)):sha(p) for p in [repo/'workflow/r2s/stage_worker.py',repo/'workflow/r2s/interchange.py']}}
(a.output/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps({'status':'passed','cases':len(rows),'wall_seconds':report['wall_seconds']}))
