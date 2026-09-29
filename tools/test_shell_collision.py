"""Canonical shell regression without Blender/MuJoCo; historical input is read-only."""
import json
import math
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'workflow'))
from r2s.shell_collision import SURFACES,shell_boxes,box_in_entity_frame

historical=json.loads((ROOT/'examples/independent_whole_scene_20260926/authoring/room.json').read_text())
room=dict(historical['room'])
window=historical['window']
room['openings']=[dict(wall='wall_left',bounds=[window['y0'],window['y1'],window['bottom'],window['top']])]
back=shell_boxes(room,'wall_back')
assert len(back)==1
assert abs(back[0]['position'][1]-back[0]['dimensions'][1]/2-room['y_max'])<1e-12
# Reproduces the old skirt-expanded envelope: its front is 25 mm too far inside.
entity=dict(root_position=[0,0,0],root_quaternion_wxyz=[1,0,0,0],
            local_aabb=[[room['x_min'],room['y_max']-.025,0],
                        [room['x_max'],room['y_max']+.12,room['height']]])
assert abs(entity['local_aabb'][0][1]-room['y_max'])>.006
assert np.allclose(box_in_entity_frame(back[0],entity)[0],back[0]['position'])
left=shell_boxes(room,'wall_left')
hole_area=(window['y1']-window['y0'])*(window['top']-window['bottom'])
expected=((room['y_max']-room['y_min'])*room['height']-hole_area)*room['thickness']
assert math.isclose(sum(np.prod(b['dimensions']) for b in left),expected,abs_tol=1e-12)
for b in left:
    y,z=b['position'][1:];dy,dz=b['dimensions'][1:]
    assert not (min(y+dy/2,window['y1'])>max(y-dy/2,window['y0'])+1e-12 and
                min(z+dz/2,window['top'])>max(z-dz/2,window['bottom'])+1e-12)

# Arbitrary non-Z root rotation and a yawed explicit world box round-trip.
def multiply(a,b):
    aw,av=a[0],np.array(a[1:]);bw,bv=b[0],np.array(b[1:])
    return np.r_[aw*bw-np.dot(av,bv),aw*bv+bw*av+np.cross(av,bv)]
q=np.array([.7,.2,-.3,.4]);q/=np.linalg.norm(q)
entity=dict(root_position=[2,-3,1],root_quaternion_wxyz=q.tolist())
proxy=dict(position=[1,2,3],dimensions=[.1,2,3],yaw=.6)
pos,local_q=box_in_entity_frame(proxy,entity)
recovered=multiply(multiply(q,[0,*pos]),q*np.array([1,-1,-1,-1]))[1:]+entity['root_position']
assert np.allclose(recovered,proxy['position'])
assert np.allclose(multiply(q,local_q),[math.cos(.3),0,0,math.sin(.3)])

simple=dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3,thickness=.1)
simple['openings']=[dict(wall='wall_front',bounds=[0,1,1,2]),dict(wall='wall_front',bounds=[.5,1.5,1.5,2.5])]
assert math.isclose(sum(np.prod(b['dimensions']) for b in shell_boxes(simple,'wall_front')),(12-1.75)*.1)
for bad in ([0,3,1,2],[1,0,1,2],[0,1,-1,2],[0,float('nan'),1,2]):
    simple['openings']=[dict(wall='wall_left',bounds=bad)]
    try:shell_boxes(simple,'wall_left')
    except ValueError:pass
    else:raise AssertionError('Invalid aperture accepted')
simple['openings']=[]
for unsupported in [dict(shape='box',position=[0,2.05,2.96],dimensions=[.02,.1,.02]),
                    dict(shape='box',position=[0,2.025,1.5],dimensions=[4,.1,3])]:
    simple['collision_proxies']={'wall_back':[unsupported]}
    try:shell_boxes(simple,'wall_back')
    except ValueError as exc:assert 'room.collision_proxies is unsupported' in str(exc)
    else:raise AssertionError('Tiny or shifted wall override was accepted')
print('SHELL_COLLISION_HISTORICAL_TRIM_OPENINGS_AND_FRAME_OK')
print('ARBITRARY_ROOM_PROXIES_REJECTED_PENDING_COVERAGE_VALIDATION_OK')
