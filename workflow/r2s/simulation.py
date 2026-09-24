"""MJCF export with independent visual meshes and conservative editable collision recipes."""
import sys,json,math,hashlib
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,ElementTree
import numpy as np
import mujoco
SPEC=Path(sys.argv[1]).resolve();OUT=Path(sys.argv[2]).resolve();S=json.loads(SPEC.read_text());branch=S.get('branch','A');audit=json.loads((OUT/'geometry_audit.json').read_text());specs={o['id']:o for o in S['objects']}
def fmt(v):return ' '.join(f'{x:.8g}' for x in v)
root=Element('mujoco',model='real2sim_'+S['case_id']+'_'+branch);SubElement(root,'compiler',angle='radian',meshdir='meshes',inertiafromgeom='false',fusestatic='false');SubElement(root,'option',timestep='0.002',gravity='0 0 -9.81');asset=SubElement(root,'asset');world=SubElement(root,'worldbody')
collisions=[]
def box(body,key,loc,dim,yaw=0):
 assert min(dim)>0
 SubElement(body,'geom',name=key,type='box',pos=fmt(loc),size=fmt(np.array(dim)/2),euler=fmt([0,0,yaw]),group='2',contype='1',conaffinity='1',rgba='0.25 0.6 0.8 0.15',friction='0.7 0.01 0.001')
 collisions.append({'entity':body.attrib['name'],'shape':'box','pos':list(loc),'dimensions':list(dim),'yaw':yaw})
def capsule(body,key,a,b,r):
 SubElement(body,'geom',name=key,type='capsule',fromto=fmt(list(a)+list(b)),size=str(r),group='2',contype='1',conaffinity='1',rgba='0.2 0.6 0.8 0.15',friction='0.7 0.01 0.001');collisions.append({'entity':body.attrib['name'],'shape':'capsule','from':list(a),'to':list(b),'radius':r})
for key,e in audit['entities'].items():
 body=SubElement(world,'body',name=key,pos=fmt(e['root_position']),quat=fmt(e['root_quaternion_wxyz']))
 SubElement(asset,'mesh',name=key+'_visual_mesh',file=key+'.obj',inertia='shell',maxhullvert='64')
 col=[.78,.78,.73,1]
 if key in ['sofa','ottoman']:col=[.6,.20,.06,1]
 elif key.startswith('table'):col=[.67,.51,.32,1]
 elif key.startswith('chair'):col=[.83,.75,.72,1]
 SubElement(body,'geom',name=key+'_visual',type='mesh',mesh=key+'_visual_mesh',group='1',contype='0',conaffinity='0',rgba=fmt(col))
 if key in ['floor','ceiling','wall_back','wall_front','wall_left','wall_right','baseboards']:
  if key=='baseboards':continue
  lo,hi=np.array(e['local_aabb']);box(body,key+'_collision',(lo+hi)/2,hi-lo);continue
 if key not in specs:continue
 o=specs[key];W,D,H=o['dimensions'];kind=o['kind'];p=o['parameters']
 if p.get('collision_proxies'):
  for i,proxy in enumerate(p['collision_proxies']):
   name=key+f'_agent_collision{i}'
   if proxy['shape']=='box':box(body,name,proxy['position'],proxy['dimensions'],proxy.get('yaw',0))
   elif proxy['shape']=='capsule':capsule(body,name,proxy['from'],proxy['to'],proxy['radius'])
   else:raise ValueError('Unsupported explicit collision proxy: '+proxy['shape'])
 elif kind=='grid_shelf':
  t=p['outer'];inn=p['inner'];cols=p['columns'];rows=p['rows'];dx=(W-2*t-(cols-1)*inn)/cols;dz=(H-2*t-(rows-1)*inn)/rows
  for i,x in enumerate([-W/2+t/2,W/2-t/2]):box(body,key+f'_side{i}',[x,0,H/2],[t,D,H])
  for i,z in enumerate([t/2,H-t/2]):box(body,key+f'_horizontal{i}',[0,0,z],[W,D,t])
  for j in range(1,cols):box(body,key+f'_divider{j}',[-W/2+t+j*dx+(j-.5)*inn,0,H/2],[inn,D,H-2*t])
  for j in range(1,rows):box(body,key+f'_shelf{j}',[0,0,t+j*dz+(j-.5)*inn],[W-2*t,D,inn])
  box(body,key+'_lower_storage',[0,0,H*.30],[W-.08,D-.03,H*.59])
 elif kind=='sofa':
  box(body,key+'_base',[0,0,.255],[W-.06,D-.025,.27]);box(body,key+'_back',[0,D/2-.09,.56],[W-.20,.18,.45]);box(body,key+'_seat',[0,-.065,.405],[W-.26,D-.27,.17])
  for i,x in enumerate([-W/2+.07,W/2-.07]):
   box(body,key+f'_arm{i}',[x,0,.42],[.14,D,.54])
   for j,y in enumerate([-D/2+.08,D/2-.08]):capsule(body,key+f'_foot{i}{j}',[x,y,.022],[x,y,.20],.027)
 elif kind=='ottoman':
  box(body,key+'_cushion',[0,0,.27],[W,D,.38])
  for i,x in enumerate([-W*.35,W*.35]):
   for j,y in enumerate([-D*.33,D*.33]):capsule(body,key+f'_foot{i}{j}',[x,y,.024],[x,y,.08],.024)
 elif kind=='organic_table':
  outline=p.get('outline_xy',[[-W/2,-D/2],[W/2,-D/2],[W/2,D/2],[-W/2,D/2]])
  verts=[[*q,z] for z in [H-.026,H] for q in outline];name=key+'_top_hull';SubElement(asset,'mesh',name=name,vertex=fmt(np.array(verts).ravel()),inertia='convex');SubElement(body,'geom',name=key+'_top_collision',type='mesh',mesh=name,group='2',contype='1',conaffinity='1',rgba='0.2 0.6 0.8 0.15')
  collisions.append({'entity':key,'shape':'convex_top','outline':outline,'z_bounds':[H-.026,H]})
  for i,(x,y) in enumerate(p['leg_xy']):capsule(body,key+f'_leg{i}',[x,y,.02],[x*.99,y*.99,H-.035],.019)
 elif kind=='barrel_chair':
  box(body,key+'_seat',[0,-.095,.395],[W-.28,D-.38,.155])
  for i in range(14):
   a=-.65+(math.pi+1.3)*(i+.5)/14;r=W/2-.05;box(body,key+f'_shell{i}',[r*math.cos(a),r*math.sin(a)-.09,.395],[.16,.10,.64],a+math.pi/2)
  for i,x in enumerate([-W*.32,W*.32]):
   for j,y in enumerate([-D*.26,D*.26]):capsule(body,key+f'_foot{i}{j}',[x,y,.022],[x,y,.26],.023)
 elif kind=='tulip_lamp':
  elevation=o['position'][2]
  if elevation>0:box(body,key+'_riser',[0,0,-elevation/2],[.285,.285,elevation])
  box(body,key+'_base',[0,0,.025],[.27,.27,.04]);capsule(body,key+'_stem',[0,0,.05],[0,0,H-.16],.014)
 elif kind=='petal_pendant':
  SubElement(body,'geom',name=key+'_shade_collision',type='ellipsoid',pos='0 0 -0.03',size=fmt([W/2,D/2,H/2]),group='2',contype='1',conaffinity='1',rgba='0.2 0.6 0.8 0.15')
 elif kind=='rug':box(body,key+'_substrate',[0,0,H/2],[W,D,H])
 elif kind=='framed_art':box(body,key+'_frame',[0,0,0],[W,D,H])
 else:
  # Explicit conservative fallback for Agent-authored custom categories. Never changes layout.
  lo,hi=np.array(e['local_aabb']);box(body,key+'_conservative_proxy',(lo+hi)/2,np.maximum(hi-lo,.002))
