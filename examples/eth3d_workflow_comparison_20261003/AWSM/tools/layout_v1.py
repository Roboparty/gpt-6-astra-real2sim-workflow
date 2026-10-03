import json, pathlib, math, hashlib, numpy as np
R=pathlib.Path(__file__).resolve().parents[1]
M=json.loads((R/'analysis/measurements.json').read_text()); P=json.loads((R/'inputs/packet.json').read_text()); X=np.array(M['model_from_input'])
L={'version':1,'units':'metres','model_from_input':X.tolist(),'materials':{'concrete':[.34,.32,.25,.9],'ceiling':[.20,.20,.18,.95],'white_wall':[.64,.64,.59,.85],'door_white':[.67,.68,.67,.55],'steel':[.28,.30,.29,.43],'dark':[.035,.04,.04,.68],'yellow':[.76,.64,.08,.7],'green':[.51,.64,.10,.65],'wood':[.46,.34,.20,.85],'light_wood':[.76,.66,.43,.75],'blue_steel':[.025,.14,.33,.55],'orange_steel':[.56,.13,.03,.65],'bag':[.73,.75,.68,.95],'glass':[.055,.09,.10,.24],'rubber':[.022,.025,.022,.92],'red':[.58,.035,.02,.55],'lamp':[.92,.91,.84,.35]},'objects':[],'colliders':[],'lights':[]}
def obj(name,cat,evidence,prov='observed semantic topology and depth-supported visible surfaces; hidden dimensions inferred'):
 o={'id':name,'category':cat,'evidence_frames':evidence,'provenance':prov,'relations':[{'relation':'supported_by','target':'hall_floor'}],'parts':[]};L['objects'].append(o);return o
def box(o,name,c,s,mat,rot=None):
 p={'name':o['id']+'__'+name,'type':'box','center':list(c),'size':list(s),'material':mat}
 if rot:p['rotation']=rot
 o['parts'].append(p);return p
def cyl(o,name,c,r,d,mat,rot=None):
 p={'name':o['id']+'__'+name,'type':'cylinder','center':list(c),'radius':r,'depth':d,'material':mat}
 if rot:p['rotation']=rot
 o['parts'].append(p)
def mesh(o,name,verts,faces,mat):o['parts'].append({'name':o['id']+'__'+name,'type':'mesh','vertices':verts,'faces':faces,'material':mat})
def proxy(o,c,s):L['colliders'].append({'name':'COLLIDER__'+o['id'],'object_id':o['id'],'shape':'box','center':list(c),'size':list(s),'physics':'static conservative proxy; mass/friction/restitution unmeasured','exclude_from_evaluation':True})
def solid(name,cat,c,s,mat,ev):
 o=obj(name,cat,ev);box(o,'body',c,s,mat);proxy(o,c,s);return o
