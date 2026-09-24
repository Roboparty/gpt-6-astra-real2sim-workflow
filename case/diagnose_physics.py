import sys,json
from pathlib import Path
import numpy as np
import mujoco
src=Path(sys.argv[1]);out=Path(sys.argv[2]);results=[]
for label,dt,disable_contact in [('original',.0005,False),('no_contact',.0005,True),('small_dt',.0001,False),('small_dt_no_contact',.0001,True)]:
 m=mujoco.MjModel.from_xml_path(str(src));m.opt.timestep=dt
 if disable_contact:m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
 d=mujoco.MjData(m);mujoco.mj_forward(m,d);initial=d.flexvert_xpos.copy();contacts=[]
 for c in sorted(d.contact,key=lambda c:c.dist)[:15]:
  names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) if int(g)>=0 else 'flex' for g in c.geom];contacts.append(dict(distance=float(c.dist),geoms=names))
 checks=[]
 for fid in range(m.nflex):
  a=int(m.flex_vertadr[fid]);n=int(m.flex_vertnum[fid]);checks.append(dict(id=mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_FLEX,fid),start=a,count=n))
 warning=d.warning.number.copy();maxacc=0
 for step in range(100):
  mujoco.mj_step(m,d);maxacc=max(maxacc,float(np.max(abs(d.qacc))))
  if any(d.warning.number-warning):break
 for c in checks:c['displacement']=float(np.max(np.linalg.norm(d.flexvert_xpos[c['start']:c['start']+c['count']]-initial[c['start']:c['start']+c['count']],axis=1)))
 result=dict(label=label,dt=dt,disable_contact=disable_contact,steps=step+1,warnings=(d.warning.number-warning).tolist(),maximum_qacc=maxacc,first_dof_body=mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,int(m.dof_bodyid[0])),initial_contacts=contacts,flex_displacements=checks);results.append(result);print(json.dumps(result),flush=True)
out.write_text(json.dumps(results,indent=2))
