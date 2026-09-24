import sys,json,math
from pathlib import Path
import numpy as np
import mujoco
src=Path(sys.argv[1]).resolve();m=mujoco.MjModel.from_xml_path(str(src));d=mujoco.MjData(m);mujoco.mj_forward(m,d)
def info(name):
 fid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_FLEX,name);return int(m.flex_vertadr[fid]),int(m.flex_vertnum[fid])
ss,sn=info('chair_pad_volume');cs,cn=info('red_garment_cloth');v=d.flexvert_xpos.copy();top=np.flatnonzero(v[ss:ss+sn,2]>v[ss:ss+sn,2].max()-.001)+ss;cloth=[i for i in range(cs,cs+cn) if m.body_dofnum[m.flex_vertbodyid[i]]>0];jid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_JOINT,'right_door_hinge');dof=int(m.jnt_dofadr[jid]);peaks={};angles=[0.,0.]
for step in range(4000):
 t=float(d.time);d.qfrc_applied[:]=0;d.xfrc_applied[:]=0;d.qfrc_applied[dof]=8 if t<1.3 else 0;wind=.12*math.sin(math.pi*min(t/.7,1)) if t<.7 else 0;load=300*min(t/.35,1) if t<.8 else 300*max(0,1-(t-.8)/.35)
 for i in cloth:d.xfrc_applied[m.flex_vertbodyid[i],1]-=wind/len(cloth)
 for i in top:d.xfrc_applied[m.flex_vertbodyid[i],2]-=load/len(top)
 mujoco.mj_step(m,d);q=float(d.qpos[m.jnt_qposadr[jid]]);angles=[min(angles[0],q),max(angles[1],q)]
 for i in range(d.ncon):
  c=d.contact[i];names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) if int(g)>=0 else 'flex' for g in c.geom];flex=list(map(int,c.flex)) if hasattr(c,'flex') else [];key=str(names)+str(flex)
  if key not in peaks or c.dist<peaks[key]['distance_m']:peaks[key]=dict(geoms=names,flex_ids=flex,distance_m=float(c.dist),time=float(d.time),position=list(map(float,c.pos)))
report=dict(hinge_range=angles,warnings=d.warning.number.tolist(),contacts=sorted(peaks.values(),key=lambda p:p['distance_m']));Path(sys.argv[2]).write_text(json.dumps(report,indent=2));print(json.dumps(dict(hinge_range=angles,worst_contacts=report['contacts'][:12]),indent=2))
