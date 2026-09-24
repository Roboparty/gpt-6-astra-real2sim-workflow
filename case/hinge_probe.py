import sys,json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
src=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);records=[]
for label in ['original','exclude_floor','exclude_frame','parent_frame','clearance','clearance_parent']:
 root=ET.parse(src).getroot();root.find('compiler').set('meshdir',str(src.parent/'meshes'));world=root.find('worldbody');door=root.find(".//body[@name='door_leaf']");frame=root.find(".//body[@name='door_frame']")
 if label.startswith('exclude_'):
  contact=ET.SubElement(root,'contact');ET.SubElement(contact,'exclude',body1='door_leaf',body2='floor' if label=='exclude_floor' else 'door_frame')
 if 'parent' in label:world.remove(door);frame.append(door)
 if label.startswith('clearance'):
  g=door.find("geom[@name='door_leaf_agent_collision0']");g.set('pos','4.08 -2.25 1.095');g.set('size','.0045 .42 1.08')
  for name in ['door_leaf_agent_collision1','door_leaf_agent_collision2']:door.find("geom[@name='"+name+"']").set('size','.006')
 m=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'));d=mujoco.MjData(m);mujoco.mj_forward(m,d);jid=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_JOINT,'right_door_hinge');dof=int(m.jnt_dofadr[jid]);pairs=[]
 for i in range(d.ncon):
  c=d.contact[i];names=[mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_GEOM,int(g)) if int(g)>=0 else 'flex' for g in c.geom]
  if any('door_leaf' in (name or '') for name in names):pairs.append(dict(distance=float(c.dist),geoms=names))
 warnings=d.warning.number.copy()
 for i in range(600):d.qfrc_applied[:]=0;d.qfrc_applied[dof]=3;mujoco.mj_step(m,d)
 rec=dict(label=label,time=float(d.time),angle_rad=float(d.qpos[m.jnt_qposadr[jid]]),initial_door_contacts=sorted(pairs,key=lambda p:p['distance'])[:12],warnings=(d.warning.number-warnings).tolist(),scope='diagnostic only; exclusions are not final physics settings');records.append(rec);print(json.dumps(rec),flush=True)
out.write_text(json.dumps(records,indent=2))
