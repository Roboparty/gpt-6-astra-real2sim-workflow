"""Full shared export/re-import of fixed RoomKit fixtures; keep every failed format."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','output','blender'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();protocol=json.loads(a.protocol.read_text());repo=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(repo/'workflow'));from r2s.core import run_command
    a.output.mkdir(parents=True,exist_ok=False)
    for file,expected in protocol['evaluator_sha256'].items():
        if sha(repo/file)!=expected:raise ValueError('Frozen evaluator bytes differ: '+file)
    env=dict(os.environ,R2S_CPU='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    report={'schema':'real2sim.roomkit-interchange/1','protocol_sha256':sha(a.protocol),
            'script_sha256':sha(__file__),'expected_cases':protocol['expected_cases'],
            'expected_format_checks':protocol['expected_format_checks'],'cases':[],
            'scope':protocol['scope'],'gpu_hours':0,'paid_api_requests':0}
    for case in protocol['cases']:
        directory=a.output/case['id'];directory.mkdir();start=time.monotonic()
        row={'id':case['id'],'status':'failed','formats':[]};report['cases'].append(row)
        try:
            assert sha(case['model'])==case['model_sha256'] and sha(case['scene'])==case['scene_sha256']
            shutil.copyfile(case['scene'],directory/'scene.json')
            commands=[('export',[str(a.blender),'-b',case['model'],'-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/blender_export.py'),'--',str(directory/'scene.json'),str(directory)]),
                      ('reload',[str(a.blender),'-b','-t','2','--python-exit-code','12','-P',str(repo/'tools/reload_scene_exports.py'),'--',str(directory)])]
            for name,argv in commands:
                remaining=protocol['resource_budget']['cpu_wall_seconds_per_case']-(time.monotonic()-start)
                if remaining<=0:raise TimeoutError('Per-case export/reload budget exhausted')
                (directory/(name+'_command.json')).write_text(json.dumps({'argv':argv,'timeout_seconds':remaining},indent=2))
                result=run_command(argv,directory,env,remaining)
                (directory/(name+'.log')).write_text(result.stdout+'\n'+result.stderr)
                row[name+'_returncode']=result.returncode
                if result.returncode:raise RuntimeError(name+' failed; artifacts and logs retained')
            reload=json.loads((directory/'reload_validation.json').read_text())
            row['formats']=reload['records'];assert [r['format'] for r in row['formats']]==protocol['formats']
            assert all(r['status']=='passed' for r in row['formats'])
            row['status']='passed'
        except Exception as exc:
            row['error']=repr(exc)
            if (directory/'reload_validation.json').exists():row['formats']=json.loads((directory/'reload_validation.json').read_text())['records']
        row['sources_unchanged']=sha(case['model'])==case['model_sha256'] and sha(case['scene'])==case['scene_sha256']
        row['artifact_hashes']={p.name:sha(p) for p in directory.iterdir() if p.is_file() and p.suffix in {'.blend','.glb','.usdc','.json'}}
        row['wall_seconds']=time.monotonic()-start
        (a.output/'summary.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({'case':case['id'],'status':row['status'],'error':row.get('error'),'wall_seconds':row['wall_seconds']}),flush=True)
    report['passed_cases']=sum(c['status']=='passed' for c in report['cases'])
    report['passed_format_checks']=sum(r['status']=='passed' for c in report['cases'] for r in c['formats'])
    (a.output/'summary.json').write_text(json.dumps(report,indent=2))
    return 0 if report['passed_cases']==report['expected_cases'] else 1


if __name__=='__main__':sys.exit(main())