# Measured envelope; unseen rear thickness .15m is inference.
solid('hall_floor','floor',[-4.3,5.6,-.10],[18.8,27.2,.2],'concrete',[8,12,20,24,27])
solid('bay_floor','floor',[10,5.5,-.10],[10,10,.2],'concrete',[6,7,8])
solid('corridor_floor','floor',[-31,-3.5,-.10],[36,8,.2],'concrete',[20,21,22,32,33,34,35])
solid('hall_ceiling','ceiling',[-4.3,5.6,4.68],[18.8,27.2,.16],'ceiling',[8,12,20,28,29,30,31])
solid('bay_ceiling','ceiling',[10,5.5,4.68],[10,10,.16],'ceiling',[6,7,8])
solid('corridor_ceiling','ceiling',[-31,-3.5,4.68],[36,8,.16],'ceiling',[20,21,22])
solid('main_left_wall','wall',[-13.7,9.9,2.3],[.18,18.6,4.6],'white_wall',[12,14,15,16,20])
solid('rear_loading_wall','wall',[-4.3,19.3,2.8],[18.8,.2,5.6],'white_wall',[10,12,13])
solid('right_upper_wall','wall',[5.08,14.75,2.3],[.2,9,4.6],'white_wall',[8,10,12])
solid('bay_rear_wall','wall',[10,10.9,2.3],[10,.18,4.6],'white_wall',[6,7,8])
solid('bay_outer_wall','wall',[15,5.5,2.3],[.18,10.8,4.6],'white_wall',[6,7,8])
solid('corridor_south_wall','wall',[-31,-7.55,2.3],[36,.2,4.6],'concrete',[20,21,22,32])
solid('corridor_north_wall','wall',[-31,.55,2.3],[36,.2,4.6],'concrete',[20,21,22,32])
solid('corridor_end_door','door',[-48.5,-3.5,2.3],[.12,8,4.6],'blue_steel',[20,21,22])
# South storage facade has actual lower voids rather than a full opaque wall.
solid('storage_upper_wall','wall',[-4.3,-7.98,3.52],[18.8,.17,2.16],'white_wall',[20,23,24,28])
solid('storage_solid_pier','wall',[.8,-7.98,1.20],[4,.20,2.4],'white_wall',[24,28])
solid('storage_back_wall','wall',[-5.5,-10.6,1.5],[15,.15,3],'concrete',[20,24,28])
solid('storage_floor','floor',[-4.5,-9.3,-.10],[19,2.8,.2],'concrete',[20,24,28])
# Main industrial sliding door, seven independent leaves / rails / hinges.
door=obj('sliding_panel_door','sliding_door',[0,1,2,3,4,25,26,27]);door['relations']=[{'relation':'mounted_to','target':'door_header'}]
for j in range(7):
 y=-7.45+(j+.5)*1.05
 for k,(z,h) in enumerate([(1.05,1.90),(3.03,1.92)]):box(door,f'leaf_{j}_{k}',[5.12,y,z],[.085,1.0,h],'door_white')
 for side in [-.525,.525]:box(door,f'upright_{j}_{side}',[5.055,y+side,2.05],[.10,.04,4.10],'steel')
 for z in [.08,2.03,4.03]:box(door,f'rail_{j}_{z}',[5.05,y,z],[.10,1.05,.045],'steel')
 for z in [.5,1.4,2.6,3.5]:box(door,f'hinge_{j}_{z}',[4.985,y-.5,z],[.06,.09,.055],'steel')
proxy(door,[5.12,-3.775,2.05],[.16,7.35,4.10])
solid('door_header','header',[5.06,-3.85,4.3],[.4,8, .42],'steel',[0,4,26])
# Hazard-painted piers. Black strips are real editable meshes (portable GLB).
def clip(poly,zmin=0,zmax=2.15):
 for axis,val,greater in [(0,-.5,True),(0,.5,False),(1,zmin,True),(1,zmax,False)]:
  out=[]
  for a,b in zip(poly,poly[1:]+poly[:1]):
   ia=(a[axis]>=val) if greater else (a[axis]<=val);ib=(b[axis]>=val) if greater else (b[axis]<=val)
   if ia:out.append(a)
   if ia!=ib:
    t=(val-a[axis])/(b[axis]-a[axis]);out.append([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])
  poly=out
  if not poly:return []
 return poly
def column(name,x,y,sx,sy,ev):
 o=solid(name,'structural_column',[x,y,2.3],[sx,sy,4.6],'white_wall',ev);box(o,'yellow_base',[x,y,1.12],[sx+.008,sy+.008,2.12],'yellow')
 for face in range(4):
  for j in range(-5,10):
   a=j*.46;poly=clip([[-.5,a-.5],[.5,a+.5],[.5,a+.73],[-.5,a-.27]],.07,2.18)
   if not poly:continue
   vs=[]
   for u,z in poly:
    if face<2:vs.append([x+(-1 if face==0 else 1)*(sx/2+.005),y+u*sy,z])
    else:vs.append([x+u*sx,y+(-1 if face==2 else 1)*(sy/2+.005),z])
   mesh(o,f'stripe_{face}_{j}',vs,[list(range(len(vs)))],'dark')
 return o
