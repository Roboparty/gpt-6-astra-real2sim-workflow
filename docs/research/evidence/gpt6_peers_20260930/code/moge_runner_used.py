"""One pinned, bounded MoGe-3 reference inference; all large files stay remote."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def save(p,d):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2,allow_nan=False));tmp.replace(p)

def inference(phase,root):
    import importlib.metadata as metadata
    import warnings
    import numpy as np
    import cv2
    import torch
    from moge.model.v3 import MoGeModel
    cfg=phase['moge'];out=root/'reference';out.mkdir(exist_ok=False);started=time.monotonic()
    receipt={'status':'started','source_sha256':sha(phase['source_image']),'model_sha256':sha(root/'model.pt'),'inference_calls':0,
        'runtime':{name:metadata.version(name) for name in ['torch','torchvision','numpy','triton']},'script_sha256':sha(__file__),'outputs':[]}
    save(root/'inference_receipt.json',receipt)
    if receipt['source_sha256']!=phase['source_sha256'] or receipt['model_sha256']!=cfg['sha256']:raise ValueError('Frozen input hash mismatch')
    torch.set_num_threads(2);torch.manual_seed(cfg['seed']);torch.cuda.reset_peak_memory_stats()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');model=MoGeModel.from_pretrained(root/'model.pt').to('cuda').eval()
        receipt['load_warnings']=[str(x.message) for x in caught]
    if any('random' in x.lower() or 'absent from the checkpoint' in x.lower() for x in receipt['load_warnings']):raise ValueError('Missing model parameters cannot be claimed loaded')
    image=cv2.cvtColor(cv2.imread(phase['source_image']),cv2.COLOR_BGR2RGB);h,w=image.shape[:2];scale=min(1,cfg['input_resize_max']/max(h,w));image=cv2.resize(image,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
    tensor=torch.from_numpy(image.astype(np.float32)/255).permute(2,0,1).to('cuda');torch.cuda.synchronize();t=time.monotonic()
    receipt['inference_calls']=1;save(root/'inference_receipt.json',receipt)
    with torch.inference_mode():result=model.infer(tensor,resolution_level=cfg['resolution_level'],refine_steps=cfg['refine_steps'],use_fp16=cfg['fp16'],apply_mask=cfg['apply_mask'],force_projection=cfg['force_projection'])
    torch.cuda.synchronize();receipt['forward_wall_seconds']=time.monotonic()-t
    arrays={k:v.detach().cpu().numpy() for k,v in result.items() if isinstance(v,torch.Tensor)}
    for key in ['points','depth','intrinsics','mask']:
        if key not in arrays:raise ValueError('Missing actual MoGe output '+key)
    np.savez_compressed(out/'prediction.npz',**arrays);cv2.imwrite(str(out/'input.png'),cv2.cvtColor(image,cv2.COLOR_RGB2BGR))
    if 'normal' in arrays:cv2.imwrite(str(out/'normal_preview.png'),cv2.cvtColor(np.clip((arrays['normal']+1)*127.5,0,255).astype(np.uint8),cv2.COLOR_RGB2BGR))
    mask=arrays['mask'].astype(bool);valid=mask&np.isfinite(arrays['depth'])&(arrays['depth']>0)
    d=arrays['depth'];lo,hi=np.percentile(d[valid],[2,98]);vis=np.clip((d-lo)/(hi-lo),0,1);vis[~valid]=0;cv2.imwrite(str(out/'depth_preview.png'),cv2.applyColorMap((vis*255).astype(np.uint8),cv2.COLORMAP_TURBO))
    receipt.update(status='inferred',wall_seconds=time.monotonic()-started,checkpoint_loaded=True,
        peak_memory_allocated_bytes=torch.cuda.max_memory_allocated(),peak_memory_reserved_bytes=torch.cuda.max_memory_reserved(),
        output_shapes={k:list(v.shape) for k,v in arrays.items()},finite_positive_depth_pixels=int(valid.sum()),raster=list(image.shape[:2][::-1]),
        intrinsics=arrays['intrinsics'].tolist(),confidence_status='unavailable unless explicitly output by this model',metric_scale_status='model estimate, not independently measured',
        source_unchanged=sha(phase['source_image'])==phase['source_sha256'])
    receipt['outputs']=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.is_file()];save(root/'inference_receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'forward_seconds':receipt['forward_wall_seconds'],'raster':receipt['raster'],'outputs':receipt['output_shapes']}))

def setup_and_run(phase,root,base_python,gpu,phase_path):
    root.mkdir(parents=True,exist_ok=False);shutil.copyfile(phase_path,root/'phase.json');started=time.monotonic();limits=phase['limits'];receipt={'status':'preparing','phase_sha256':sha(phase_path),'script_sha256':sha(__file__),'downloads':[],'network_streamed_bytes':0,'gpu_process_wall_seconds':0,'model_calls':0,'paid_external_api_requests':0,'errors':[]}
    cfg=phase['moge'];env={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','CUDA_VISIBLE_DEVICES':'','PIP_INDEX_URL':'https://pypi.org/simple',
        'PIP_CACHE_DIR':str(root/'pip_cache'),'TRITON_CACHE_DIR':str(root/'triton_cache'),'HF_HOME':str(root/'hf_cache'),'TORCH_HOME':str(root/'torch_cache')}
    def remaining():
        value=limits['setup_wall_seconds']-(time.monotonic()-started)
        if value<=0:raise TimeoutError('Shared setup time limit exhausted')
        return value
    def persist():save(root/'receipt.json',receipt)
    def download(label,url,dest,expected_sha=None,expected_bytes=None):
        row={'id':label,'source_url':url,'status':'running','streamed_bytes':0};receipt['downloads'].append(row);persist();t=time.monotonic()
        with urllib.request.urlopen(url,timeout=min(60,remaining())) as response,Path(dest).open('wb') as f:
            while b:=response.read(4<<20):
                remaining();f.write(b);row['streamed_bytes']+=len(b);receipt['network_streamed_bytes']+=len(b)
                if receipt['network_streamed_bytes']>limits['remote_download_bytes']:raise ValueError('Download byte limit exceeded')
        row.update(status='downloaded',sha256=sha(dest),bytes=Path(dest).stat().st_size,wall_seconds=time.monotonic()-t)
        if expected_sha and row['sha256']!=expected_sha:raise ValueError('Download SHA mismatch: '+label)
        if expected_bytes and row['bytes']!=expected_bytes:raise ValueError('Download size mismatch: '+label)
        persist()
    def command(label,argv,timeout,extra_env=None):
        t=time.monotonic()
        with (root/(label+'.log')).open('w') as stream:
            proc=subprocess.Popen(argv,env={**env,**(extra_env or {})},stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise TimeoutError(label+' timed out')
        receipt.setdefault('commands',[]).append({'id':label,'returncode':code,'wall_seconds':time.monotonic()-t});persist()
        if code:raise RuntimeError(label+' exited '+str(code))
    try:
        packages=[]
        for owner,repo,revision in [('microsoft','MoGe',cfg['code']),('EasternJournalist','utils3d-moge',cfg['utils3d_commit']),('JeffreyXiang','FlexGEMM',cfg['flex_gemm_commit'])]:
            dest=root/(repo+'.tar.gz');download(repo,'https://codeload.github.com/'+owner+'/'+repo+'/tar.gz/'+revision,dest)
            extracted=root/repo;extracted.mkdir()
            with tarfile.open(dest) as archive:
                for member in archive.getmembers():
                    relative=Path(member.name);member.name=str(Path(*relative.parts[1:]))
                    if not member.name or member.name=='.':continue
                    target=(extracted/member.name).resolve()
                    if not target.is_relative_to(extracted.resolve()) or member.issym() or member.islnk():raise ValueError('Unsafe upstream archive member')
                    archive.extract(member,extracted,filter='data')
            packages.append(extracted)
        wheels=root/'wheels';wheels.mkdir();deps=root/'deps';deps.mkdir()
        command('wheel_download',[base_python,'-m','pip','download','--index-url','https://pypi.org/simple','--no-deps','--only-binary=:all:','--dest',str(wheels),'numpy=='+cfg['numpy'],'triton=='+cfg['triton']],min(600,remaining()))
        for wheel in wheels.glob('*.whl'):
            name,version=wheel.name.split('-')[:2];data=json.load(urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=min(30,remaining())))
            official=next(x for x in data['urls'] if x['filename']==wheel.name)
            if sha(wheel)!=official['digests']['sha256']:raise ValueError('PyPI wheel checksum mismatch')
            receipt['downloads'].append({'id':wheel.name,'source_url':official['url'],'status':'verified','sha256':sha(wheel),'bytes':wheel.stat().st_size})
            receipt['network_streamed_bytes']+=wheel.stat().st_size
        if receipt['network_streamed_bytes']+(1<<28)+cfg['bytes']>limits['remote_download_bytes']:raise ValueError('Download plan exceeds cap')
        command('wheel_install',[base_python,'-m','pip','install','--no-index','--no-deps','--target',str(deps),*map(str,wheels.glob('*.whl'))],min(120,remaining()))
        pythonpath=os.pathsep.join(map(str,[deps,*packages]));env['PYTHONPATH']=pythonpath
        # Importing package source avoids invoking its optional installer/cache side effects.
        command('moge_import',[base_python,'-c','from moge.model.v3 import MoGeModel; print("MOGE3_IMPORT_OK")'],min(120,remaining()))
        download('model','https://huggingface.co/'+cfg['repo']+'/resolve/'+cfg['revision']+'/'+cfg['file'],root/'model.pt',cfg['sha256'],cfg['bytes'])
        receipt['setup_wall_seconds']=time.monotonic()-started;receipt['network_conservative_bytes']=receipt['network_streamed_bytes']+(1<<28);persist()
        inventory=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True).stdout.splitlines()
        selected=next(row for row in inventory if row.split(',')[0].strip()==str(gpu));fields=[x.strip() for x in selected.split(',')]
        if int(fields[2])>16 or int(fields[3])!=0:raise ValueError('Selected GPU no longer idle; external work is not touched')
        receipt['gpu_preflight']={'index':gpu,'uuid':fields[1],'memory_used_mib':int(fields[2]),'utilization':int(fields[3])};receipt['status']='inference_running';persist();t=time.monotonic()
        try:command('moge_inference',[base_python,__file__,'--phase',str(root/'phase.json'),'--root',str(root),'--mode','inference'],limits['gpu_process_wall_seconds'],{'CUDA_VISIBLE_DEVICES':str(gpu),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
        finally:receipt['gpu_process_wall_seconds']=time.monotonic()-t;persist()
        receipt['model_calls']=json.loads((root/'inference_receipt.json').read_text())['inference_calls'];receipt['status']='completed'
    except Exception as exc:
        receipt['status']='blocked_or_failed';receipt['errors'].append({'type':type(exc).__name__,'summary':str(exc)[:250]})
        if (root/'inference_receipt.json').exists():receipt['model_calls']=json.loads((root/'inference_receipt.json').read_text())['inference_calls']
        persist();raise
    finally:
        receipt['wall_seconds']=time.monotonic()-started;persist()
    print(json.dumps({k:receipt[k] for k in ['status','setup_wall_seconds','gpu_process_wall_seconds','model_calls','network_conservative_bytes']}))

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--mode',choices=['all','inference'],default='all')
    p.add_argument('--base-python');p.add_argument('--gpu',type=int,default=6);a=p.parse_args();phase=json.loads(a.phase.read_text())
    if a.mode=='inference':inference(phase,a.root);return
    if a.root.exists():raise ValueError('New attempt root already exists; do not reset or overwrite it')
    a.root.parent.mkdir(parents=True,exist_ok=True)
    setup_and_run(phase,a.root,a.base_python,a.gpu,a.phase)

if __name__=='__main__':main()