# Lamps and inferred photographic illumination are preserved as explicit simulation lights.
r=S['room'];mid=np.array([(r['x_min']+r['x_max'])/2,(r['y_min']+r['y_max'])/2,r['height']*.8]);SubElement(world,'light',name='daylight_proxy',pos=fmt(mid),dir='-1 0 -0.4',diffuse='.7 .67 .6')
SubElement(world,'light',name='fill_proxy',pos=fmt(mid+[0,-.2,0]),dir='0 1 -.4',diffuse='.4 .43 .5')
for o in S['objects']:
 if o['kind']=='petal_pendant':SubElement(world,'light',name=o['id']+'_light',pos=fmt(o['position']),dir='0 0 -1',diffuse='.15 .13 .10')
camera_specs=S.get('cameras') or [S['camera']]
for index,camera in enumerate(camera_specs):
 Rc=np.array(camera['rotation_world_to_cv']);axes=np.r_[Rc[0],-Rc[1]];W,H=camera['image_size'];f=camera['focal_px'];cx,cy=camera['principal_point'];name='source_camera' if index==0 else f'source_camera_{index:04d}'
 # MuJoCo frustum offsets are expressed in sensor coordinates. Verify their transfer
 # back to top-left pixel coordinates below instead of assuming a centered fovy camera.
 SubElement(world,'camera',name=name,pos=fmt(camera['position']),xyaxes=fmt(axes),resolution=f'{W} {H}',sensorsize=fmt([.036,.036*H/W]),focalpixel=fmt([f,f]),principalpixel=fmt([W/2-cx,H/2-cy]),ipd='0')