column('center_column',-4.40,1.13,.72,.7,[16,17,18,19])
column('far_column',-4.40,10.64,.72,.72,[12,13,14])
column('cage_column',-4.20,-7.77,.80,.52,[23,24,28,32,33])
column('door_north_pier',5.05,.62,.65,.65,[0,3,4,6,7])
column('door_south_pier',5.05,-7.78,.65,.65,[25,26,27])
column('bay_far_pier',5.05,10.5,.65,.7,[8,9,10])
column('corridor_north_pier',-13.55,.55,.6,.55,[15,20])
column('corridor_south_pier',-13.55,-7.5,.55,.55,[20,21])
# Cages: perimeter frames plus explicit wire grid and partial stored equipment.
for n,(xa,xb) in enumerate([(-13.35,-4.65),(-3.75,-1.25)]):
 o=obj(f'storage_cage_{n}','wire_storage_cage',[20,23,24,28,32,33]);y=-7.78;h=2.4
 for x in np.arange(xa,xb+.01,1.1):box(o,f'post_{x:.2f}',[x,y,h/2],[.045,.05,h],'steel')
 for z in [0.08,1.2,2.4]:box(o,f'rail_{z}',[(xa+xb)/2,y,z],[xb-xa,.045,.04],'steel')
 for k,x in enumerate(np.arange(xa,xb,.12)):box(o,f'wire_v_{k}',[x,y,h/2],[.006,.008,h],'steel')
 for k,z in enumerate(np.arange(.08,h,.12)):box(o,f'wire_h_{k}',[(xa+xb)/2,y,z],[xb-xa,.008,.006],'steel')
 proxy(o,[(xa+xb)/2,y,1.2],[xb-xa,.08,2.4])
 for j in range(3):box(o,f'stored_container_{j}',[xa+.7+j*.8,y-.8,.6],[.65,.7,1.2],'dark')
# Pallet crate with boards and straps.
o=obj('wood_crate','pallet_crate',[8,9,10,11]);cx=2.15;cy=7.65;sx=1.25;sy=2.05
for side in [-1,1]:
 for j in range(7):
  z=.25+j*.16;box(o,f'frontback_{side}_{j}',[cx,cy+side*sy/2,z],[sx,.045,.145],'wood');box(o,f'left_right_{side}_{j}',[cx+side*sx/2,cy,z],[.045,sy,.145],'wood')
 for x in [cx-sx/2,cx+sx/2]:box(o,f'corner_{side}_{x}',[x,cy+side*sy/2,.73],[.055,.06,1.23],'orange_steel')
for x in [cx-.48,cx,cx+.48]:box(o,f'pallet_runner_{x}',[x,cy,.09],[.12,sy,.18],'wood')
for y in np.linspace(cy-.85,cy+.85,6):box(o,f'base_plank_{y}',[cx,y,.19],[sx,.18,.06],'wood')
proxy(o,[cx,cy,.73],[sx,sy,1.46])
# Two open skips; rear one partially occluded, width inferred from multiple oblique photos.
for k,cy in enumerate([10.5,13.15]):
 o=obj(f'green_skip_{k}','open_waste_skip',[8,9,10,11,12]);cx=2.65;sx=2.3;sy=2.3;h=1.5
 box(o,'base',[cx,cy,.2],[sx- .4,sy-.25,.12],'green')
 for side in [-1,1]:
  box(o,f'longwall_{side}',[cx+side*sx/2,cy,.86],[.10,sy,h-.2],'green')
  box(o,f'endwall_{side}',[cx,cy+side*sy/2,.86],[sx,.10,h-.2],'green')
  for j in [-.65,0,.65]:box(o,f'rib_{side}_{j}',[cx+side*(sx/2+.045),cy+j,.86],[.10,.06,1.4],'green')
 for x in [cx-.65,cx+.65]:box(o,f'foot_{x}',[x,cy,.08],[.18,1.6,.16],'green')
 proxy(o,[cx,cy,.8],[sx,sy,1.6])
# Storage shelving: blue uprights, orange shelf beams, pallets and individually editable bags.
o=obj('storage_shelf','pallet_racking',[6,7,8,9]);xa=5.8;xb=12.5;y=10.13
for j,x in enumerate(np.linspace(xa,xb,5)):
 for dy in [-.43,.43]:box(o,f'upright_{j}_{dy}',[x,y+dy,1.95],[.07,.07,3.9],'blue_steel')
for lev,z in enumerate([.12,1.03,2.0,3.0]):
 for dy in [-.43,.43]:box(o,f'beam_{lev}_{dy}',[(xa+xb)/2,y+dy,z],[xb-xa,.09,.14],'orange_steel')
 box(o,f'deck_{lev}',[(xa+xb)/2,y,z],[xb-xa,.86,.04],'wood')
 for j,x in enumerate(np.linspace(xa+.3,xb-.3,12)):
  box(o,f'bag_{lev}_{j}',[x,y-.08,z+.34],[.43,.60,.58],'bag')
  cyl(o,f'bag_neck_{lev}_{j}',[x,y-.08,z+.66],.06,.09,'bag')
