import sys,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow'))
from r2s.core import Workflow,atomic_json
w=Workflow(R/'case');out=Path(w.state['stages']['agent_calibrate']['directory']);fit=json.loads((out/'calibration.json').read_text())
shutil.copyfile(R/'authoring/fit_camera.py',out/'fit_camera.py')
atomic_json(out/'response.json',dict(status='complete',artifacts=['calibration.json','fit_overlay.jpg','fit_camera.py'],evidence=['fit_overlay.jpg','14 original hand-observed points; three focal initializations converge'],reasoning_summary='Initial constrained pinhole estimate. Residuals reported honestly; geometry gate must still check bed supports and cabinet silhouette. Camera and catalogue assumptions are fitting priors, not independent validation.'))
print(w.accept('agent_calibrate',out/'response.json'));print(w.run())
out=Path(w.state['stages']['agent_calibrate_room']['directory']);c=fit['camera'];C=np.array(c['position']);rot=np.array(c['rotation_world_to_cv'])
def ray(u,v):return rot.T@np.array([(u-851)/c['focal_px'],(v-638)/c['focal_px'],1])
def plane(u,v,axis,value):
 d=ray(u,v);return C+d*((value-C[axis])/d[axis])
yb=fit['parameters']['wardrobe_front_y']+.565+.045
corner=plane(908,315,1,yb);xl=float(corner[0]);h=float(corner[2]);xr=2.6;yf=-2.2
room=dict(x_min=xl,x_max=xr,y_min=yf,y_max=yb,height=h,thickness=.12,preserve_full_shell=True)
# Ray intersections constrain each observed edge to its own physically coherent plane.
window_y0=float(plane(294,92,0,xl)[1]);window_y1=float(plane(837,295,0,xl)[1]);window_bottom=float(plane(831,727,0,xl)[2])
blinds=[]
for u0,v0,u1,v1,ub,vb in [(300,96,518,179,430,531),(525,181,744,258,635,504),(748,260,837,295,790,508)]:
 a=plane(u0,v0,0,xl+.03);b=plane(u1,v1,0,xl+.03);z=plane(ub,vb,0,xl+.03)[2];blinds.append(dict(y0=float(a[1]),y1=float(b[1]),top=h-.02,bottom=float(z)))
board_lo=plane(955,617,1,yb-.025);board_hi=plane(1303,401,1,yb-.025)
data=dict(room=room,window=dict(y0=window_y0,y1=window_y1,bottom=max(.04,window_bottom),top=h-.02),blinds=blinds,board=dict(x0=float(board_lo[0]),x1=float(board_hi[0]),z0=float(board_lo[2]),z1=float(board_hi[2])),surface_basis='Source ray-plane intersections conditional on accepted camera; hidden front/right extents conservative assumptions',uncertainty='Back wall fixed by conditional wardrobe depth plus estimated clearance; single-view scene scale conditional on bed length interpretation.')
surfs=[]
for id,normal,point,vis,evidence in [('wall_back',[0,-1,0],[0,yb,0],'partial','Ceiling corner 908,315 and broad rear wall; wardrobe gives estimated rear extent'),('wall_left',[1,0,0],[xl,0,0],'partial','Window wall and left wall strip; plane has measured opening, not a solid occluding wall'),('wall_front',[0,1,0],[0,yf,0],'unobserved','Behind source camera; conservative enclosed-room completion'),('wall_right',[-1,0,0],[xr,0,0],'unobserved','Beyond foreground partition; inferred enclosing wall'),('floor',[0,0,1],[0,0,0],'observed','Carpet and visible furniture feet define floor'),('ceiling',[0,0,-1],[0,0,h],'observed','Rear ceiling junction 908,315 and broad tiled ceiling')]:
  s=dict(id=id,plane=dict(normal=normal,point=point),visibility=vis,status='hypothesized' if vis=='unobserved' else 'fitted',evidence=[evidence],uncertainty=data['uncertainty'])
  if vis!='unobserved':s.update(image_constraints=[evidence],residuals={'corner_px':0 if id in ['wall_back','wall_left','ceiling'] else fit['residuals']['median_px'],'interpretation':'Conditional plane fit; exact corner by construction, not independent accuracy'})
  surfs.append(s)
data.update(surfaces=surfs,openings_and_columns_reviewed=True,opening_findings='Three tall glazed window bays, lower safety rails, roller blinds; no separate visible opaque door; right glass partition foreground. No observed load-bearing column beyond window reveal.')
atomic_json(out/'room_calibration.json',data);atomic_json(R/'authoring/room.json',data);shutil.copyfile(R/'authoring/room.py',out/'room.py')
atomic_json(out/'response.json',dict(status='complete',artifacts=['room_calibration.json','room.py'],evidence=['original full image','conditional source-ray plane constraints'],reasoning_summary='All six enclosing surfaces accounted for. Source-visible planes fitted conditional on camera; front/right walls are explicit hypotheses. Windows remain real openings in complete shell.'))
print(json.dumps(data,indent=2));print(w.accept('agent_calibrate_room',out/'response.json'));print(w.run())
