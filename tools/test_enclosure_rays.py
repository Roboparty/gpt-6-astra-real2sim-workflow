"""Real MuJoCo regression: window trim must not masquerade as a missing wall."""
import sys
from pathlib import Path
import numpy as np
import mujoco
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.simulation_checks import check_enclosure_rays,check_opening_rays
from r2s.shell_collision import SURFACES,shell_boxes,box_in_entity_frame
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

# Canonical collision export survives the historical 25 mm skirt envelope.
import json
from xml.etree.ElementTree import Element,SubElement,tostring
historical=json.loads((Path(__file__).resolve().parents[1]/'examples/independent_whole_scene_20260926/authoring/room.json').read_text())
room=dict(historical['room']);w=historical['window']
room['openings']=[dict(wall='wall_left',bounds=[w['y0'],w['y1'],w['bottom'],w['top']])]
def canonical_model(fill_opening=False,back_offset=0):
    root=Element('mujoco');world=SubElement(root,'worldbody')
    # Nonidentity body rotations expose wrong world/local export conventions.
    entity=dict(root_position=[.3,-.6,.2],root_quaternion_wxyz=[.5,.5,.5,.5])
    for surface in SURFACES:
        body=SubElement(world,'body',name=surface,pos=' '.join(map(str,entity['root_position'])),quat=' '.join(map(str,entity['root_quaternion_wxyz'])))
        boxes=shell_boxes(dict(room,openings=[]) if fill_opening else room,surface)
        for proxy in boxes:
            if surface=='wall_back':proxy['position'][1]+=back_offset
            pos,quat=box_in_entity_frame(proxy,entity)
            SubElement(body,'geom',type='box',pos=' '.join(map(str,pos)),quat=' '.join(map(str,quat)),size=' '.join(str(v/2) for v in proxy['dimensions']),group='2')
    m=mujoco.MjModel.from_xml_string(tostring(root,encoding='unicode'));d=mujoco.MjData(m);mujoco.mj_forward(m,d)
    return m,d
m,d=canonical_model();result=check_enclosure_rays(m,d,room,[1,0]);assert len(result)==6
assert result['back']['error_m']<1e-10
groups=m.geom_group.copy();assert len(check_opening_rays(m,d,room))==1;assert np.array_equal(groups,m.geom_group)
m,d=canonical_model(fill_opening=True);groups=m.geom_group.copy()
try:check_opening_rays(m,d,room)
except ValueError as exc:assert 'fills declared opening' in str(exc)
else:raise AssertionError('A filled window was accepted')
assert np.array_equal(groups,m.geom_group),'Opening failure must restore model metadata'
m,d=canonical_model(back_offset=-.025)
try:check_enclosure_rays(m,d,room,[1,0])
except ValueError as exc:assert 'wall_back' in str(exc)
else:raise AssertionError('A 25 mm incorrect wall plane was accepted')
print('CANONICAL_SHELL_6MM_GATE_AND_FILLED_WINDOW_NEGATIVE_OK')

# Unsupported tiny or shifted wall overrides fail before reaching the simulator.
room['openings'].append(dict(wall='wall_back',bounds=[-.5,.5,1,2]))
bad_proxies=shell_boxes(room,'wall_back')
for proxy in bad_proxies:proxy['position'][1]-=.025
tiny=[dict(shape='box',position=[0,room['y_max']+room['thickness']/2,room['height']-.04],dimensions=[.02,room['thickness'],.02])]
for unsupported in (bad_proxies,tiny):
    room['collision_proxies']={'wall_back':unsupported}
    try:canonical_model()
    except ValueError as exc:assert 'room.collision_proxies is unsupported' in str(exc)
    else:raise AssertionError('Unvalidated explicit room collision proxies were accepted')
del room['collision_proxies']
# Aperture-aware candidate rays still use the fixed canonical normal coordinate.
m,d=canonical_model(back_offset=-.025)
try:check_enclosure_rays(m,d,room,[1,0])
except ValueError as exc:assert 'wall_back' in str(exc)
else:raise AssertionError('Wrong wall with an aperture moved its own validation origin')
print('ROOM_OVERRIDE_REJECTION_AND_APERTURE_6MM_GATE_OK')
