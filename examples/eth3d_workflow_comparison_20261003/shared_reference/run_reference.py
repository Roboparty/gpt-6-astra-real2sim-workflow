from pathlib import Path
import os, json, time, hashlib, shutil, platform, subprocess
import numpy as np
import torch
from depth_anything_3.api import DepthAnything3
import depth_anything_3.api as da3_api
original_align=da3_api.align_poses_umeyama
alignment_scales=[]
def audit_align(*a,**kw):
 result=original_align(*a,**kw); alignment_scales.append(float(result[2])); return result
da3_api.align_poses_umeyama=audit_align
ROOT=Path(__file__).resolve().parent
sha=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p,x): Path(p).write_text(json.dumps(x,indent=2)+'\n')
config=json.loads((ROOT/'frozen_config.json').read_text())
frames=json.loads((ROOT/'frames.json').read_text())['frames']
out=ROOT/'shared'; out.mkdir(exist_ok=True)
(out/'frames').mkdir(exist_ok=True); (ROOT/'windows').mkdir(exist_ok=True)
for n in ['frozen_config.json','frames.json','cameras.json']:shutil.copyfile(ROOT/n,out/n)
started=time.monotonic(); torch.manual_seed(42); np.random.seed(42); torch.set_num_threads(8)
provenance={'torch':torch.__version__,'cuda':torch.version.cuda,'python':platform.python_version(),'gpu':torch.cuda.get_device_name(),'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'weights_sha256':sha(ROOT/'weights/model.safetensors'),'config_sha256':sha(ROOT/'frozen_config.json'),'script_sha256':sha(__file__),'source_commit':config['official_source_commit'],'source_archive_sha256':sha(ROOT/'source.tar.gz'),'aws_source_commit':'4dc2f5c515b77fd5f5f8dbedbdad76663882267e','aws_run_script_sha256':'b86c93da47fb6fd04979fcf12cfc84cc914dab0b806c5ad76e1682bc19cd261d','aws_depth_pipeline_sha256':'215684b1c0d1da73445e34fee7f38f985ddbcb3bfd4c6b807b2633b7f7bc4e15'}
js(out/'provenance.json',provenance)
model=DepthAnything3.from_pretrained(str(ROOT/'weights')).to('cuda').eval(); model.device=torch.device('cuda')
print('MODEL_READY',time.monotonic()-started,flush=True)
selected={}; windows=[]
for wi,indices in enumerate(config['windows']):
 t0=time.monotonic(); fs=[frames[i] for i in indices]
 T=np.asarray([f['T_world_camera'] for f in fs],dtype=np.float32)
 ext=np.linalg.inv(T); K=np.asarray([f['K_raster'] for f in fs],dtype=np.float32)
 baseline=np.linalg.norm(T[:,None,:3,3]-T[None,:,:3,3],axis=-1).max(); assert baseline>1e-5
 pred=model.inference([f['path'] for f in fs],extrinsics=ext,intrinsics=K,align_to_input_ext_scale=True,process_res=392,process_res_method='upper_bound_resize',ref_view_strategy='saddle_balanced',use_ray_pose=False)
 d=np.asarray(pred.depth,dtype=np.float32); c=np.asarray(pred.conf,dtype=np.float32)
 sky=np.zeros_like(d,dtype=bool) if pred.sky is None else np.asarray(pred.sky,dtype=bool)
 valid=np.isfinite(d)&(d>0)&~sky; confvalid=np.isfinite(c)
 assert d.shape[0]==4 and np.any(valid) and np.isfinite(pred.intrinsics).all()
 records=[]
 for j,i in enumerate(indices):
  kr=np.asarray(pred.intrinsics[j],dtype=np.float32); ki=kr.copy(); ki[:2,2]-=0.5
  scale=np.diag([d.shape[2]/fs[j]['image_size'][0],d.shape[1]/fs[j]['image_size'][1],1])
  assert np.allclose(kr,scale@np.asarray(fs[j]['K_raster']),rtol=1e-5,atol=1e-4)
  p=ROOT/'windows'/f'w{wi:02d}_f{i:03d}.npz'
  np.savez_compressed(p,depth_z_m=np.where(valid[j],d[j],0),valid_mask=valid[j],confidence=np.where(confvalid[j],c[j],0),confidence_valid_mask=confvalid[j],sky=sky[j],K_depth=ki,K_depth_raster=kr,T_world_camera=T[j],input_world_to_camera=ext[j],processed_rgb=pred.processed_images[j],sample_index=np.int64(i),window_index=np.int64(wi))
  rec={'sample_index':i,'frame_id':frames[i]['frame_id'],'window':wi,'centrality':min(j,3-j),'path':str(p),'sha256':sha(p),'shape':list(d[j].shape),'valid_fraction':float(valid[j].mean()),'finite_confidence_fraction':float(confvalid[j].mean()),'valid_depth_quantiles_m':np.quantile(d[j][valid[j]],[0,.1,.5,.9,1]).tolist()}
  records.append(rec)
  if i not in selected or (rec['centrality'],-wi)>(selected[i]['centrality'],-selected[i]['window']):selected[i]=rec
 w={'window':wi,'indices':indices,'baseline_m':float(baseline),'depth_divisor_from_camera_alignment':alignment_scales[-1],'seconds':time.monotonic()-t0,'records':records}; windows.append(w); js(ROOT/'windows'/f'w{wi:02d}.json',w)
 print(json.dumps({'window':wi,'seconds':w['seconds'],'total_seconds':time.monotonic()-started}),flush=True)
assert len(selected)==36
final=[]
for i in range(36):
 rec=selected[i].copy(); dst=out/'frames'/f'{i:03d}.npz';shutil.copyfile(rec['path'],dst);rec['path']=str(dst.relative_to(out));rec['sha256']=sha(dst);final.append(rec)
manifest={'schema_version':1,'status':'COMPLETE','model':'DA3-GIANT','frames':final,'windows':17,'seconds':time.monotonic()-started,'depth':'optical camera-Z in metres aligned only from registered input camera translations; learned prediction, not ground-truth geometry','intrinsics':'K_depth is integer-centre; K_depth_raster is corner-origin; use K_depth with integer u/v unprojection','mask':'valid_mask: finite positive non-sky prediction; invalid depth stored as0. confidence_valid_mask marks finite raw model confidence, not calibrated probability; invalid confidence stored0. No confidence threshold applied.','camera':'T_world_camera is supplied OpenCV C2W in common canonical metres/Z-up gauge','files':{n:sha(out/n) for n in ['frozen_config.json','frames.json','cameras.json','provenance.json']}}
js(out/'manifest.json',manifest)
print(json.dumps({'status':'COMPLETE','manifest':str(out/'manifest.json'),'manifest_sha256':sha(out/'manifest.json'),'seconds':manifest['seconds']}),flush=True)