proxy(o,[(xa+xb)/2,y,1.95],[xb-xa,.95,3.9])
# Trailer, length in X, observed front x10.3; unseen chassis construction inferred.
o=obj('box_trailer','trailer',[6,7,8]);box(o,'cargo_box',[12.0,7.92,1.6],[3.38,1.86,2.26],'door_white');box(o,'chassis',[11.8,7.92,.39],[3.8,1.9,.12],'steel')
for yy in [6.97,8.87]:
 for xx in [11.7,12.3]:cyl(o,f'wheel_{xx}_{yy}',[xx,yy,.34],.34,.16,'rubber',[math.pi/2,0,0])
for xx in [11.4,12.5]:box(o,f'window_{xx}',[xx,6.975,1.85],[.62,.025,.67],'glass')
box(o,'drawbar',[9.6,7.92,.40],[1.9,.10,.10],'steel');cyl(o,'support_wheel',[8.7,7.92,.16],.15,.07,'rubber',[math.pi/2,0,0]);proxy(o,[11.6,7.92,1.37],[4.8,2.1,2.74])
# Delivery truck: wheelbase, cab wedge, separate windows/lamps/bumper and cargo box.
o=obj('delivery_truck','refrigerated_delivery_truck',[12,13,14,15]);cx=-5.64
box(o,'cargo',[cx,12.7,1.73],[2.15,4.15,2.65],'door_white');box(o,'refrigerator',[cx,10.51,2.57],[.95,.42,.60],'door_white')
verts=[[cx+x,y,z] for x in [-.96,.96] for y,z in [(8.5,.46),(10.7,.46),(10.7,2.0),(9.2,2.0),(8.65,1.1)]]
mesh(o,'cab',verts,[list(range(5)),list(range(5,10)),[0,1,6,5],[1,2,7,6],[2,3,8,7],[3,4,9,8],[4,0,5,9]],'door_white')
mesh(o,'windshield',[[cx-.85,8.85,1.2],[cx+.85,8.85,1.2],[cx+.85,9.21,1.93],[cx-.85,9.21,1.93]],[[0,1,2,3]],'glass')
box(o,'bumper',[cx,8.45,.56],[2.05,.16,.32],'dark');box(o,'grille',[cx,8.48,.91],[1.1,.05,.25],'dark')
for s in [-1,1]:
 box(o,f'headlamp_{s}',[cx+s*.79,8.46,.96],[.30,.04,.24],'lamp');box(o,f'cab_sideglass_{s}',[cx+s*.968,9.94,1.63],[.015,.9,.65],'glass')
 for yy in [9.3,13.5]:cyl(o,f'wheel_{s}_{yy}',[cx+s*1.04,yy,.39],.39,.18,'rubber',[0,math.pi/2,0]);cyl(o,f'hub_{s}_{yy}',[cx+s*1.14,yy,.39],.23,.012,'steel',[0,math.pi/2,0])
proxy(o,[cx,11.55,1.55],[2.3,6.2,3.1])
# Parked hatchback, compact multi-part silhouette; unseen front inferred.
o=obj('black_hatchback','car',[10,11,12,13]);cx=-2.8;cy=13.25
box(o,'lower_body',[cx,cy,.60],[1.58,3.35,.62],'dark');box(o,'cabin',[cx,cy+.1,1.07],[1.40,1.90,.66],'dark');box(o,'rear_window',[cx,cy-.86,1.18],[1.26,.02,.43],'glass')
for s in [-1,1]:
 box(o,f'taillamp_{s}',[cx+s*.65,cy-1.69,.91],[.19,.025,.31],'red')
 for yy in [cy-1.03,cy+1.05]:cyl(o,f'wheel_{s}_{yy}',[cx+s*.81,yy,.31],.31,.15,'rubber',[0,math.pi/2,0])
