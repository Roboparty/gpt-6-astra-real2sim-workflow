import sys,json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
src=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);results=[]
variants=[(.003,.0005,'discrete'),(0,.0005,'Euler'),(0,.0001,'Euler'),(.00001,.0001,'Euler'),(.0001,.0001,'discrete'),(.00001,.00002,'Euler')]
for damping,dt,integrator in variants:
 root=ET.parse(src).getroot();root.find('compiler').set('meshdir',str(src.parent/'meshes'));option=root.find('option');option.set('timestep',str(dt));option.set('integrator',integrator)
 for node in root.findall('.//flexcomp/elasticity'):node.set('damping',str(damping))
 m=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'));m.opt.disableflags|=int(mujoco.mjtDisableBit.mjDSBL_CONTACT);d=mujoco.MjData(m);mujoco.mj_forward(m,d);initial=d.flexvert_xpos.copy();warning=d.warning.number.copy();acc=0;displacement=0;initial_acc=float(max(abs(d.qacc)))
 for i in range(200):
  mujoco.mj_step(m,d);acc=max(acc,float(max(abs(d.qacc))));displacement=max(displacement,float(np.max(np.linalg.norm(d.flexvert_xpos-initial,axis=1))))
  if any(d.warning.number-warning):break
 rec=dict(damping=damping,dt=dt,integrator=integrator,contacts_disabled_for_diagnosis_only=True,initial_qacc=initial_acc,steps=i+1,warnings=(d.warning.number-warning).tolist(),max_qacc=acc,max_displacement=displacement);results.append(rec);print(json.dumps(rec),flush=True)
out.write_text(json.dumps(results,indent=2))
