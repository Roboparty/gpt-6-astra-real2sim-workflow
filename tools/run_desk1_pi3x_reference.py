"""One real single-RGB Pi3X control; no invented second view or prior scene read."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--gpu',type=int,required=True);a=p.parse_args();cfg=json.loads(a.phase.read_text());a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic();gpu_start=None
    receipt={'status':'started','source_sha256':cfg['source_sha256'],'phase_sha256':sha(a.phase),'script_sha256':sha(__file__),'inference_calls':0,'input_images':1,'gpu_process_wall_seconds':0,'errors':[]}
    save(a.output/'receipt.json',receipt)
    try:
        if sha(cfg['source_image'])!=cfg['source_sha256']:raise ValueError('Source changed')
        base=Path(cfg['runtime_root'])
        for rel,value in cfg['source_hashes'].items():
            if sha(base/rel)!=value:raise ValueError('Pinned model source changed')
        if sha(base/'model.safetensors')!=cfg['weight_sha256']:raise ValueError('Pinned model weights changed')
        selected=next(row for row in subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines() if row.split(',')[0].strip()==str(a.gpu));fields=[x.strip() for x in selected.split(',')]
        if int(fields[2])>16 or int(fields[3])!=0:raise ValueError('Selected GPU has external work')
        receipt['gpu_preflight']={'index':a.gpu,'uuid':fields[1],'used_mib':int(fields[2]),'utilization':int(fields[3])};save(a.output/'receipt.json',receipt)
        os.environ['CUDA_VISIBLE_DEVICES']=str(a.gpu);sys.path.insert(0,str(base/'source'))
        import numpy as np
        import torch
        from safetensors.torch import load_file
        from pi3.models.pi3x import Pi3X
        from pi3.utils.basic import load_multimodal_data
        from PIL import Image
        torch.set_num_threads(2);torch.manual_seed(cfg['inference']['seed']);receipt['runtime']={'torch':torch.__version__,'numpy':np.__version__};gpu_start=time.monotonic()
        model=Pi3X(use_multimodal=True).eval();weights=load_file(str(base/'model.safetensors'),device='cpu');model.load_state_dict(weights,strict=True);del weights;model.disable_multimodal(free_cuda_cache=False);model=model.to('cuda');receipt['checkpoint_loaded_strictly']=True
        inputs=a.output/'input';inputs.mkdir();shutil.copyfile(cfg['source_image'],inputs/'00.jpg')
        images,conditions=load_multimodal_data(str(inputs),{'intrinsics':None,'poses':None,'depths':None},interval=1,PIXEL_LIMIT=cfg['inference']['pixel_limit'],device='cuda')
        if images.shape[0]!=1 or images.shape[1]!=1:raise ValueError('Exactly one real input frame required')
        receipt['input_tensor_shape']=list(images.shape);torch.cuda.synchronize();t=time.monotonic();receipt['inference_calls']=1;save(a.output/'receipt.json',receipt)
        with torch.inference_mode(),torch.amp.autocast('cuda',dtype=torch.bfloat16):pred=model(imgs=images,**conditions)
        torch.cuda.synchronize();receipt['forward_seconds']=time.monotonic()-t;arrays={k:v.detach().float().cpu().numpy() for k,v in pred.items() if torch.is_tensor(v)};np.savez_compressed(a.output/'raw_predictions.npz',**arrays)
        local=arrays['local_points'][0,0];H,W=local.shape[:2];depth=local[...,2];confidence_key='confidence' if 'confidence' in arrays else 'conf' if 'conf' in arrays else None;mask=np.isfinite(local).all(axis=-1)&(depth>0)
        confidence=None if confidence_key is None else 1/(1+np.exp(-arrays[confidence_key][0,0].squeeze()))
        if confidence is not None:mask&=np.isfinite(confidence)&(confidence>.1)
        receipt['confidence_status']='unavailable; no invented confidence' if confidence_key is None else 'actual predicted field '+confidence_key
        yy,xx=np.mgrid[:H,:W];u=(xx+.5)/W-.5;v=(yy+.5)/H-.5;dx=local[...,0]/depth;dy=local[...,1]/depth
        fx=float(np.sum(dx[mask]*u[mask])/np.sum(dx[mask]**2));fy=float(np.sum(dy[mask]*v[mask])/np.sum(dy[mask]**2))
        if not fx>0 or not fy>0:raise ValueError('Invalid inferred centred focal')
        residual=np.sqrt((fx*dx-u)**2*W**2+(fy*dy-v)**2*H**2);K=np.array([[fx,0,.5],[0,fy,.5],[0,0,1]],np.float32);points=np.stack([u*depth/fx,v*depth/fy,depth],axis=-1).astype(np.float32)
        reference=a.output/'reference';reference.mkdir();standard={'points':points,'depth':depth,'mask':mask,'intrinsics':K}
        if confidence is not None:standard['confidence']=confidence
        np.savez_compressed(reference/'prediction.npz',**standard)
        rgb=(images[0,0].permute(1,2,0).float().cpu().numpy()*255).clip(0,255).astype(np.uint8);Image.fromarray(rgb).save(reference/'input.png')
        receipt.update(status='predicted',reference_sha256=sha(reference/'prediction.npz'),raw_sha256=sha(a.output/'raw_predictions.npz'),output_shapes={k:list(x.shape) for k,x in arrays.items()},
            camera_adapter='centred focal from raw local point directions; predicted depth reprojected through this declared assumed camera',raw_direction_projection_median_px=float(np.median(residual[mask])),
            raw_direction_projection_p95_px=float(np.percentile(residual[mask],95)),K_normalized=K.tolist(),metric_scale_status='relative, unvalidated; height anchor applied only in editable scene adapter',
            source_unchanged=sha(cfg['source_image'])==cfg['source_sha256'],peak_reserved_bytes=torch.cuda.max_memory_reserved())
    except Exception as exc:receipt['status']='blocked_or_failed';receipt['errors'].append({'type':type(exc).__name__,'summary':str(exc)[:250]});raise
    finally:
        receipt['wall_seconds']=time.monotonic()-start;receipt['gpu_process_wall_seconds']=0 if gpu_start is None else time.monotonic()-gpu_start;save(a.output/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'forward_seconds':receipt['forward_seconds'],'input_images':1,'shape':receipt['input_tensor_shape']}))

if __name__=='__main__':main()
