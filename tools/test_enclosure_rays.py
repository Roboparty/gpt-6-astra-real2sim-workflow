"""Real MuJoCo regression: window trim must not masquerade as a missing wall."""
import sys
from pathlib import Path
import numpy as np
import mujoco
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.simulation_checks import check_enclosure_rays
room=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3)
parts=[('floor','0 0 -.05','2 2 .05'),('ceiling','0 0 3.05','2 2 .05'),('wall_left','-2.05 0 1.5','.05 2 1.5'),('wall_right','2.05 0 1.5','.05 2 1.5'),('wall_front','0 -2.05 1.5','2 .05 1.5'),('wall_back','0 2.05 1.5','2 .05 1.5'),('window_trim','-1.975 0 2.96','.02 .4 .04')]
def load(rows):
 xml='<mujoco><worldbody>'+''.join(f'<body name="{n}" pos="{p}"><geom type="box" size="{s}" group="2"/></body>' for n,p,s in rows)+'</worldbody></mujoco>'
 m=mujoco.MjModel.from_xml_string(xml);d=mujoco.MjData(m);mujoco.mj_forward(m,d);return m,d
m,d=load(parts);rid=np.zeros(1,np.int32);distance=mujoco.mj_ray(m,d,np.array([-1.95,0,2.96]),np.array([-1.,0,0]),np.array([0,0,1,0,0,0],np.uint8),True,-1,rid)
assert abs(distance-.05)>.006,'Fixture must reproduce old fixed-ray failure'
result=check_enclosure_rays(m,d,room,[.8,.8]);assert len(result)==6 and result['left']['rejected_candidate_count']>0 and result['left']['hit_body']=='wall_left'
m,d=load([row for row in parts if row[0]!='wall_right'])
try:check_enclosure_rays(m,d,room,[.8,.8])
except ValueError as exc:assert 'wall_right' in str(exc)
else:raise AssertionError('Missing wall was accepted')
print('ENCLOSURE_RAYS_OCCLUSION_AND_MISSING_WALL_OK')
