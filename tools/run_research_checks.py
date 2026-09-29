"""Run the fixed development regression set, retaining every failure and log."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

CHECKS = ['structure_contract', 'appearance_contract', 'appearance_worker',
          'refinement', 'surface_contract', 'viewpoint_aabb', 'enclosure_rays',
          'shell_collision', 'geometry_feedback', 'geometry_feedback_gate',
          'physical_priors', 'physical_prior_runtime', 'optional_dynamics', 'task_evaluation']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--blender',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    env=dict(os.environ,OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONPATH=str(repo/'workflow'),R2S_BLENDER=str(args.blender.resolve()),R2S_CPU='1',CUDA_VISIBLE_DEVICES='')
    results=[]
    for name in CHECKS:
        script=repo/'tools'/('test_'+name+'.py')
        command=[sys.executable,str(script)]
        if name=='viewpoint_aabb':command=[str(args.blender.resolve()),'-b','-t','2','--python-exit-code','12','-P',str(script)]
        if name in {'geometry_feedback','optional_dynamics'}:command+=['--output-dir',str(out/name)]
        start=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            try:
                result=subprocess.run(command,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
                status='passed' if result.returncode==0 else 'failed'
                returncode=result.returncode
            except subprocess.TimeoutExpired:
                status,returncode='timeout',None
        row=dict(check=name,status=status,returncode=returncode,wall_seconds=time.monotonic()-start,
                 script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),command=command)
        results.append(row)
        print(json.dumps(row),flush=True)
    report=dict(schema='real2sim.research-checks/1',scope='development regressions, not a reconstruction benchmark',
                denominator=len(CHECKS),passed=sum(r['status']=='passed' for r in results),checks=results,
                implementation={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted((repo/'workflow'/'r2s').rglob('*.py'))})
    (out/'summary.json').write_text(json.dumps(report,indent=2))
    return 0 if report['passed']==report['denominator'] else 1


if __name__=='__main__':sys.exit(main())
