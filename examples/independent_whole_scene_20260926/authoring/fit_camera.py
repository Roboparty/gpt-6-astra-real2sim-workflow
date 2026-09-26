import json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');out=Path(w.state['stages']['agent_calibrate']['directory'])
obs=json.loads((Path(w.state['stages']['agent_observe']['directory'])/'furniture_observation.json').read_text())
uv=np.array([o['uv'] for t in obs['targets'] for o in t['observations']])
names=[o['id'] for t in obs['targets'] for o in t['observations']]
# Parameters: camera position/rotation, focal; bed width, rail top, head top;
# wardrobe left x/front y; cabinet front x/far y/width/height.
def pts(v):
 bw,bz,hz,wx,wy,sx,sy,sw,sh=v[7:]
 return np.array([[-bw/2,0,bz],[bw/2,0,bz],[-bw/2,0,0],[bw/2,0,0],[-bw/2,2,hz],[bw/2,2,hz],
 [wx,wy,2.01],[wx+.794,wy,2.01],[wx,wy,0],[wx+.794,wy,0],
 [sx,sy,sh],[sx,sy,0],[sx,sy-.25,sh-.15],[sx,sy-.25,.09]])
def project(v,points):
 q=(points-v[:3])@Rotation.from_rotvec(v[3:6]).as_matrix().T
 return q[:,:2]/q[:,2:3]*v[6]+[851,638]
def residual(v):
 p=project(v,pts(v));return np.r_[(p-uv).ravel(),(v[7]-1.2)*15,(v[8]-.42)*12,(v[9]-.99)*8,(v[11]-1.52)*5]
def look(C,T):
 z=np.array(T)-C;z=z/np.linalg.norm(z);x=np.cross(z,[0,0,1]);x=x/np.linalg.norm(x);y=np.cross(z,x);return Rotation.from_matrix(np.array([x,y,z])).as_rotvec()
initial=np.r_[[2.5,-3.7,1.65],look(np.array([2.5,-3.7,1.65]),[0,1,1.1]),1000,1.2,.42,1.0,1.0,1.5,-.8,.0,1.2,1.2]
lo=[.05,-7,1.0,-3.2,-3.2,-3.2,550,.8,.28,.75,.65,.6,-2.0,-.5,.8,.8]
hi=[4,-1.1,2.2,3.2,3.2,3.2,1600,1.6,.6,1.3,2.5,2.2,-.5,1.1,1.6,1.6]
solutions=[]
for f in [750,1000,1250]:
 a=initial.copy();a[6]=f;sol=least_squares(residual,a,bounds=(lo,hi),max_nfev=3500,ftol=1e-11,xtol=1e-11,gtol=1e-11);solutions.append(sol)
best=min(solutions,key=lambda x:np.linalg.norm(residual(x.x)));v=best.x;p=pts(v);proj=project(v,p);errors=np.linalg.norm(proj-uv,axis=1)
cam=dict(position=v[:3].tolist(),rotation_world_to_cv=Rotation.from_rotvec(v[3:6]).as_matrix().tolist(),focal_px=float(v[6]),principal_point=[851,638],image_size=[1702,1276],role='reconstruction')
params=dict(bed_width=float(v[7]),bed_rail_top=float(v[8]),bed_head_top=float(v[9]),wardrobe_left_x=float(v[10]),wardrobe_front_y=float(v[11]),cabinet_front_x=float(v[12]),cabinet_far_y=float(v[13]),cabinet_width=float(v[14]),cabinet_height=float(v[15]))
rows=[dict(id=n,world=x.tolist(),uv=u.tolist(),projected=q.tolist(),error_px=float(e)) for n,x,u,q,e in zip(names,p,uv,proj,errors)]
data=dict(camera=cam,parameters=params,correspondences=rows,residuals=dict(median_px=float(np.median(errors)),max_px=float(max(errors))),solutions=[dict(focal_px=float(x.x[6]),residual_norm=float(np.linalg.norm(residual(x.x)))) for x in solutions],coordinate_system='metres, Z up; bed foot center at origin, head towards +Y; +X towards wardrobe',priors=['bed longitudinal rail 2.0m user confirmed','wardrobe BRUKSVARA dimensions conditional candidate'],uncertainty=['Principal point fixed to image center; no EXIF lens prior','No radial distortion fitted','All points are reconstruction observations, not held out','Shoe cabinet dimensions free estimates','Visible furniture residuals do not certify silhouettes or hidden geometry'])
atomic_json(out/'calibration.json',data);atomic_json(R/'authoring/fit.json',data)
im=Image.open(R/'input/01_bedroom.jpg').convert('RGB');d=ImageDraw.Draw(im)
for a,b in zip(uv,proj):d.ellipse((a[0]-5,a[1]-5,a[0]+5,a[1]+5),outline='lime',width=2);d.line([tuple(a),tuple(b)],fill='red',width=2);d.ellipse((b[0]-4,b[1]-4,b[0]+4,b[1]+4),outline='red',width=2)
im.save(out/'fit_overlay.jpg');print(json.dumps(data,indent=2))