ElementTree(root).write(OUT/'scene.xml',encoding='unicode',xml_declaration=True);(OUT/'collision_recipes.json').write_text(json.dumps(collisions,indent=2))
model=mujoco.MjModel.from_xml_path(str(OUT/'scene.xml'));data=mujoco.MjData(model);mujoco.mj_forward(model,data)
camera_transfer=[]
for index,camera in enumerate(camera_specs):
 name='source_camera' if index==0 else f'source_camera_{index:04d}';cid=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_CAMERA,name);vc=mujoco.MjvCamera();vc.type=mujoco.mjtCamera.mjCAMERA_FIXED;vc.fixedcamid=cid;view=mujoco.MjvScene(model,maxgeom=max(2000,model.ngeom+50));mujoco.mjv_updateScene(model,data,mujoco.MjvOption(),None,vc,mujoco.mjtCatBit.mjCAT_ALL,view);g=view.camera[0];W,H=camera['image_size'];f=camera['focal_px'];cx,cy=camera['principal_point'];recovered=[g.frustum_near*W/(2*g.frustum_width),g.frustum_near*H/(g.frustum_top-g.frustum_bottom),W/2-g.frustum_center*W/(2*g.frustum_width),H*g.frustum_top/(g.frustum_top-g.frustum_bottom)];error=abs(np.array(recovered)-[f,f,cx,cy]);assert max(error)<.002,'Camera intrinsic transfer mismatch'
 camera_transfer.append({'camera':name,'canonical_fx_fy_cx_cy':[f,f,cx,cy],'recovered_from_engine_frustum':recovered,'maximum_transfer_error_px':float(max(error)),'interpretation':'format transfer consistency, not physical camera calibration accuracy'})
required=['floor','ceiling','wall_back','wall_front','wall_left','wall_right']+[o['id'] for o in S['objects'] if 'lamp' in o['kind'] or 'pendant' in o['kind'] or o.get('semantic_class')=='luminaire'];missing=[x for x in required if mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,x)<0];assert not missing
# Contact probe has its own file, never becomes part of exported reconstructed scene.
group=np.array([0,0,1,0,0,0],np.uint8);rid=np.zeros(1,np.int32);probe_xy=None
for x in np.linspace(r['x_min']+.12,r['x_max']-.12,15):
 for y in np.linspace(r['y_min']+.12,r['y_max']-.12,15):
  dist=mujoco.mj_ray(model,data,np.array([x,y,r['height']*.7]),np.array([0.,0.,-1.]),group,True,-1,rid)
  if abs(dist-r['height']*.7)<.003:probe_xy=[float(x),float(y)];break
 if probe_xy is not None:break
if probe_xy is None:raise ValueError('No exposed free floor cell found for probe; provide an explicit validation probe location')
probe=SubElement(world,'body',name='test_probe',pos=fmt(probe_xy+[min(1.2,r['height']*.6)]));SubElement(probe,'freejoint');SubElement(probe,'inertial',mass='.1',diaginertia='.000036 .000036 .000036',pos='0 0 0');SubElement(probe,'geom',name='test_probe_sphere',type='sphere',size='.03',contype='1',conaffinity='1',friction='.7 .01 .001')
ElementTree(root).write(OUT/'probe_test.xml',encoding='unicode',xml_declaration=True);pm=mujoco.MjModel.from_xml_path(str(OUT/'probe_test.xml'));pd=mujoco.MjData(pm)
for _ in range(1500):mujoco.mj_step(pm,pd)
assert np.isfinite(pd.qpos).all() and abs(float(pd.qpos[2])-.03)<.015,'Sphere floor-support test failed'
rays={};z=r['height']-.04;mx=(r['x_min']+r['x_max'])/2;my=(r['y_min']+r['y_max'])/2
for name,origin,direction,expected in [
 ('left',[r['x_min']+.05,my,z],[-1,0,0],.05),('right',[r['x_max']-.05,my,z],[1,0,0],.05),
 ('back',[mx,r['y_max']-.05,z],[0,1,0],.05),('front',[mx,r['y_min']+.05,z],[0,-1,0],.05),
 ('ceiling',[*probe_xy,z],[0,0,1],.04),('floor',[*probe_xy,r['height']*.5],[0,0,-1],r['height']*.5)]:
  d=mujoco.mj_ray(model,data,np.array(origin,dtype=float),np.array(direction,dtype=float),group,True,-1,rid);rays[name]={'distance_m':float(d),'expected_m':expected,'error_m':float(abs(d-expected))};assert abs(d-expected)<.006,f'{name} ray mismatch'
report={'status':'passed','mujoco_version':mujoco.__version__,'bodies':model.nbody,'geoms':model.ngeom,'visual_meshes':model.nmesh,'required_entities_present':required,'probe_steps':1500,'probe_final_position_m':pd.qpos[:3].tolist(),'six_surface_ray_tests':rays,'camera_transfer':camera_transfer,'layout_modified':False,'limitations':['static furniture with explicit conservative collision proxies','soft fabrics, hinged cabinets and movable objects are not dynamically identified','OBJ visual meshes use flat per-entity colors in MJCF; textured reference visuals are in Blender/GLB/USD'],'collision_reference':'https://mujoco.readthedocs.io/en/stable/XMLreference.html#asset-mesh'}
(OUT/'simulation_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
