"""Create case-specific, explicitly labelled MuJoCo recipes from the frozen scene.
Run only after static visual acceptance. The editable reference scene is not posed/animated.
"""
import bpy,json,sys,shutil,math
import numpy as np
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]);out=Path(args[1]);out.mkdir(parents=True,exist_ok=True);root=Path(__file__).resolve().parents[1]
s=json.loads(source.read_text());cloth_path=Path(args[2]) if len(args)>2 else source.parent/'cloth_rest.json';cloth=json.loads(cloth_path.read_text());coat=next(o for o in bpy.data.objects if o.get('entity_id')=='coat_red' and o.type=='MESH');actual=np.array([list(coat.matrix_world@v.co) for v in coat.data.vertices]);rest=np.array(cloth['points_world']);assert actual.shape==rest.shape and np.max(abs(actual-rest))<1e-5
# Collision decomposition is part of physics setup, not a change to the frozen visual layout.
# A whole-frame AABB would incorrectly fill the doorway with a solid collision box.
objects={o['id']:o for o in s['objects']};frame_boxes=[]
for entity,confidence,evidence in [('wall_front',.1,'unobserved behind the source camera; complete-shell placement is a prior'),('wall_right',.2,'right boundary beyond visible window endpoint is hypothesized; see room calibration'),('door_leaf',.55,'partial glass door and handle observed; full extent, depth, hinge installation and mechanical clearances are priors'),('left_foreground_glass',.4,'cropped foreground glass edge observed; hidden full leaf extent and mounting inferred'),('left_foreground_frame',.55,'cropped dark edge fitted in image; unseen mounting inferred')]:
 objects[entity]['confidence']=confidence;objects[entity]['evidence']=[evidence]
for o in bpy.data.objects:
 if o.get('entity_id')=='door_frame' and o.type=='MESH':frame_boxes.append(dict(shape='box',position=list(o.matrix_world.translation),dimensions=list(o.dimensions)))
objects['door_frame']['parameters']['collision_proxies']=frame_boxes
objects['door_leaf']['parameters']['collision_proxies']=[dict(shape='box',position=[4.08,-2.25,1.095],dimensions=[.009,.84,2.16])]+[dict(shape='capsule',**{'from':[4.08,y,.02],'to':[4.08,y,2.18],'radius':.006}) for y in [-2.67,-1.83]]
if s.get('model_version',0)<4:
 for chair_id in ['chair_near','chair_far']:
  corrected=[]
  for leg in objects[chair_id]['parameters']['collision_proxies']:
   a=np.array(leg['from']);b=np.array(leg['to']);axis=(b-a)/np.linalg.norm(b-a);radius=.0115
   corrected.append(dict(shape='capsule',**{'from':(a+radius*axis).tolist(),'to':(b-radius*axis).tolist(),'radius':radius}))
   corrected.append(dict(shape='box',position=[float(a[0]),float(a[1]),.0075],dimensions=[.024,.024,.013]))
  objects[chair_id]['parameters']['collision_proxies']=corrected
 
else:
 # Version 4 proxies follow each generated member, with inscribed/shortened beam capsules and oriented seat/apron boxes.
 assert all(objects[e]['parameters'].get('collision_proxies') for e in ['table','chair_near','chair_far'])

deps=bpy.context.evaluated_depsgraph_get()
def component_proxies(entity):
 result=[]
 for o in bpy.data.objects:
  if o.get('entity_id')!=entity:continue
  if o.type=='MESH' and o.data.name.startswith('Cylinder'):
   v=np.array([list(v.co) for v in o.data.vertices]);z0,z1=float(v[:,2].min()),float(v[:,2].max());radius=float(np.linalg.norm(v[:,:2],axis=1).max());a=o.matrix_world@Vector((0,0,z0));b=o.matrix_world@Vector((0,0,z1));result.append(dict(shape='capsule',**{'from':list(a),'to':list(b),'radius':radius}))
  elif o.type=='MESH':
   ev=o.evaluated_get(deps);me=ev.to_mesh();v=np.array([list(o.matrix_world@p.co) for p in me.vertices]);lo=v.min(axis=0);hi=v.max(axis=0);ev.to_mesh_clear();result.append(dict(shape='box',position=((lo+hi)/2).tolist(),dimensions=np.maximum(hi-lo,.001).tolist()))
  elif o.type=='CURVE':
   for sp in o.data.splines:
    bp=list(sp.bezier_points)
    for a,b in zip(bp[:-1],bp[1:]):
     vs=[]
     for t in np.linspace(0,1,9):
      t=float(t);vs.append(o.matrix_world@((1-t)**3*a.co+3*(1-t)**2*t*a.handle_right+3*(1-t)*t*t*b.handle_left+t**3*b.co))
     for v,w in zip(vs[:-1],vs[1:]):result.append(dict(shape='capsule',**{'from':list(v),'to':list(w),'radius':max(.001,float(o.data.bevel_depth))}))
 return result
