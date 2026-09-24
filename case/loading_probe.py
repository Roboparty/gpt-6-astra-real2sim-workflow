import sys,json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
src=Path(sys.argv[1]).resolve();scene=json.loads((src.parent/'scene.json').read_text());definition=next(x for x in scene['dynamics']['deformables'] if x['kind']=='soft_body');elems=np.array(definition['elements'],int);records=[]
for E,loadmax in [(20000,0),(20000,10),(20000,50),(20000,300),(100000,300),(200000,300)]:
 root=ET.parse(src).getroot();root.find('compiler').set('meshdir',str(src.parent/'meshes'));root.find(".//flexcomp[@name='chair_pad_volume']/elasticity").set('young',str(E));m=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'));d=mujoco.MjData(m);mujoco.mj_forward(m,d);fid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_FLEX,'chair_pad_volume');start=int(m.flex_vertadr[fid]);count=int(m.flex_vertnum[fid]);initial=d.flexvert_xpos[start:start+count].copy();p=initial[elems];vol0=np.linalg.det(np.stack([p[:,1]-p[:,0],p[:,2]-p[:,0],p[:,3]-p[:,0]],axis=2))/6;ids=np.flatnonzero(initial[:,2]>initial[:,2].max()-.001)+start;warn=d.warning.number.copy();mins=1;disp=0;steps=[]
 if '--trim-legs' in sys.argv:
  for g in root.findall('.//geom'):
   if g.get('name','').startswith('chair_near_agent_collision') and g.get('type')=='capsule':
    pts=np.fromstring(g.get('fromto'),sep=' ').reshape(2,3);axis=(pts[1]-pts[0]);axis/=np.linalg.norm(axis);pts[0]+=.0115*axis;pts[1]-=.0115*axis;g.set('fromto',' '.join(map(str,pts.ravel())));g.set('size','.0115')
  m=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'));d=mujoco.MjData(m);mujoco.mj_forward(m,d);fid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_FLEX,'chair_pad_volume');start=int(m.flex_vertadr[fid]);count=int(m.flex_vertnum[fid]);initial=d.flexvert_xpos[start:start+count].copy();p=initial[elems];vol0=np.linalg.det(np.stack([p[:,1]-p[:,0],p[:,2]-p[:,0],p[:,3]-p[:,0]],axis=2))/6;ids=np.flatnonzero(initial[:,2]>initial[:,2].max()-.001)+start;warn=d.warning.number.copy()
 for step in range(1000):
  d.xfrc_applied[:]=0;force=loadmax*min(d.time/.35,1)
  for vi in ids:d.xfrc_applied[m.flex_vertbodyid[vi],2]-=force/len(ids)
  mujoco.mj_step(m,d)
  if step%25==0:
   p=d.flexvert_xpos[start:start+count][elems];vol=np.linalg.det(np.stack([p[:,1]-p[:,0],p[:,2]-p[:,0],p[:,3]-p[:,0]],axis=2))/6;ratio=float(np.min(vol/vol0));mins=min(mins,ratio);disp=max(disp,float(np.max(np.linalg.norm(d.flexvert_xpos[start:start+count]-initial,axis=1))));steps.append(dict(time=float(d.time),force_N=float(force),volume_ratio=ratio))
   if ratio<.05:break
  if any(d.warning.number-warn):break
 rec=dict(young_pa=E,load_max_N=loadmax,trimmed_leg_collision_ends='--trim-legs' in sys.argv,steps=step+1,minimum_volume_ratio=mins,max_displacement=disp,warnings=(d.warning.number-warn).tolist(),top_vertices=len(ids),top_unique_bodies=len(set(int(m.flex_vertbodyid[i]) for i in ids)),dynamic_body_mass_sum=float(sum(m.body_mass[int(m.flex_vertbodyid[i])] for i in range(start,start+count) if m.body_dofnum[int(m.flex_vertbodyid[i])]>0)),trace=steps);records.append(rec);print(json.dumps({k:v for k,v in rec.items() if k!='trace'}),flush=True)
Path(sys.argv[2]).write_text(json.dumps(records,indent=2))
