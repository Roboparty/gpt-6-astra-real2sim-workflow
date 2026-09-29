"""Actual retained-room file export, strict reload and fixed-rig render diagnostics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','output','blender'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.protocol.read_text());repo=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(repo/'workflow'));from r2s.core import run_command
    assert sha(cfg['source_model'])==cfg['source_model_sha256'] and sha(cfg['source_scene'])==cfg['source_scene_sha256']
    a.output.mkdir(parents=True,exist_ok=False);export=a.output/'export';export.mkdir()
    shutil.copyfile(cfg['source_scene'],export/'scene.json')
    env=dict(os.environ,R2S_CPU='1',CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    report={'schema':'real2sim.room-portability-run/1','protocol_sha256':sha(a.protocol),
            'script_sha256':sha(__file__),'stages':[],'scope':cfg['scope'],'gpu_hours':0,'paid_api_requests':0}
    commands=[('export',[str(a.blender),'-b',cfg['source_model'],'-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/blender_export.py'),'--',str(export/'scene.json'),str(export),'--interchange-only']),
              ('strict',[str(a.blender),'-b','-t','2','--python-exit-code','12','-P',str(repo/'workflow/r2s/interchange.py'),'--',str(export),'--source-model',cfg['source_model'],'--source-scene',cfg['source_scene']]),
              ('appearance',[str(a.blender),'-b','-t','2','--python-exit-code','12','-P',str(repo/'tools/render_interchange_appearance.py'),'--','--protocol',str(a.protocol),'--export-dir',str(export),'--output',str(a.output/'appearance')])]
    start=time.monotonic()
    for name,argv in commands:
        t=time.monotonic();row={'stage':name,'status':'failed'};report['stages'].append(row)
        try:
            remaining=cfg['budget']['cpu_wall_seconds_per_run']-(time.monotonic()-start)
            if remaining<=0:raise TimeoutError('Shared portability run budget exhausted')
            result=run_command(argv,a.output,env,remaining)
            (a.output/(name+'.log')).write_text(result.stdout+'\n'+result.stderr)
            row.update(returncode=result.returncode,status='passed' if result.returncode==0 else 'failed')
        except Exception as exc:row['error']=repr(exc)
        row['wall_seconds']=time.monotonic()-t
        (a.output/'receipt.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(row),flush=True)
        # Appearance is allowed after strict failure only as a retained diagnostic;
        # missing/corrupt format files are recorded by the renderer, never dropped.
        if name=='export' and row['status']!='passed':break
    report['wall_seconds']=time.monotonic()-start
    report['sources_unchanged']=sha(cfg['source_model'])==cfg['source_model_sha256'] and sha(cfg['source_scene'])==cfg['source_scene_sha256']
    report['implementation_sha256']={str(f.relative_to(repo)):sha(f) for f in [repo/'workflow/r2s/blender_export.py',repo/'workflow/r2s/interchange.py',repo/'tools/render_interchange_appearance.py']}
    (a.output/'receipt.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
