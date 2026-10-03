"""Frozen three-condition Pi3X reference ablation; no evaluator truth is read.

This is a controlled static reference/mesh adapter experiment, not a fresh AWSM
agent session or full semantic/physics qualification of quality_v2.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8<<20),b''):h.update(chunk)
    return h.hexdigest()


def save(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False))


def similarity(source,target):
    import numpy as np
    x=source-source.mean(0);y=target-target.mean(0)
    u,s,vt=np.linalg.svd(y.T@x/len(x));D=np.eye(3);D[-1,-1]=np.linalg.det(u@vt);R=u@D@vt
    scale=float(np.sum(s*np.diag(D))/np.mean(np.sum(x*x,axis=1)))
    t=target.mean(0)-scale*R@source.mean(0)
    return scale,R,t


def mesh_adapter(arrays,images,Ks,supplied_poses,condition,out):
    import numpy as np
    local=arrays['local_points'][0];pred_poses=arrays['camera_poses'][0];poses=pred_poses
    scale=1.;fit=None
    if condition=='RGB_K_T':
        scale,R,t=similarity(pred_poses[:,:3,3],supplied_poses[:,:3,3]);poses=supplied_poses
        fit=dict(scale=scale,rmse_m=float(np.sqrt(np.mean(np.sum((pred_poses[:,:3,3]@R.T*scale+t-supplied_poses[:,:3,3])**2,axis=1)))),
                 source='Supplied mapping camera baseline only; no GT mesh/depth/evaluator access')
    N,H,W,_=local.shape;ys,xs=np.mgrid[0:H:2,0:W:2];height,width=ys.shape
    indices=np.arange(height*width).reshape(height,width)
    a=indices[:-1,:-1].ravel();b=indices[:-1,1:].ravel();c=indices[1:,:-1].ravel();d=indices[1:,1:].ravel()
    triangles=np.concatenate([np.stack([a,b,c],1),np.stack([b,d,c],1)])
    vertices=[];faces=[];colors=[];offset=0;counts=[]
    for i in range(N):
        depth=local[i,ys,xs,2]*scale
        if condition=='RGB':p=local[i,ys,xs]*scale
        else:
            p=np.stack([(xs+.5-Ks[i,0,2])/Ks[i,0,0]*depth,(ys+.5-Ks[i,1,2])/Ks[i,1,1]*depth,depth],axis=-1)
        world=p@poses[i,:3,:3].T+poses[i,:3,3]
        valid=np.isfinite(world).all(-1)&(depth>0)&(arrays['conf'][0,i,ys,xs,0]>=0)
        v=world.reshape(-1,3);tri=triangles[valid.ravel()[triangles].all(1)]
        lengths=np.max(np.stack([np.linalg.norm(v[tri[:,0]]-v[tri[:,1]],axis=1),np.linalg.norm(v[tri[:,0]]-v[tri[:,2]],axis=1),np.linalg.norm(v[tri[:,1]]-v[tri[:,2]],axis=1)]),axis=0)
        # Same relative depth-jump rejection in every condition; thresholds never use GT.
        tri=tri[lengths<.15*np.maximum(depth.ravel()[tri].mean(1),1e-3)]
        vertices.append(v);faces.append(tri+offset);colors.append(images[i,:,ys,xs].reshape(-1,3));offset+=len(v);counts.append(len(tri))
    np.savez_compressed(out/'editable_mesh.npz',vertices=np.concatenate(vertices).astype('float32'),faces=np.concatenate(faces).astype('int32'),
                        colors=np.concatenate(colors).astype('float32'),frame_face_counts=np.array(counts),camera_poses=poses)
    save(out/'mesh_receipt.json',dict(status='constructed',representation='editable per-observation triangle patches; not semantic solids',
        source_prediction_sha256=sha(out/'raw_predictions.npz'),mesh_sha256=sha(out/'editable_mesh.npz'),frames=N,
        vertices=sum(len(v) for v in vertices),triangles=sum(counts),triangles_by_frame=counts,confidence_policy='sigmoid(conf)>=0.5',
        downsample_stride=2,depth_jump_relative_threshold=.15,scale_from_supplied_camera_fit=fit,
        coordinate_frame='supplied world' if condition=='RGB_K_T' else 'predicted camera gauge',
        missing_regions='retained in evaluation denominator; no background/GT mesh completion',qualification='unverified semantics, closure and physics'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--gpu',type=int,default=3);parser.add_argument('--reference-adapter',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    import numpy as np
    input_manifest=json.loads((args.input/'frames.json').read_text());frames=input_manifest['frames']
    if len(frames)!=36 or input_manifest['scene_id']!='eth3d_delivery_area':raise ValueError('Expected frozen36-frame real-scene input')
    prep=dict(output_size_wh=[420,280],resize='Pillow LANCZOS',crop='none',color='RGB',tensor='float32_0_1',
              camera_convention='K_raster uses image-corner origin; +0.5 ray grid in Pi3X; native workflow manifest uses integer centres')
    protocol=dict(status='frozen_before_inference',frame_manifest_sha256=sha(args.input/'frames.json'),conditions=['RGB','RGB_K','RGB_K_T'],
        runner_sha256=sha(__file__),code_revision='9fa3ddb3f8d53041f8b2738df404f62223bbaa7b',
        weight_revision='bb1deea4d7423de5b30691739cb451a3f57dc1d5',weight_sha256='69972d6e1c4492cb4d737a84fe940e357087d81c52f5c9b7c160b49c1f41669a',
        preprocessing=prep,seed=0,forwards_per_condition=1,max_seconds=1200,
        estimator_scope='Pi3X static adapter ablation; not complete Agent workflow/AWSM comparison',
        permission='All RGB shared; only RGB_K/RGB_K_T receive K and only RGB_K_T receives mapping GT poses; no GT depth/mesh/heldout inputs')
    save(args.output/'protocol.json',protocol)
    if sha(args.runtime/'model.safetensors')!=protocol['weight_sha256']:raise ValueError('Checkpoint hash changed')
    expected={'source/pi3/models/pi3x.py':'d29a67eec7cc38e110baa1a07aac1b178f0317a8ded9e391f07da33f09ef5b7a',
              'source/pi3/utils/basic.py':'d4eb33dbc753d4f5a2f3cba161bc5b96068005e789430a8ddc5062c1cc504ad1'}
    for path,h in expected.items():
        if sha(args.runtime/path)!=h:raise ValueError('Runtime source changed '+path)
    selected=next(line.split(',') for line in subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).splitlines() if int(line.split(',')[0])==args.gpu)
    if int(selected[2])>16 or int(selected[3])!=0:raise RuntimeError('Selected GPU has existing work')
    os.environ['CUDA_VISIBLE_DEVICES']=selected[1].strip();sys.path.insert(0,str(args.runtime/'source'))
    import torch
    from PIL import Image
    from safetensors.torch import load_file
    from pi3.models.pi3x import Pi3X
    spec=importlib.util.spec_from_file_location('reference_adapter',args.reference_adapter);adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    frozen=adapter.freeze(dict(preprocessing=prep,frames=[dict(id=f['frame_id'],path=str(args.input/'rgb'/f"{i:03d}.png"),pts_seconds=0.,role='fit') for i,f in enumerate(frames)]),args.input)
    frozen['timestamp_scope']='Each independent DSLR still has presentation time zero; no video timing or frame-rate claim';save(args.output/'frozen_inputs.json',frozen)
    images=[];Ks=[];poses=[]
    for i,f in enumerate(frames):
        path=args.input/'rgb'/f'{i:03d}.png'
        if sha(path)!=f['sha256']:raise ValueError('RGB hash drift')
        images.append(np.asarray(Image.open(path).convert('RGB').resize((420,280),Image.Resampling.LANCZOS),np.float32).transpose(2,0,1)/255)
        K=np.array(f['K_raster'],float);K[0]*=420/f['image_size'][0];K[1]*=280/f['image_size'][1];Ks.append(K);poses.append(f['T_world_camera'])
    images=np.stack(images);Ks=np.array(Ks);poses=np.array(poses)
    torch.set_num_threads(2);torch.manual_seed(0);start=time.monotonic()
    model=Pi3X(use_multimodal=True).eval();weights=load_file(str(args.runtime/'model.safetensors'),device='cpu');model.load_state_dict(weights,strict=True);del weights
    model=model.to('cuda');tensor=torch.from_numpy(images)[None].to('cuda')
    summary=dict(status='running',gpu=[x.strip() for x in selected],strict_checkpoint_loading=True,torch=torch.__version__,conditions=[])
    save(args.output/'summary.json',summary)
    for condition in protocol['conditions']:
        out=args.output/condition;out.mkdir();row=dict(condition=condition,status='started');summary['conditions'].append(row);save(args.output/'summary.json',summary)
        began=time.monotonic()
        try:
            if time.monotonic()-start>1200:raise TimeoutError('Frozen shared inference budget exceeded')
            torch.manual_seed(0);torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize()
            kwargs={}
            if condition!='RGB':kwargs['intrinsics']=torch.tensor(Ks,dtype=torch.float32,device='cuda')[None]
            if condition=='RGB_K_T':kwargs['poses']=torch.tensor(poses,dtype=torch.float32,device='cuda')[None]
            with torch.inference_mode(),torch.amp.autocast('cuda',dtype=torch.bfloat16):pred=model(imgs=tensor,**kwargs)
            torch.cuda.synchronize();row.update(forward_seconds=time.monotonic()-began,peak_reserved_bytes=torch.cuda.max_memory_reserved())
            arrays={k:v.detach().float().cpu().numpy() for k,v in pred.items() if torch.is_tensor(v)};np.savez_compressed(out/'raw_predictions.npz',**arrays)
            provenance=dict(input_sha256=sha(args.output/'frozen_inputs.json'),npz_sha256=sha(out/'raw_predictions.npz'),
                **{k:protocol[k] for k in ['code_revision','weight_revision','weight_sha256']},preprocessing=prep,
                frame_ids=[f['frame_id'] for f in frames],kind='backend_output',run_receipt=str(args.output/'summary.json'))
            save(out/'provenance.json',provenance);save(out/'reference_receipt.json',adapter.consume(args.output/'frozen_inputs.json',out/'raw_predictions.npz',provenance,.5))
            mesh_adapter(arrays,images,Ks,poses,condition,out)
            row.update(status='complete',predictions_sha256=sha(out/'raw_predictions.npz'),mesh_sha256=sha(out/'editable_mesh.npz'))
            del pred,arrays;torch.cuda.empty_cache()
        except Exception as exc:
            row.update(status='failed',error=repr(exc));torch.cuda.empty_cache()
        row['wall_seconds']=time.monotonic()-began;save(args.output/'summary.json',summary);print(json.dumps(row),flush=True)
    summary.update(status='complete' if all(r['status']=='complete' for r in summary['conditions']) else 'incomplete',wall_seconds=time.monotonic()-start)
    save(args.output/'summary.json',summary)


if __name__=='__main__':main()