for entity in ['window_frames','window_rails','blinds','rack','hangers']:objects[entity]['parameters']['collision_proxies']=component_proxies(entity)
# Other garments are static context. Thin mid-surface strips avoid falsely filling an entire folded-cloth AABB.
for entity in ['coat_0','coat_1','coat_2','coat_3','coat_4']:
 o=next(o for o in bpy.data.objects if o.get('entity_id')==entity and o.type=='MESH');v=np.array([list(o.matrix_world@p.co) for p in o.data.vertices]).reshape(23,13,3);axis=np.mean(v[:,-1,:2]-v[:,0,:2],axis=0);axis/=np.linalg.norm(axis);normal=np.array([-axis[1],axis[0]]);proxies=[]
 for j in range(22):
  pts=v[j:j+2].reshape(-1,3);along=pts[:,:2]@axis;across=pts[:,:2]@normal;centerxy=axis*((along.min()+along.max())/2)+normal*across.mean();proxies.append(dict(shape='box',position=[*centerxy,float((pts[:,2].min()+pts[:,2].max())/2)],dimensions=[float(along.max()-along.min()),.002,float(np.ptp(pts[:,2])+.001)],yaw=float(math.atan2(axis[1],axis[0]))))
 objects[entity]['parameters']['collision_proxies']=proxies
seat=next(o for o in bpy.data.objects if o.get('entity_id')=='chair_near_cushion' and o.type=='MESH');q=np.array([list(seat.matrix_world@v.co) for v in seat.data.vertices]);assert q.shape==(4,3)
seat_eval=seat.evaluated_get(deps);seat_mesh=seat_eval.to_mesh();evaluated_points=np.array([list(seat.matrix_world@v.co) for v in seat_mesh.vertices]);seat_lo=evaluated_points.min(axis=0);seat_hi=evaluated_points.max(axis=0);seat_eval.to_mesh_clear();raw_lo=q.min(axis=0);raw_hi=q.max(axis=0)
q[:,:2]=(q[:,:2]-raw_lo[:2])/(raw_hi[:2]-raw_lo[:2])*(seat_hi[:2]-seat_lo[:2])+seat_lo[:2]
points=[];nx=5;ny=5;nz=3
for k in range(nz):
 for j in range(ny):
  for i in range(nx):
   u=i/(nx-1);v=j/(ny-1);p=q[0]*(1-u)*(1-v)+q[1]*u*(1-v)+q[2]*u*v+q[3]*(1-u)*v;p[2]=seat_lo[2]+(seat_hi[2]-seat_lo[2])*k/(nz-1);points.append(p.tolist())
idx=lambda i,j,k:k*nx*ny+j*nx+i;tets=[]
for k in range(nz-1):
 for j in range(ny-1):
  for i in range(nx-1):
   c=[idx(i,j,k),idx(i+1,j,k),idx(i,j+1,k),idx(i+1,j+1,k),idx(i,j,k+1),idx(i+1,j,k+1),idx(i,j+1,k+1),idx(i+1,j+1,k+1)]
   for local in [[0,1,3,7],[0,3,2,7],[0,2,6,7],[0,6,4,7],[0,4,5,7],[0,5,1,7]]:
    e=[c[a] for a in local];v=np.array([points[a] for a in e]);vol=np.linalg.det(np.stack([v[1]-v[0],v[2]-v[0],v[3]-v[0]],axis=1))
    if vol<0:e[1],e[2]=e[2],e[1]
    tets.append(e)
door_mass=36.;door_w=.84;door_h=2.18;door_t=.009;inertia=[door_mass*(door_w**2+door_h**2)/12,door_mass*(door_t**2+door_h**2)/12,door_mass*(door_t**2+door_w**2)/12]
hinge=dict(id='right_door_hinge',moving_body='door_leaf',parent_body='door_frame',moving_part_segmented=True,evidence=['right glass door with visible lever in original; inferred hinge on opposite vertical edge','36kg is a glass-panel mass prior, not a measurement; cuboid COM inertia computed from assumed dimensions','collision surrogate has 15mm lower clearance and 6mm rail radius to represent unmeasured manufacturing gaps; visual reference transforms unchanged'],parameter_provenance='assumed',axis_local=[0,0,1],anchor_local=[4.08,-2.67,0],range_rad=[0,.9],mass_kg=door_mass,inertia_diag_kgm2=inertia,center_of_mass_local=[4.08,-2.25,1.09],damping=.7,frictionloss=.08,test_torque_nm=3)
common=dict(rest_shape_matched=True,replace_static_geometry=True,parameter_provenance='assumed',contact_radius_m=.0015,poisson=.25,elastic_damping=.003,maximum_allowed_edge_strain=.50)
cloth_def=dict(common,id='red_garment_cloth',entity='coat_red',kind='cloth',points_local=rest.tolist(),elements=cloth['elements'],pinned_vertices=cloth['pinned_vertices'],mass_kg=.28,young_pa=5000000,thickness_m=.0008,rgba=[.35,.025,.055,1],evidence=['red garment source contour and actual original static mesh vertices; shoulder row pinned to hanger surrogate','5MPa is an assumed woven-fabric effective membrane modulus, not a measured property'])
soft_def=dict(common,id='chair_pad_volume',entity='chair_near_cushion',kind='soft_body',points_local=points,elements=tets,pinned_vertices=list(range(nx*ny)),mass_kg=.20,young_pa=100000,rgba=[.5,.62,.25,1],evidence=['source crop shows thin raised green pad; interior foam interpretation assumed; tetrahedral grid spans actual pad thickness, bottom bonded to seat board','100kPa firm-pad modulus is an unmeasured prior; 20kPa candidate failed the chosen 300N load test, retained in diagnostics'])
s['dynamics']=dict(hinges=[hinge],deformables=[cloth_def,soft_def],integrator='discrete',timestep_s=.0005,test_steps=2000,not_applicable={},interpretation='Actual numerical demonstration with assumed mechanics, not measured physical calibration. Static source pose preserved separately.')
for camera in bpy.data.objects:
 if camera.type=='CAMERA' and camera.name=='source_camera':camera['r2s_intrinsics_json']=json.dumps(s['camera'],sort_keys=True)
