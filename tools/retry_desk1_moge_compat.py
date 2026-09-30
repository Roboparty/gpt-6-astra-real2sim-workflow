"""One retry with an explicitly recorded Triton metadata compatibility shim."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from run_desk1_moge3 import sha,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',type=Path,required=True);p.add_argument('--python',required=True);p.add_argument('--gpu',type=int,required=True);p.add_argument('--child',action='store_true');a=p.parse_args()
    if a.child:
        import triton.language as tl
        if not hasattr(tl.int32,'itemsize'):tl.dtype.itemsize=property(lambda self:self.primitive_bitwidth//8)
        import torch
        from flex_gemm.kernels.triton.hashmap import hashmap_build,hashmap_lookup
        keys=torch.arange(512,dtype=torch.int32,device='cuda').reshape(128,4);table=hashmap_build(keys);lookup=hashmap_lookup(table,keys,keys.flip(0));torch.cuda.synchronize()
        if not torch.equal(lookup,torch.arange(127,-1,-1,dtype=torch.int32,device='cuda')):raise ValueError('Hash map roundtrip mismatch')
        save(a.output/'compatibility_test.json',{'status':'passed','real_gpu_hash_queries':128,'inference_calls':0,'dtype_bytes':{str(t):t.itemsize for t in [tl.int8,tl.int16,tl.int32,tl.int64]},'shim_script_sha256':sha(__file__)})
        from run_desk1_moge3 import inference
        inference(json.loads((a.output/'phase.json').read_text()),a.output);return
    original=json.loads((a.base/'receipt.json').read_text());repair=json.loads(a.phase.read_text());a.output.mkdir(parents=True,exist_ok=False);os.link(a.base/'model.pt',a.output/'model.pt');(a.output/'phase.json').write_bytes((a.base/'phase.json').read_bytes())
    if original['model_calls']!=1:raise ValueError('Original failure must remain exactly one inference attempt')
    record={'status':'starting_retry','original_attempts':1,'additional_attempts':0,'original_gpu_seconds':original['gpu_process_wall_seconds'],'repair_sha256':sha(a.phase),'script_sha256':sha(__file__),'model_sha256':sha(a.output/'model.pt')};save(a.output/'retry_receipt.json',record)
    selected=next(x for x in subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines() if x.split(',')[0].strip()==str(a.gpu));fields=[x.strip() for x in selected.split(',')]
    if int(fields[2])>16 or int(fields[3])!=0:raise ValueError('GPU has external work')
    budget=json.loads((a.base/'phase.json').read_text())['limits']['gpu_process_wall_seconds']-original['gpu_process_wall_seconds'];record['gpu_preflight']={'index':a.gpu,'uuid':fields[1]};t=time.monotonic()
    env={**os.environ,'CUDA_VISIBLE_DEVICES':str(a.gpu),'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','PYTHONPATH':os.pathsep.join(map(str,[a.base/'deps',a.base/'MoGe',a.base/'utils3d-moge',a.base/'FlexGEMM'])),'TRITON_CACHE_DIR':str(a.output/'triton_cache'),'HF_HOME':str(a.output/'hf_cache'),'TORCH_HOME':str(a.output/'torch_cache'),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    argv=[a.python,__file__,'--base',str(a.base),'--output',str(a.output),'--phase',str(a.phase),'--python',a.python,'--gpu',str(a.gpu),'--child']
    with (a.output/'retry.log').open('w') as log:
        proc=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        try:code=proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=-1
    record.update(status='completed' if code==0 else 'failed',returncode=code,gpu_process_wall_seconds=time.monotonic()-t)
    if (a.output/'inference_receipt.json').exists():record['additional_attempts']=json.loads((a.output/'inference_receipt.json').read_text())['inference_calls']
    record['cumulative_attempts']=record['original_attempts']+record['additional_attempts'];record['cumulative_gpu_seconds']=record['original_gpu_seconds']+record['gpu_process_wall_seconds'];save(a.output/'retry_receipt.json',record);print(json.dumps(record))
    if code:raise RuntimeError('Compatibility retry failed; retain all costs and original failure')

if __name__=='__main__':main()
