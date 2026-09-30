"""Continue the original setup clock after the CPU-only Triton import diagnostic.

No model/seed/settings change and no inference quota reset. Do not reinstall deps.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request
from run_desk1_moge3 import sha,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--python',required=True);p.add_argument('--gpu',type=int,required=True);p.add_argument('--ticket',type=Path);a=p.parse_args();root=a.root;phase=json.loads((root/'phase.json').read_text());cfg=phase['moge'];limits=phase['limits'];path=root/'receipt.json';record=json.loads(path.read_text())
    if record.get('model_calls') or (root/'inference_receipt.json').exists():raise ValueError('Cannot reset an inference attempt')
    tag='transport' if a.ticket else 'import'
    backup=root/('receipt_before_'+tag+'_repair.json')
    if backup.exists():raise ValueError('This setup repair already used')
    save(backup,record);save(root/('setup_'+tag+'_repair.json'),{'reason':'Official canonical HF transport connection reset; resolved public CDN ticket transferred as small metadata only.' if a.ticket else 'Triton autotuner requires a CUDA driver at import; prior CUDA_VISIBLE_DEVICES empty diagnostic is retained. Import deferred to the guarded actual GPU process.','old_gpu':6,'new_gpu':a.gpu,'gpu_change_reason':'Original GPU6 acquired external work; only newly idle selected card used.','settings_unchanged':True,'setup_clock_not_reset':True,'original_setup_epoch':(root/'phase.json').stat().st_mtime})
    deadline=(root/'phase.json').stat().st_mtime+limits['setup_wall_seconds'];record['errors_retained']=record.get('errors',[]);record['errors']=[]
    def remaining():
        value=deadline-time.time()
        if value<=0:raise TimeoutError('Original shared setup deadline expired')
        return value
    started=time.monotonic();row={'id':'model','source_url':'https://huggingface.co/'+cfg['repo']+'/resolve/'+cfg['revision']+'/'+cfg['file'],'status':'downloading','streamed_bytes':0};record['downloads'].append(row);save(path,record)
    try:
        url=row['source_url']
        if a.ticket:
            ticket=json.loads(a.ticket.read_text())
            if ticket['canonical_url']!=url or ticket['model_body_read_bytes']!=0:raise ValueError('Transport ticket must be metadata only for this exact pinned checkpoint')
            url=ticket['url']
        with urllib.request.urlopen(url,timeout=min(60,remaining())) as response,(root/'model.pt').open('wb') as f:
            while chunk:=response.read(4<<20):
                remaining();f.write(chunk);row['streamed_bytes']+=len(chunk);record['network_streamed_bytes']+=len(chunk)
                if record['network_streamed_bytes']+(1<<28)>limits['remote_download_bytes']:raise ValueError('Shared download cap exhausted')
        row.update(status='verified',sha256=sha(root/'model.pt'),bytes=(root/'model.pt').stat().st_size,wall_seconds=time.monotonic()-started)
        if row['sha256']!=cfg['sha256'] or row['bytes']!=cfg['bytes']:raise ValueError('Pinned weight checksum/size mismatch')
        record['setup_wall_seconds']=time.time()-((root/'phase.json').stat().st_mtime);record['network_conservative_bytes']=record['network_streamed_bytes']+(1<<28)
        selected=next(x for x in subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines() if x.split(',')[0].strip()==str(a.gpu));fields=[x.strip() for x in selected.split(',')]
        if int(fields[2])>16 or int(fields[3])!=0:raise ValueError('Selected GPU acquired external work; do not touch it')
        record['gpu_preflight']={'index':a.gpu,'uuid':fields[1],'used_mib':int(fields[2]),'utilization':int(fields[3])};record['status']='inference_running';save(path,record)
        env={**os.environ,'CUDA_VISIBLE_DEVICES':str(a.gpu),'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','PYTHONPATH':os.pathsep.join(map(str,[root/'deps',root/'MoGe',root/'utils3d-moge',root/'FlexGEMM'])),'TRITON_CACHE_DIR':str(root/'triton_cache'),'HF_HOME':str(root/'hf_cache'),'TORCH_HOME':str(root/'torch_cache'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        argv=[a.python,str(Path(__file__).with_name('run_desk1_moge3.py')),'--phase',str(root/'phase.json'),'--root',str(root),'--mode','inference'];t=time.monotonic()
        with (root/'moge_inference.log').open('w') as log:
            proc=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            try:code=proc.wait(timeout=limits['gpu_process_wall_seconds'])
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise TimeoutError('GPU process timeout')
            finally:record['gpu_process_wall_seconds']+=time.monotonic()-t;save(path,record)
        if code:raise RuntimeError('Actual MoGe inference process failed; see retained log')
        record['model_calls']=json.loads((root/'inference_receipt.json').read_text())['inference_calls'];record['status']='completed'
    except Exception as exc:
        record['status']='blocked_or_failed';record['errors'].append({'type':type(exc).__name__,'summary':str(exc)[:250]})
        if (root/'inference_receipt.json').exists():record['model_calls']=json.loads((root/'inference_receipt.json').read_text())['inference_calls']
        save(path,record);raise
    finally:record['resume_wall_seconds']=time.monotonic()-started;save(path,record)
    print(json.dumps({k:record[k] for k in ['status','setup_wall_seconds','gpu_process_wall_seconds','model_calls','network_conservative_bytes']}))

if __name__=='__main__':main()
