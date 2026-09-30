"""CPU-only recovery from the retained successful single-frame forward tensors."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image
from run_desk1_pi3x_reference import sha,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root;path=root/'receipt.json';receipt=json.loads(path.read_text());raw=np.load(root/'raw_predictions.npz')
    print(json.dumps({'raw_outputs':{k:list(raw[k].shape) for k in raw.files}}))
    if receipt['inference_calls']!=1 or not receipt.get('checkpoint_loaded_strictly'):raise ValueError('No eligible original successful forward')
    if (root/'receipt_before_adapter_repair.json').exists():raise ValueError('Repair already applied')
    save(root/'receipt_before_adapter_repair.json',receipt);local=raw['local_points'][0,0];H,W=local.shape[:2];depth=local[...,2];mask=np.isfinite(local).all(axis=-1)&(depth>0);confidence=None
    for key in ['confidence','conf']:
        if key in raw.files:
            confidence=1/(1+np.exp(-raw[key][0,0].squeeze()));mask&=np.isfinite(confidence)&(confidence>.1);receipt['confidence_output_key']=key;break
    if confidence is None:receipt['confidence_status']='unavailable; no confidence filter invented'
    yy,xx=np.mgrid[:H,:W];u=(xx+.5)/W-.5;v=(yy+.5)/H-.5;dx=local[...,0]/depth;dy=local[...,1]/depth;fx=float(np.sum(dx[mask]*u[mask])/np.sum(dx[mask]**2));fy=float(np.sum(dy[mask]*v[mask])/np.sum(dy[mask]**2))
    if not fx>0 or not fy>0:raise ValueError('Invalid centred focal')
    residual=np.sqrt((fx*dx-u)**2*W**2+(fy*dy-v)**2*H**2);K=np.array([[fx,0,.5],[0,fy,.5],[0,0,1]],np.float32);points=np.stack([u*depth/fx,v*depth/fy,depth],axis=-1).astype(np.float32)
    reference=root/'reference';reference.mkdir(exist_ok=False);arrays={'points':points,'depth':depth,'mask':mask,'intrinsics':K}
    if confidence is not None:arrays['confidence']=confidence
    np.savez_compressed(reference/'prediction.npz',**arrays)
    image=Image.open(root/'input/00.jpg').convert('RGB').resize((W,H),Image.Resampling.LANCZOS);image.save(reference/'input.png')
    receipt.update(status='predicted_after_cpu_adapter_recovery',reference_sha256=sha(reference/'prediction.npz'),raw_sha256=sha(root/'raw_predictions.npz'),
        output_shapes={k:list(raw[k].shape) for k in raw.files},raw_direction_projection_median_px=float(np.median(residual[mask])),raw_direction_projection_p95_px=float(np.percentile(residual[mask],95)),
        K_normalized=K.tolist(),metric_scale_status='relative; no true metric scale inferred',adapter_repair={'new_model_calls':0,'reason':'Use actual returned confidence key or explicitly unavailable, preserving original raw tensors','script_sha256':sha(__file__)})
    save(path,receipt);print(json.dumps({'status':receipt['status'],'source_images':1,'model_calls':receipt['inference_calls'],'raw_projection_median_px':receipt['raw_direction_projection_median_px']}))

if __name__=='__main__':main()
