import json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
R=Path('/home/wqz/real2sim_whole_scene_20260926');f=json.loads((R/'authoring/fit.json').read_text());c=f['camera'];p=f['parameters'];C=np.array(c['position']);M=np.array(c['rotation_world_to_cv']);uv=np.array([r['uv'] for r in f['correspondences'][:6]])
def points(v):
 x,y,a,bw,bz,hz,footin=v
 q=np.array([[-bw/2,0,bz],[bw/2,0,bz],[-bw/2,footin,0],[bw/2,footin,0],[-bw/2,2,hz],[bw/2,2,hz]])
 q[:,:2]=q[:,:2]@np.array([[np.cos(a),np.sin(a)],[-np.sin(a),np.cos(a)]])+[x,y];return q
def loss(v):
 q=(points(v)-C)@M.T;return np.r_[(q[:,:2]/q[:,2:3]*c['focal_px']+[851,638]-uv).ravel(),v[2]*15,v[6]*15]
v=least_squares(loss,[0,0,0,p['bed_width'],p['bed_rail_top'],p['bed_head_top'],.025],bounds=([-.1,-.1,-.1,.95,.25,.75,-.015],[.1,.1,.1,1.3,.45,1.05,.065])).x
print(v.tolist(),np.linalg.norm(loss(v)[:12].reshape(-1,2),axis=1).tolist());(R/'authoring/bed_revision.json').write_text(json.dumps(dict(parameters=v.tolist(),meaning=['origin_x','origin_y','yaw','width','rail_top','head_top','foot_inset_y'],world_points=points(v).tolist(),residual_px=np.linalg.norm(loss(v)[:12].reshape(-1,2),axis=1).tolist(),source='same accepted six original bed points, fixed camera, 2m longitudinal frame preserved'),indent=2))