(out/'scene.json').write_text(json.dumps(s,indent=2));bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
setup=dict(reference_pose_preserved=True,parameters_are_measured_or_prior_labelled=True,target_decisions=[dict(option='hinges',entity='door_leaf',applicable=True,reason='Observed door/handle; axis and opposite-edge mounting are explicit completion priors'),dict(option='cloth',entity='coat_red',applicable=True,reason='Observed thin hanging garment; shoulder-pinned triangular shell'),dict(option='soft_bodies',entity='chair_near_cushion',applicable=True,reason='Thin raised upholstered-looking green pad is present; volumetric foam surrogate, conditional on cushion interpretation, not cloth relabelled')],rest_checks=dict(cloth_max_vertex_difference_m=float(np.max(abs(actual-rest))),cloth_vertices=len(rest),cloth_triangles=len(cloth['elements']),soft_vertices=len(points),soft_tetrahedra=len(tets)),parameter_provenance='assumed, plausible values only; no force/displacement measurements supplied',backend='MuJoCo 3.13.0',references=['https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-flexcomp','https://mujoco.readthedocs.io/en/stable/modeling.html#deformable-objects'],format_scope='MuJoCo XML and numerical trajectory; not a Blender Cloth cache')
setup['collision_refinement']='Jamb/header parts, individual window frames/rails, blinds, rack and hanger parts replace whole-entity AABBs. Other static garments use 2mm mid-surface strip proxies; micro-wrinkle contact is approximate. No visual transform changed.'
setup['integration']='MuJoCo 3.13 discrete integrator, dt0.0005s; explicit integration and obsolete implicitfast were rejected by actual diagnostics. Final contact-enabled validation is still required.'
setup['hinge_clearance_revision']='Initial collision proxies penetrated the floor by 2mm and jambs by 0.5mm, causing friction lock. Physical proxy bottom clearance is now 15mm and rail radius 6mm; frame is the parent. These are gap priors, not measurements or edits to frozen visual transforms.'
setup['soft_body_parameter_revision']='20kPa candidate was stable under gravity and 50N but inverted under the chosen 300N load. 100kPa is a plausible firm-pad prior tested for numerical demonstration; this tuning is not independent identification of the real cushion.'
setup['provenance_consolidation']='Unobserved wall, partial door and foreground glass metadata explicitly marked as hypotheses; no visual geometry/camera/material changed.'
setup['chair_collision_revision']='Capsule endpoints are shortened by their radius so spherical ends stay within flat-ended chair legs, instead of protruding 16.5mm into the cushion. Small foot proxies retained. Visual geometry unchanged.'
if s.get('model_version',0)>=4:
 setup['chair_collision_revision']='Revised rigid furniture frames supply per-member inscribed and endpoint-shortened capsules plus oriented apron/seat/top boxes. Whole-chair AABBs are not used. Curved back-rail surface collision is approximate/omitted from this demonstration; visible-mesh structure/intersection tests are separately enforced before physics.'
 setup['furniture_revision']='Near pad rests on the rebuilt seat board and ends ahead of the rear posts. Its new evaluated native envelope is used to construct the tetrahedral rest volume. No old pad trajectory or old collision envelope is reused.'
setup['soft_reference_envelope']={'method':'Construct tetrahedral volume from actual native evaluated cushion envelope, including Solidify direction; rounded edges are approximated','native_world_aabb':[seat_lo.tolist(),seat_hi.tolist()],'tet_world_aabb':[np.min(points,axis=0).tolist(),np.max(points,axis=0).tolist()],'maximum_envelope_error_m':float(np.max(abs(np.array([seat_lo,seat_hi])-np.array([np.min(points,axis=0),np.max(points,axis=0)]))))}
(out/'physics_setup.json').write_text(json.dumps(setup,indent=2))
