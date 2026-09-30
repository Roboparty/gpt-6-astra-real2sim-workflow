"""One bounded sequential CPU phase; retain every attempt and immutable baseline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--python',required=True);p.add_argument('--blender',required=True)
    a=p.parse_args();code=Path(__file__).resolve().parents[1];phase=code/'docs/research/DESK1_WEB_PHASE_20260930.json';annotation=code/'docs/research/DESK1_SCENE_REVISION2_20260930.json'
    cfg=json.loads(phase.read_text());started=time.monotonic();env={**os.environ,'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
    receipt={'schema':'real2sim.desk1-native-phase-receipt/1','phase_sha256':sha(phase),'source_sha256':cfg['source_sha256'],
        'baseline_sha256_before':sha(cfg['old_baseline_remote']),'paid_api_requests':0,'gpu_process_seconds':0,'attempts':[],'status':'running'}
    receipt_path=a.root/'native_phase_receipt.json'
    if receipt_path.exists():raise ValueError('Phase already has a receipt; never reset attempts')
    def run(label,argv,timeout):
        t=time.monotonic();row={'id':label,'argv':argv,'timeout_seconds':timeout,'status':'running'};receipt['attempts'].append(row);write(receipt_path,receipt)
        try:
            proc=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=timeout)
            (a.root/(label+'.stdout.log')).write_text(proc.stdout);(a.root/(label+'.stderr.log')).write_text(proc.stderr)
            row.update(status='succeeded' if proc.returncode==0 else 'failed',exit_code=proc.returncode)
        except subprocess.TimeoutExpired as exc:
            # Renderer gets its own owned process group via r2s.core.run_command below.
            row.update(status='timeout',error=str(exc));proc=None
        row['wall_seconds']=time.monotonic()-t;write(receipt_path,receipt);return proc is not None and proc.returncode==0
    gate=a.root/'native_case'
    okay=run('native_web_gate',[a.python,str(code/'tools/run_desk1_web_gate.py'),'--source',cfg['source_remote'],
        '--bundle-directory',str(code/'docs/research/desk1_web_sources_20260930'),'--output',str(gate)],120)
    if okay:
        web=gate/'runs/validate_web_research/0001/web_research_report.json'
        for arm in ['B_image_cuboids','C_web_soft_cuboids','D_web_fixed_cuboids']:
            fit=a.root/arm/'fitting'
            okay=run(arm+'_fit',[a.python,str(code/'tools/fit_desk1_cuboids.py'),'--annotation',str(annotation),
                '--phase',str(phase),'--web-report',str(web),'--arm',arm,'--output',str(fit)],180)
            if not okay:continue
            # Own a Blender process group so a timeout also kills only its children.
            t=time.monotonic();label=arm+'_render';out=a.root/arm/'rendered';argv=[a.blender,'-b','-t','2','--python-exit-code','12','-P',str(code/'tools/build_desk1_cuboids.py'),'--',
                '--annotation',str(annotation),'--fit',str(fit/'fit.json'),'--output',str(out)]
            row={'id':label,'argv':argv,'timeout_seconds':600,'status':'running'};receipt['attempts'].append(row);write(receipt_path,receipt)
            try:
                import sys
                sys.path.insert(0,str(code/'workflow'))
                from r2s.core import run_command
                out.parent.mkdir(parents=True,exist_ok=True)
                proc=run_command(argv,a.root,env,600)
                (a.root/(label+'.stdout.log')).write_text(proc.stdout);(a.root/(label+'.stderr.log')).write_text(proc.stderr)
                row.update(status='succeeded' if proc.returncode==0 else 'failed',exit_code=proc.returncode)
            except Exception as exc:row.update(status='failed',error=str(exc))
            row['wall_seconds']=time.monotonic()-t;write(receipt_path,receipt)
    receipt.update(status='completed' if all(x['status']=='succeeded' for x in receipt['attempts']) and len(receipt['attempts'])==7 else 'partial_or_failed',
        wall_seconds=time.monotonic()-started,baseline_sha256_after=sha(cfg['old_baseline_remote']),source_sha256_after=sha(cfg['source_remote']))
    write(receipt_path,receipt);print(json.dumps(receipt))

if __name__=='__main__':main()
