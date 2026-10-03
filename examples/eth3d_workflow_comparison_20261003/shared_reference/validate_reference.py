from pathlib import Path
import numpy as np,json,hashlib
r=Path(__file__).resolve().parent/'shared';m=json.loads((r/'manifest.json').read_text());fs=json.loads((r/'frames.json').read_text())['frames'];summary=[]
assert len(m['frames'])==len(fs)==36
for rec in m['frames']:
 i=rec['sample_index'];p=r/rec['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256']
 with np.load(p) as z:
  d=z['depth_z_m'];v=z['valid_mask'];c=z['confidence'];cv=z['confidence_valid_mask'];T=z['T_world_camera'];k=z['K_depth'];kr=z['K_depth_raster'];H,W=d.shape
  assert d.shape==v.shape==c.shape==cv.shape and z['processed_rgb'].shape==(H,W,3)
  assert np.isfinite(d).all() and np.isfinite(c).all() and np.all(d[v]>0) and np.all(d[~v]==0)
  assert np.allclose(T,fs[i]['T_world_camera'],atol=1e-6) and np.allclose(T@z['input_world_to_camera'],np.eye(4),atol=1e-5)
  assert np.allclose(kr[:2,2]-k[:2,2],.5,atol=1e-5)
  assert np.allclose(kr,np.diag([W/fs[i]['image_size'][0],H/fs[i]['image_size'][1],1])@np.array(fs[i]['K_raster']),atol=1e-4)
  summary.append({'index':i,'shape':[H,W],'valid_pixels':int(v.sum()),'total_pixels':v.size,'median_depth_m':float(np.median(d[v]))})
a={'status':'PASS','checks':'36 input/output identities, hashes, finite masked depth and confidence, exact K resize and half-pixel conversion, input camera inversion, processed RGB alignment','records':summary,'manifest_sha256':hashlib.sha256((r/'manifest.json').read_bytes()).hexdigest()}
(r.parent/'validation.json').write_text(json.dumps(a,indent=2));print(json.dumps(a))