proxy(o,[cx,cy,.73],[1.78,3.5,1.46])
# Raised loading dock and distant blue lift doors.
solid('loading_dock','raised_platform',[-4.3,17.85,.5],[18.7,3.1,1.0],'concrete',[9,10,12,13])
solid('blue_service_door','service_door',[-4.3,19.17,2.35],[4.25,.04,2.7],'blue_steel',[10,12,13])
solid('dock_wooden_box','wooden_crate',[-1.5,18.0,1.55],[3.6,1,1.1],'light_wood',[12])
# Lumber cart: retain depth edge conflicts in measurements; solid interior face fixes y~-6.95.
o=obj('lumber_trolley','lumber_cart',[23,24,25,28]);cx=.95;cy=-6.97
box(o,'frame',[cx,cy,.25],[2.0,.72,.08],'blue_steel')
for xx in [cx-.9,cx+.9]:
 box(o,f'upright_{xx}',[xx,cy-.28,1.05],[.045,.05,1.65],'blue_steel')
 for yy in [cy-.25,cy+.25]:cyl(o,f'caster_{xx}_{yy}',[xx,yy,.14],.13,.055,'rubber',[math.pi/2,0,0])
for j in range(11):box(o,f'lumber_{j}',[cx+(.09 if j%3==0 else 0),cy+.10,.38+j*.055],[4.65-(j%3)*.10,.46,.05],'light_wood')
box(o,'restraining_strap',[cx-.22,cy+.345,.67],[.035,.015,.7],'dark');proxy(o,[cx,cy,.87],[4.8,.9,1.74])
# Compactor in long corridor, approximate observed multipart form.
o=obj('corridor_compactor','industrial_compactor',[20,21,22,32,33,34]);box(o,'lower_machine',[-19.55,-1.22,.73],[2.2,1.7,1.46],'door_white');box(o,'hopper',[-19.55,-1.22,2.35],[2.25,1.78,1.45],'steel');box(o,'front_panel',[-18.4,-1.22,1.0],[.04,1.3,.75],'yellow');proxy(o,[-19.55,-1.22,1.55],[2.4,1.9,3.1])
# Wall-mounted fire box/sink and utility details.
solid('fire_cabinet','fire_cabinet',[-13.56,2.7,1.55],[.15,.42,.55],'red',[16,20])
solid('utility_sink','sink',[-13.40,1.45,.87],[.48,.52,.22],'steel',[16,20])
o=obj('fire_extinguisher','fire_extinguisher',[16,20]);cyl(o,'body',[-13.45,2.7,.54],.095,.6,'red');proxy(o,[-13.45,2.7,.55],[.25,.25,.8])
# Ceiling fixtures and pipe runs follow observed orthogonal building axes.
o=obj('overhead_pipes','utility_pipes',[8,12,20,24,28,29,30,31]);o['relations']=[{'relation':'mounted_to','target':'hall_ceiling'}]
for j,x in enumerate([3.9,4.12,4.35]):cyl(o,f'longitudinal_{j}',[x,5.5,4.24],.045,27,'steel',[math.pi/2,0,0])
for j,y in enumerate([-6.9,-6.65]):cyl(o,f'transverse_{j}',[-3.8,y,4.23],.05,18.2,'steel',[0,math.pi/2,0])
o=obj('light_fixtures','lighting',[8,12,20,28,29,30,31]);o['relations']=[{'relation':'mounted_to','target':'hall_ceiling'}]
for x in [-11,-4,2]:
 for y in [-5,0,5,10,15]:
  box(o,f'fixture_{x}_{y}',[x,y,4.43],[.12,3.5,.08],'steel');box(o,f'tube_{x}_{y}',[x,y,4.375],[.06,3.3,.035],'lamp');L['lights'].append({'center':[x,y,4.31],'length':3.0,'power':160})
for x in [-17,-23,-29,-35,-41,-46]:
 box(o,f'corridor_{x}',[x,-3.5,4.40],[.10,2.5,.08],'lamp');L['lights'].append({'center':[x,-3.5,4.3],'length':2.4,'power':130})
