from pathlib import Path
import json,hashlib,numpy as np
from PIL import Image
r=Path('/data/wqz/real2sim-agent-compare-20261003/comparison');out=r/'audit';t=Path('/data/wqz/real2sim-awsm-20261003/eth3d/benchmark_v1/evaluation');views=json.loads((t/'views.json').read_text());viewmap={v['frame_id']:v for v in views};sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for m in ['OURS','AWSM']:
 d=np.load(out/f'{m}_model_to_laser_requeried.npy');owners=np.load(out/f'{m}_sample_owners.npy');points=np.load(r/'evaluation'/m/'model_surface_samples.npy');top=[]
 for name in np.unique(owners):
  take=owners==name;top.append(dict(object=str(name),samples=int(take.sum()),sample_fraction=float(take.mean()),mean_distance_m=float(d[take].mean()),distance_sum_fraction=float(d[take].sum()/d.sum()),contribution_to_overall_mean_m=float(d[take].sum()/len(d)),over_1m_fraction=float((d[take]>1).mean())))
 top.sort(key=lambda x:x['contribution_to_overall_mean_m'],reverse=True);seen=np.zeros(len(points),bool)
 for v in views:
  T=np.array(v['T_world_camera']);K=np.array(v['K']);q=(points-T[:3,3])@T[:3,:3];z=q[:,2];u=q[:,0]/z*K[0,0]+K[0,2];yy=q[:,1]/z*K[1,1]+K[1,2];W,H=v['image_size'];seen|=(z>0)&(u>=-.5)&(u<W-.5)&(yy>=-.5)&(yy<H-.5)
 result=dict(method=m,top20_objects=top[:20],all_objects=top,never_in_any_44_camera_frustum=dict(count=int((~seen).sum()),fraction=float((~seen).mean()),distance_sum_fraction=float(d[~seen].sum()/d.sum())),scope='Post-freeze explanation only; no mask, metric, mesh or denominator changed. Laser-unmatched surfaces may be unsupported completion or unobserved scan coverage, not automatically incorrect physical geometry. Whole-model surface metric includes back/exterior surfaces unlike sparse visible-depth metric.');(out/f'{m}_surface_attribution.json').write_text(json.dumps(result,indent=2));print('ATTRIBUTION',m,json.dumps(dict(top=top[:8],frustum=result['never_in_any_44_camera_frustum'])))
pairs=json.loads((r/'lpips_pairs/pairs.json').read_text());res=json.loads((r/'evaluation/lpips_results.json').read_text());final=json.loads((r/'evaluation/comparison_final.json').read_text());assert len(pairs)==len(res['pairs'])==26;assert sha(r/'lpips_pairs/pairs.json')==res['pair_manifest_sha256'];keys=lambda p:(p['method'],p['frame_id'],p['split']);assert len(set(map(keys,pairs)))==26;bykey={keys(p):p for p in res['pairs']};checks=[];resize_methods={}
for p in pairs:
 record=bykey[keys(p)];assert all(record[k]==p[k] for k in p);source=r/'lpips_pairs'/p['source'];render=r/'lpips_pairs'/p['render'];assert sha(source)==p['source_sha256'];assert sha(render)==p['render_sha256'];manifest=json.loads((r/'evaluation'/p['method']/'render_manifest.json').read_text());rr=next(x for x in manifest if x['frame_id']==p['frame_id']);assert sha(Path(rr['render']))==p['render_sha256'];v=viewmap[p['frame_id']];assert v['role']==p['split'];original=Image.open(v['path']).convert('RGB');img=np.array(Image.open(source));matched=[]
 for name,mode in [('nearest',Image.Resampling.NEAREST),('bilinear',Image.Resampling.BILINEAR),('bicubic',Image.Resampling.BICUBIC),('lanczos',Image.Resampling.LANCZOS)]:
  if np.array_equal(np.array(original.resize((img.shape[1],img.shape[0]),mode)),img):matched.append(name)
 assert matched,(p['frame_id'],'no source-resize match');assert sha(Path(v['path']))==v['sha256'];checks.append(dict(method=p['method'],frame_id=p['frame_id'],split=p['split'],source_hash_verified=True,render_hash_verified=True,source_resize=matched,value=record['lpips_alex_v01']))
means={}
for method in ['OURS','AWSM']:
 means[method]={}
 for role in ['reconstruction','heldout']:
  ps=[p for p in res['pairs'] if p['method']==method and p['split']==role];means[method][role]=dict(count=len(ps),mean=float(np.mean([p['lpips_alex_v01'] for p in ps])),frame_ids=[p['frame_id'] for p in ps]);assert len(ps)==(5 if role=='reconstruction' else 8)
  if role=='heldout':assert {p['frame_id'] for p in ps}=={v['frame_id'] for v in views if v['role']=='heldout'}
 summary=next(x for x in final['methods'] if x['id']==method);print('FINAL_KEYS',method,summary.keys());print('appearance_means',summary.get('appearance_means'))
result=dict(status='PASS',pair_count=26,paired_hash_and_identity_checks=checks,means=means,identical_image_sanity=res['identical_image_sanity'],weight_provenance=res['weights'],scope='Recomputed aggregation and byte/pixel input integrity for all26pairs; neural LPIPS inference itself not rerun in this audit. Original source resize matches PIL Lanczos/Bicubic as recorded per pair.');(out/'lpips_integrity.json').write_text(json.dumps(result,indent=2));print('LPIPS',json.dumps(means))
