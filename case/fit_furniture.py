"""Fit whole rigid furniture frames to explicitly owned source observations.
No independently backprojected leg/rail points and no post-fit foot averaging.
This is a case recipe, not a new-photo reconstruction system.
"""
import json,hashlib,math
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
root=Path(__file__).resolve().parents[1]
obs=json.loads((root/'case/furniture_observation.json').read_text());cal=json.loads((root/'case/calibration_initial.json').read_text())
C=np.array(cal['position']);R=np.array(cal['rotation_world_to_cv']);F=cal['focal_px'];PP=np.array(cal['principal_point'])
def project(p):
 q=(np.asarray(p)-C)@R.T;return q[...,:2]/q[...,2,None]*F+PP
def world(p,x,y,a):
 p=np.array(p,dtype=float);rot=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);p[...,:2]=p[...,:2]@rot.T+[x,y];return p
def table_landmarks(p):
 x,y,a,w,l,h=p;sg=[(-1,-1),(-1,1),(1,1),(1,-1)];out={}
 for i,(sx,sy) in enumerate(sg):
  out['top_'+str(i)]=world([sx*w/2,sy*l/2,h],x,y,a)
  out['foot_'+str(i)]=world([sx*w*.43,sy*l*.43,.002],x,y,a)
 return out
def chair_landmarks(p,far=False):
 x,y,a,w,d,h,bh=p;sg=([(-1,1),(1,1),(1,-1),(-1,-1)] if far else [(1,-1),(-1,-1),(-1,1),(1,1)]);out={}
 for i,(sx,sy) in enumerate(sg):
  out['seat_'+str(i)]=world([sx*(w/2-.004),(-d/2+.004 if sy<0 else d/2-.035),h],x,y,a)
  out['foot_'+str(i)]=world([sx*(w/2-.020),sy*(d/2-.020),.002],x,y,a)
  if sy>0:out['back_post_'+str(i)]=world([sx*(w/2-.035),d/2-.012,bh-.012],x,y,a)
 return out
def residual(points,target):return [(points[v['landmark']][i]-v['uv'][i])/v['sigma_px'] for v in target['observations'] for i in [0,1]]
t,n,f=obs['targets']
def tres(p):return residual({k:project(v) for k,v in table_landmarks(p).items()},t)+[(p[5]-.79)/.13]
tf=least_squares(tres,[1.45,-.87,-.1,.7,1.15,.8],bounds=([.7,-1.5,-.7,.5,.7,.65],[2,-.2,.6,1.0,1.7,.9]),max_nfev=4000)
# Shared shape, separate poses; the family assumption is explicitly declared.
def split(p):return np.r_[p[:3],p[6:]],np.r_[p[3:6],p[6:]]
def cres(p):
 pn,pf=split(p)
 return residual({k:project(v) for k,v in chair_landmarks(pn).items()},n)+residual({k:project(v) for k,v in chair_landmarks(pf,True).items()},f)+[(p[6]-.40)/.09,(p[7]-.42)/.09,(p[8]-.46)/.07,(p[9]-.72)/.10]
cf=least_squares(cres,[1.75,-.65,-1.57,.72,-.49,1.57,.40,.43,.46,.72],bounds=([1.3,-1.2,-2.2,.3,-1.2,.8,.3,.3,.39,.62],[2.3,-.1,-.8,1.2,.1,2.3,.55,.55,.54,.9]),max_nfev=4000)
pn,pf=split(cf.x);data={}
for target,p,fn in [(t,tf.x,table_landmarks),(n,pn,chair_landmarks),(f,pf,lambda p:chair_landmarks(p,True))]:
 lm=fn(p);rows=[dict(v,world=lm[v['landmark']].tolist(),projected=project(lm[v['landmark']]).tolist(),error_px=float(np.linalg.norm(project(lm[v['landmark']])-v['uv']))) for v in target['observations']];err=[v['error_px'] for v in rows]
 data[target['entity']]=dict(parameters=p.tolist(),parameter_names=['x_m','y_m','yaw_rad','width_m','length_m','height_m'] if target is t else ['x_m','y_m','yaw_rad','width_m','depth_m','seat_top_m','back_top_m'],observation_ids=[v['id'] for v in rows],landmarks=rows,median_error_px=float(np.median(err)),max_error_px=max(err),uncertainty=target['uncertain'])
result=dict(schema='real2sim.furniture-fit/1',source_observation='case/furniture_observation.json',source_observation_sha256=hashlib.sha256((root/'case/furniture_observation.json').read_bytes()).hexdigest(),calibration_sha256=hashlib.sha256((root/'case/calibration_initial.json').read_bytes()).hexdigest(),model_version=4,method='joint rigid rectangle and assembly fit, shared chair dimensions, floor constraints; fitting points only',targets=data,independent_accuracy=False)
(root/'case/furniture_parameters.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