# Sparse construction joints: semantic surface markings, never evaluation masks.
o=obj('floor_joints','floor_surface_joints',[12,20,24,27]);o['relations']=[{'relation':'on_surface','target':'hall_floor'}]
for y in [-6,-1,4,9,14]:box(o,f'eastwest_{y}',[-4.3,y,.003],[18.7,.012,.002],'dark')
for x in [-11,-5,1]:box(o,f'northsouth_{x}',[x,5.6,.003],[.01,27,.002],'dark')
# Record object dimensions from actual generated components, not prose placeholders.
objects=[]
for o in L['objects']:
 pts=[]
 for p in o['parts']:
  if p['type']=='mesh':pts.extend(p['vertices'])
  elif p['type']=='box':
   c=np.array(p['center']);s=np.array(p['size'])/2;pts.extend([c-s,c+s])
  else:
   c=np.array(p['center']);s=np.array([p['radius']]*3);s[2]=p['depth']/2
   if p.get('rotation')==[0,math.pi/2,0]:s=np.array([p['depth']/2,p['radius'],p['radius']])
   if p.get('rotation')==[math.pi/2,0,0]:s=np.array([p['radius'],p['depth']/2,p['radius']])
   pts.extend([c-s,c+s])
 a=np.array(pts);objects.append({k:v for k,v in o.items() if k!='parts'}|{'components':[p['name'] for p in o['parts']],'dimensions':(a.max(0)-a.min(0)).tolist(),'bounds':[a.min(0).tolist(),a.max(0).tolist()],'measurement_source':'analysis/measurements.json and point_measurements.json; semantic completion explicitly inferred'})
(R/'layout.json').write_text(json.dumps(L,indent=2));(R/'objects.json').write_text(json.dumps({'objects':objects},indent=2));(R/'colliders.json').write_text(json.dumps({'colliders':L['colliders'],'physical_parameters':'unmeasured, no physical acceptance'},indent=2))
cs={'frames':[{'sample_index':f['input_index'],'source_index':f['input_index'],'frame_id':f['frame_id'],'timestamp_ns':f['input_index'],'camera_to_world':(X@np.array(f['T_world_camera'])).tolist(),'intrinsics':f['K'],'valid':True,'confidence':'provided registered reference camera; no per-frame adjustment'} for f in P['frames']],'coordinate_frame':'model','pose_convention':'OpenCV RDF camera-to-world','intrinsic_convention':'integer-centre','model_from_input':X.tolist()};(R/'cameras.json').write_text(json.dumps(cs,indent=2))
issues=['DA3 predicted-depth disagreement at thin lumber and cage grid retained in measurement records','Far corridor end depth and hidden surfaces uncertain; no GT feedback','Truck/car/trailer hidden shape, tire detail, physics and materials inferred','Lighting approximate, procedural Blender textures have only base-color equivalents in GLB','No claim original Astra identity, original World Lobby reconstruction or physics acceptance']
manifest={'method_id':'AWSM','model_id':'inherited Codex model; exact serving identifier not exposed','status':'v1_ready_for_input_checks','model_from_input':X.tolist(),'geometry_scale':1,'revisions':1,'checking_render_count':0,'input_bvh_pass_count':0,'input_packet_sha256':hashlib.sha256((R/'inputs/packet.json').read_bytes()).hexdigest(),'depth_manifest_sha256':hashlib.sha256((R/'inputs/depth_reference/manifest.json').read_bytes()).hexdigest(),'unresolved_issues':issues,'quality_status':'LIMITED_PENDING_INDEPENDENT_REVIEW','protocol_deviations':['36 real ETH3D images replacing synthetic 180 World Lobby','fixed paired indices 0,4,8,12,16,20,24,28,32,35','Blender4.5.3 replacing original5.2','same inherited Codex model replacing original Astra','actual-aspect width640 RGB and160x120 exact K depth checker','public registered K/T plus same pose-conditioned DA3 predicted depth, M4-like condition'],'construction':'editable semantic parametric parts; no fused point or triangle view-patch final mesh'}
(R/'modelling_manifest.json').write_text(json.dumps(manifest,indent=2));(R/'iteration_log.json').write_text(json.dumps([{'version':1,'action':'fresh measured semantic construction','reason':'RGB inventory + robust plane fits + labelled interior depth points; mixed-region errors retained','measurement_files':['analysis/measurements.json','analysis/point_measurements.json'],'geometry_sources':'own input RGB, K/T, frozen DA3 only','status':'await_checks'}],indent=2))
print('LAYOUT',len(objects),'objects',sum(len(o['parts']) for o in L['objects']),'parts')
