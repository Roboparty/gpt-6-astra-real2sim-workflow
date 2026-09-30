"""Pinned Triton3.4 runtime upgrade, with retained failures and shared budgets."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from run_desk1_moge3 import sha,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--previous-retry',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--upgrade-phase',type=Path,required=True);p.add_argument('--python',required=True);p.add_argument('--gpu',type=int,required=True);p.add_argument('--child',action='store_true');a=p.parse_args()
    if a.child:
        import torch
        import triton
        import triton.language as tl
        from flex_gemm.kernels.triton.hashmap import hashmap_build,hashmap_lookup
        if triton.__version__!='3.4.0' or tl.int32.itemsize!=4:raise ValueError('Wrong pinned Triton runtime')
        keys=torch.arange(512,dtype=torch.int32,device='cuda').reshape(128,4);table=hashmap_build(keys);lookup=hashmap_lookup(table,keys,keys.flip(0));torch.cuda.synchronize()
        if not torch.equal(lookup,torch.arange(127,-1,-1,dtype=torch.int32,device='cuda')):raise ValueError('Hash map roundtrip mismatch')
        save(a.output/'compatibility_test.json',{'status':'passed','queries':128,'source_library_unmodified':True,'runtime':triton.__version__})
        from run_desk1_moge3 import inference
        inference(json.loads((a.output/'phase.json').read_text()),a.output);return
    a.output.mkdir(parents=True,exist_ok=False);started=time.monotonic();old=json.loads((a.base/'receipt.json').read_text());last=json.loads((a.previous_retry/'retry_receipt.json').read_text());limits=json.loads((a.base/'phase.json').read_text())['limits'];prior_gpu=old['gpu_process_wall_seconds']+last['gpu_process_wall_seconds']
    os.link(a.base/'model.pt',a.output/'model.pt');(a.output/'phase.json').write_bytes((a.base/'phase.json').read_bytes());record={'status':'preparing','prior_model_calls':1,'prior_gpu_seconds':prior_gpu,'upgrade_phase_sha256':sha(a.upgrade_phase),'new_download_bytes':0,'additional_model_calls':0,'gpu_process_wall_seconds':0};save(a.output/'upgrade_receipt.json',record)
    try:
        meta=json.load(urllib.request.urlopen('https://pypi.org/pypi/triton/3.4.0/json',timeout=30));wheel=next(x for x in meta['urls'] if 'cp310' in x['filename'] and 'x86_64' in x['filename']);dest=a.output/wheel['filename']
        with urllib.request.urlopen(wheel['url'],timeout=60) as response,dest.open('wb') as f:
            while chunk:=response.read(4<<20):
                if time.monotonic()-started>900:raise TimeoutError('Additional setup time exhausted')
                f.write(chunk);record['new_download_bytes']+=len(chunk)
                if old.get('network_conservative_bytes',old['network_streamed_bytes']+(1<<28))+record['new_download_bytes']>limits['remote_download_bytes']:raise ValueError('Shared download cap exhausted')
        if sha(dest)!=wheel['digests']['sha256']:raise ValueError('Official PyPI checksum mismatch')
        target=a.output/'triton34';target.mkdir();proc=subprocess.run([a.python,'-m','pip','install','--no-index','--no-deps','--target',str(target),str(dest)],capture_output=True,text=True,timeout=120);(a.output/'install.log').write_text(proc.stdout+'\n'+proc.stderr)
        if proc.returncode:raise ValueError('Isolated wheel installation failed')
        record['wheel_sha256']=sha(dest);record['setup_wall_seconds']=time.monotonic()-started;record['network_conservative_bytes_total']=old['network_conservative_bytes']+record['new_download_bytes'];save(a.output/'upgrade_receipt.json',record)
        selected=next(x for x in subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines() if x.split(',')[0].strip()==str(a.gpu));fields=[x.strip() for x in selected.split(',')]
        if int(fields[2])>16 or int(fields[3])!=0:raise ValueError('Selected GPU has external work')
        env={**os.environ,'CUDA_VISIBLE_DEVICES':str(a.gpu),'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','PYTHONPATH':os.pathsep.join(map(str,[target,a.base/'deps',a.base/'MoGe',a.base/'utils3d-moge',a.base/'FlexGEMM'])),'TRITON_CACHE_DIR':str(a.output/'triton_cache'),'HF_HOME':str(a.output/'hf_cache'),'TORCH_HOME':str(a.output/'torch_cache'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        args=[a.python,__file__,'--base',str(a.base),'--previous-retry',str(a.previous_retry),'--output',str(a.output),'--upgrade-phase',str(a.upgrade_phase),'--python',a.python,'--gpu',str(a.gpu),'--child'];t=time.monotonic();record['gpu_preflight']={'index':a.gpu,'uuid':fields[1]}
        with (a.output/'run.log').open('w') as log:
            proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            try:code=proc.wait(timeout=limits['gpu_process_wall_seconds']-prior_gpu)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=-1
        record['gpu_process_wall_seconds']=time.monotonic()-t;record['status']='completed' if code==0 else 'failed';record['returncode']=code
        if (a.output/'inference_receipt.json').exists():record['additional_model_calls']=json.loads((a.output/'inference_receipt.json').read_text())['inference_calls']
        if code:raise RuntimeError('Upgraded actual inference failed')
    except Exception as exc:record['status']='failed';record['error']={'type':type(exc).__name__,'summary':str(exc)[:250]};raise
    finally:record['wall_seconds']=time.monotonic()-started;record['cumulative_model_calls']=1+record['additional_model_calls'];record['cumulative_gpu_seconds']=prior_gpu+record['gpu_process_wall_seconds'];save(a.output/'upgrade_receipt.json',record)
    print(json.dumps(record))

if __name__=='__main__':main()
