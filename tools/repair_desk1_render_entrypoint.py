"""Append only entrypoint-repair attempts; retain fits, failures and budget history."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--blender',required=True);a=p.parse_args()
    code=Path(__file__).resolve().parents[1];sys.path.insert(0,str(code/'workflow'));from r2s.core import run_command,atomic_json
    path=a.root/'native_phase_receipt.json';receipt=json.loads(path.read_text())
    if any(x['id'].endswith('_entrypoint_repair') for x in receipt['attempts']):raise ValueError('Repair already attempted; preserve counts')
    for arm in ['B_image_cuboids','C_web_soft_cuboids','D_web_fixed_cuboids']:
        label=arm+'_entrypoint_repair';out=a.root/arm/'rendered_entrypoint_repair';t=time.monotonic()
        argv=[a.blender,'-b','-t','2','--python-exit-code','12','-P',str(code/'tools/build_desk1_cuboids.py'),'--',
            '--annotation',str(code/'docs/research/DESK1_SCENE_REVISION2_20260930.json'),'--fit',str(a.root/arm/'fitting/fit.json'),'--output',str(out)]
        row={'id':label,'argv':argv,'status':'running','repair_reason':'Blender script directory absent from sys.path; no fit/model/renderer parameter changed','timeout_seconds':600}
        receipt['attempts'].append(row);atomic_json(path,receipt)
        try:
            proc=run_command(argv,a.root,{**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'},600)
            (a.root/(label+'.stdout.log')).write_text(proc.stdout);(a.root/(label+'.stderr.log')).write_text(proc.stderr)
            row.update(status='succeeded' if proc.returncode==0 else 'failed',exit_code=proc.returncode)
        except Exception as exc:row.update(status='failed',error=str(exc))
        row['wall_seconds']=time.monotonic()-t;atomic_json(path,receipt)
    receipt['status']='completed_with_retained_entrypoint_failures' if all(x['status']=='succeeded' for x in receipt['attempts'][-3:]) else 'partial_or_failed'
    receipt['wall_seconds']=sum(x['wall_seconds'] for x in receipt['attempts']);atomic_json(path,receipt);print(json.dumps({'status':receipt['status'],'attempts':len(receipt['attempts'])}))

if __name__=='__main__':main()
