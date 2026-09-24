"""Case-specific editable model, authored from original image annotations only.
Run with Blender --background --python build_scene.py -- OUT [neutral|lit] [version].
"""
import bpy,math,json,sys,random,os
from pathlib import Path
from mathutils import Vector,Matrix
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
args=sys.argv[sys.argv.index('--')+1:];OUT=Path(args[0]);OUT.mkdir(exist_ok=True,parents=True)
mode=args[1] if len(args)>1 else 'lit';version=int(args[2]) if len(args)>2 else 1
cal=json.loads((ROOT/'case/calibration_initial.json').read_text());R=np.array(cal['rotation_world_to_cv']);C=np.array(cal['position']);F=cal['focal_px'];PP=np.array(cal['principal_point']);W,H=cal['image_size']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=24;sc.cycles.use_denoising=True;sc.render.resolution_x=W;sc.render.resolution_y=H;sc.render.resolution_percentage=50
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=0
sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 sc.cycles.device='CPU' if os.environ.get('R2S_CPU')=='1' else 'GPU'
except:pass
def lin(v):return v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4
def mat(name,color,rough=.7,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*[lin(c) for c in color],1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
wall=mat('paint_warm_offwhite',(.81,.80,.74),.85);ceilm=mat('mineral_ceiling_tile',(.78,.78,.72),.9);black=mat('black_powdercoat',(.055,.065,.06),.52);metal=mat('brushed_aluminium',(.46,.48,.46),.38,.65);wood=mat('wood_clear_lacquer',(.58,.46,.29),.52);topmat=mat('gray_laminate',(.46,.48,.46),.68);green=mat('green_woven_seat',(.56,.61,.30),.87);carpet=mat('carpet_gray',(.42,.43,.40),.97);blindmat=mat('roller_blind_woven',(.53,.53,.46),.9);darkcloth=mat('black_woven_clothing',(.042,.06,.055),.96);teal=mat('teal_woven_clothing',(.05,.12,.13),.92);red=mat('red_woven_clothing',(.30,.035,.07),.88);pale=mat('pale_coat',(.56,.56,.49),.88);yellow=mat('warning_yellow',(.79,.60,.035),.67);bin_green=mat('recycle_green',(.01,.32,.20),.67);glass=mat('door_glass',(.80,.90,.85),.14);glass.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=1;glass.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value=1.45
def noise_bump(m,scale,strength,distance):
 ns=m.node_tree.nodes;lk=m.node_tree.links;t=ns.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=scale;t.inputs['Detail'].default_value=2;b=ns.new('ShaderNodeBump');b.inputs['Strength'].default_value=strength;b.inputs['Distance'].default_value=distance;lk.new(t.outputs['Fac'],b.inputs['Height']);lk.new(b.outputs[0],ns['Principled BSDF'].inputs['Normal'])
for m in [green,blindmat,darkcloth,teal,red,pale]:noise_bump(m,210,.24,.0009)
noise_bump(wood,90,.12,.0004);noise_bump(wall,120,.08,.0003)
# Carpet physically scaled per-tile weave, alternating orientation using actual tile objects.
for orient in range(2):
 m=carpet if orient==0 else carpet.copy();m.name='carpet_tile_'+str(orient)
 ns=m.node_tree.nodes;lk=m.node_tree.links;tc=ns.new('ShaderNodeTexCoord');wave=ns.new('ShaderNodeTexWave');wave.wave_type='BANDS';wave.bands_direction='X' if orient==0 else 'Y';wave.inputs['Scale'].default_value=150;wave.inputs['Distortion'].default_value=7;wave.inputs['Detail Scale'].default_value=2
 lk.new(tc.outputs['Object'],wave.inputs['Vector']);ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.115,.12,.11,1);ramp.color_ramp.elements[1].color=(.23,.24,.22,1);lk.new(wave.outputs['Color'],ramp.inputs[0]);lk.new(ramp.outputs[0],ns['Principled BSDF'].inputs['Base Color']);b=ns.new('ShaderNodeBump');b.inputs['Strength'].default_value=.22;b.inputs['Distance'].default_value=.0009;lk.new(wave.outputs['Color'],b.inputs['Height']);lk.new(b.outputs[0],ns['Principled BSDF'].inputs['Normal'])
CARP=[bpy.data.materials['carpet_tile_0'],bpy.data.materials['carpet_tile_1']]
entities={};counter={};proxy={}
def record(e,kind='custom',conf=.8,evidence='source observation; editable custom geometry'):
 entities.setdefault(e,dict(id=e,kind=kind,evidence=[evidence],confidence=conf,layout_lock=True,parameters={},asset_resolution={'mode':'authored_A'}))
def tag(o,e,m):
 record(e);o['entity_id']=e;o['layout_locked']=True;counter[e]=counter.get(e,0)+1;o.name=e if counter[e]==1 else e+'__'+str(counter[e]);
 if m:o.data.materials.append(m)
 return o
def box(e,p,d,m,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=tag(bpy.context.object,e,m);o.dimensions=d;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  mod=o.modifiers.new('manufactured_edge_radius','BEVEL');mod.width=bevel;mod.segments=3;o.modifiers.new('weighted_corner_normals','WEIGHTED_NORMAL')
 return o
def mesh(e,vs,fs,m,solid=0,bevel=0):
 me=bpy.data.meshes.new(e+'_mesh');me.from_pydata(vs,[],fs);me.update();o=bpy.data.objects.new(e,me);bpy.context.collection.objects.link(o);tag(o,e,m)
 if solid:q=o.modifiers.new('physical_thickness','SOLIDIFY');q.thickness=solid
 if bevel:q=o.modifiers.new('edge_softness','BEVEL');q.width=bevel;q.segments=3
 return o
def rod(e,a,b,r,m,vertices=12):
 if version>=3 and e=='table':
  a,b=Vector(a),Vector(b);v=b-a;o=box(e,(a+b)/2,(r*1.7,r*1.3,v.length),m,.002);o.rotation_euler=v.to_track_quat('Z','Y').to_euler();return o
 a,b=Vector(a),Vector(b);v=b-a;bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=v.length,location=(a+b)/2);o=tag(bpy.context.object,e,m);o.rotation_euler=v.to_track_quat('Z','Y').to_euler()
 for poly in o.data.polygons:poly.use_smooth=True
 return o
def curve(e,points,r,m):
 cu=bpy.data.curves.new(e+'_curve','CURVE');cu.dimensions='3D';cu.resolution_u=16;cu.bevel_depth=r;cu.bevel_resolution=3;sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
 for p,co in zip(sp.bezier_points,points):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 o=bpy.data.objects.new(e,cu);bpy.context.collection.objects.link(o);return tag(o,e,m)
def inv(uv,z=None,y=None,x=None):
 ray=np.r_[(np.array(uv)-PP)/F,1]@R;axis=2 if z is not None else 1 if y is not None else 0;v=z if z is not None else y if y is not None else x;distance=(v-C[axis])/ray[axis]
 if distance<=0:raise ValueError('Annotation ray falls behind camera: '+str(uv))
 return C+ray*distance
def proj(xyz):
 q=(np.array(xyz)-C)@R.T;return q[:2]/q[2]*F+PP
height=2.8;win_end=cal['room_parameters']['width'];xmax=win_end+.68;ymin=-4.65;t=.12
room=dict(x_min=0,x_max=xmax,y_min=ymin,y_max=0,height=height,thickness=t,preserve_full_shell=True)
box('floor',(xmax/2,ymin/2,-.061),(xmax,-ymin,.12),carpet)
for i in range(math.ceil(xmax/.5)):
 for j in range(math.ceil(-ymin/.5)):
  w=min(.5,xmax-i*.5);d=min(.5,-ymin-j*.5)
  box('floor',(i*.5+w/2,-j*.5-d/2,.001),(w-.001,d-.001,.002),CARP[(i+j)%2])
box('ceiling',(xmax/2,ymin/2,height+.06),(xmax,-ymin,.12),ceilm)
# Thin suspended ceiling grid remains below complete ceiling slab.
for x in np.arange(0,xmax,.6):box('ceiling',(float(x),ymin/2,height+.001),(.009,-ymin,.006),wall)
for y in np.arange(ymin,0,.6):box('ceiling',(xmax/2,float(y),height+.001),(xmax,.009,.006),wall)
# Back wall is a perforated composite: opaque left pier, right return, sill and header.
xstart=float(inv([787,160],y=0)[0]);sill=.055
box('wall_back',(xstart/2,.06,height/2),(xstart,.12,height),wall)
box('wall_back',((win_end+xmax)/2,.06,height/2),(xmax-win_end,.12,height),wall)
box('wall_back',((xstart+win_end)/2,.06,sill/2),(win_end-xstart,.12,sill),wall)
box('wall_back',((xstart+win_end)/2,.06,height-.025),(win_end-xstart,.12,.05),wall)
left_window_depth=1.05
box('wall_left',(-.06,(ymin-left_window_depth)/2,height/2),(.12,-ymin-left_window_depth,height),wall)
box('wall_left',(-.06,-left_window_depth/2,.025),(.12,left_window_depth,.05),wall)
box('wall_left',(-.06,-left_window_depth/2,height-.025),(.12,left_window_depth,.05),wall)
if version<2:box('wall_right',(xmax+.06,ymin/2,height/2),(.12,-ymin,height),wall)
else:
 for ya,yb in [(ymin,-2.72),(-1.78,0)]:box('wall_right',(xmax+.06,(ya+yb)/2,height/2),(.12,yb-ya,height),wall)
 box('wall_right',(xmax+.06,-2.25,(2.22+height)/2),(.12,.94,height-2.22),wall)
 # Door jamb returns connect the observed inner glass plane to the inferred outside wall.
 for y in [-2.70,-1.80]:box('door_frame',((4.08+xmax+.12)/2,y,1.11),(xmax+.12-4.08,.045,2.22),wall,.002)
 box('door_frame',((4.08+xmax+.12)/2,-2.25,2.22),(xmax+.12-4.08,.94,.055),wall,.002)
 # The observed glass door leads to an indoor continuation, not the outdoor sky.
 # Conservative unseen returns prevent the environment sun entering through an interior doorway.
 ext=xmax+.52
 box('doorway_unseen_returns',(ext,-2.25,1.4),(.10,1.9,2.8),wall)
 for y in [-3.2,-1.3]:box('doorway_unseen_returns',((xmax+.121+ext)/2,y,1.4),(ext-xmax-.121,.08,2.8),wall)
 box('doorway_unseen_returns',((xmax+ext)/2,-2.25,-.045),(ext-xmax,1.9,.09),carpet)
 box('doorway_unseen_returns',((xmax+ext)/2,-2.25,2.85),(ext-xmax,1.9,.10),ceilm)
 entities['doorway_unseen_returns']['confidence']=.15;entities['doorway_unseen_returns']['evidence']=['indoor doorway continuation hypothesis; exact hidden corridor plan unknown; prevents unphysical direct outdoor sun through interior door']
box('wall_front',(xmax/2,ymin-.06,height/2),(xmax,.12,height),wall)
# Column side faces from calibrated width and depth, rigid vertical geometry.
rp=cal['room_parameters'];near=rp['column_front_y'];far=-rp['left_window_depth'];cw=rp['column_width']
box('column',(cw/2,(near+far)/2,height/2),(cw,far-near,height),wall,.003)
for x1,y1,x2,y2 in [(0,ymin,0,near),(cw,near,cw,far),(0,0,xstart,0),(win_end,0,xmax,0),(xmax,0,xmax,ymin)]:
 a=np.array([x1,y1,.045]);b=np.array([x2,y2,.045]);v=b-a;o=box('baseboards',(a+b)/2,(np.linalg.norm(v),.017,.09),wall,.002);o.rotation_euler.z=math.atan2(v[1],v[0])
# Actual window glass omitted on open-view areas (clear glass has negligible tint in reference); frames remain physical.
xs=[xstart,float(inv([900,142],y=0)[0]),float(inv([1146,86],y=0)[0]),win_end]
for x in xs:box('window_frames',(x,-.025,height/2),(.035,.06,height-.03),black,.003)
zrail=float(inv([900,539],y=0)[2])
for z in [.095,zrail,height-.04]:box('window_frames',((xstart+win_end)/2,-.03,z),(win_end-xstart,.065,.045),black,.003)
if version>=2:
 transom_z=float(inv([1220,291],y=0)[2]);box('window_frames',((xs[2]+xs[3])/2,-.035,transom_z),(xs[3]-xs[2],.075,.085),black,.003)
for x in np.arange(xstart+.055,win_end,.13):rod('window_rails',(x,-.07,.10),(x,-.07,zrail-.03),.011,black)
for ya in [-left_window_depth,0]:box('window_frames',(-.005,ya,height/2),(.055,.025,height),black)
for z in [.095,.75,height-.04]:box('window_frames',(-.005,-left_window_depth/2,z),(.055,left_window_depth,.035),black)
for y in np.arange(-left_window_depth+.04,0,.12):rod('window_rails',(.035,y,.10),(.035,y,.74),.01,black)
for k,(x0,x1) in enumerate(zip(xs[:-1],xs[1:])):
 bottom=float(inv(([830,489] if k==0 else [1010,500] if k==1 else [1250,265]),y=-.065)[2]);top=height-.075
 # Very gentle cloth bow, with visible narrow folded edges.
 vs=[];fs=[];nx=18;nz=20
 for j in range(nz+1):
  z=bottom+(top-bottom)*j/nz
  for i in range(nx+1):
   x=x0+.018+(x1-x0-.036)*i/nx;y=-.068-.008*math.sin(i/nx*math.pi)*math.sin(j/nz*math.pi)-.002*math.sin(i*.7);vs.append((x,y,z))
 for j in range(nz):
  for i in range(nx):a=j*(nx+1)+i;fs.append((a,a+1,a+nx+2,a+nx+1))
 mesh('blinds',vs,fs,blindmat,.001);rod('blinds',(x0+.016,-.072,bottom),(x1-.016,-.072,bottom),.009,metal)
leftbot=.78
box('blinds',(.05,-left_window_depth/2,(leftbot+height-.07)/2),(.007,left_window_depth-.045,height-.07-leftbot),blindmat)
# Exterior contextual geometry; not treated as measured buildings.
ext=mat('distant_building',(.55,.65,.68),.95)
box('exterior_building',(2.5,9,1.6),(8,.5,5),ext)
for x in np.arange(-1,7,.35):
 for z in np.arange(-.5,4,.35):box('exterior_building',(x,8.74,z),(.20,.012,.21),mat('extglass_'+str(x)+'_'+str(z),(.33,.49,.53),.5))
leaf=mat('distant_foliage',(.29,.40,.13),1)
random.seed(9)
for i in range(45):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=random.uniform(.14,.4),location=(random.uniform(-1,5),random.uniform(1,4),random.uniform(-.1,.7)));tag(bpy.context.object,'exterior_foliage',leaf)
if version>=2:
 # Source-derived outdoor-only backdrop, entirely behind the room. No indoor photo pixels are projected onto reconstructed geometry.
 for e in ['exterior_building','exterior_foliage']:
  for o in list(bpy.data.objects):
   if o.get('entity_id')==e:bpy.data.objects.remove(o,do_unlink=True)
  entities.pop(e,None)
 uvq=[[u,v] for v in np.linspace(-50,800,35) for u in np.linspace(450,1500,43)];vp=[inv(p,y=8).tolist() for p in uvq];faces=[]
 for j in range(34):
  for i in range(42):a=j*43+i;faces.append((a,a+1,a+44,a+43))
 backdrop=mesh('exterior_backdrop',vp,faces,None)
 mm=bpy.data.materials.new('source_derived_exterior_only');mm.use_nodes=True;ns=mm.node_tree.nodes;ns.clear();tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'evidence/exterior_only.png'));tex.extension='EXTEND';em=ns.new('ShaderNodeEmission');em.inputs['Strength'].default_value=.9;outnode=ns.new('ShaderNodeOutputMaterial');mm.node_tree.links.new(tex.outputs['Color'],em.inputs['Color']);mm.node_tree.links.new(em.outputs[0],outnode.inputs['Surface']);backdrop.data.materials.append(mm)
 uvmap=backdrop.data.uv_layers.new(name='source_camera_projection')
 for face in backdrop.data.polygons:
  for loop_index in face.loop_indices:
   u,v=uvq[backdrop.data.loops[loop_index].vertex_index];uvmap.data[loop_index].uv=(u/W,1-v/H)
 entities['exterior_backdrop']['confidence']=.3;entities['exterior_backdrop']['evidence']=['original outdoor pixel regions only; source-camera projection; external depth unmeasured and novel-view background not validated']
if version>=3:
 box('external_shading_hypothesis',(3.5,3.0,4.9),(8,.12,2.2),wall)
 record('external_shading_hypothesis','exterior_shadow_proxy',.15,'unobserved exterior obstruction hypothesis, blocks upper-window direct sun; not a recovered building')
 entities['external_shading_hypothesis']['kind']='exterior_shadow_proxy';entities['external_shading_hypothesis']['confidence']=.15;entities['external_shading_hypothesis']['evidence']=['inferred exterior solar obstruction, unobserved and not independently validated; source has no strong upper-window far-floor sun pool']
if version>=4:
 exec(compile((ROOT/'case/furniture_model.py').read_text(),str(ROOT/'case/furniture_model.py'),'exec'))
else:
 # Table: all four corners fit the photo at a plausible height, separately editable trestles.
 th=.81;top_uv=[[615,576],[739,547],[849,556],[716,597]];tp=[inv(p,z=th) for p in top_uv]
 mesh('table',[v.tolist() for v in tp],[(0,1,2,3)],topmat,.022,.004)
 for idx,(a,b) in enumerate([(tp[0],tp[3]),(tp[1],tp[2])]):
  center=(a+b)/2
  for q,sgn in [(a,1),(b,-1)]:
   up=q+(center-q)*.08;up[2]=th-.025;bottom=up.copy();bottom[2]=.02;bottom[:2]+=(q-center)[:2]*.10
   if idx==0:bottom=inv([636,724] if sgn==1 else [720,750],z=.02)
   rod('table',up,bottom,.021,wood);proxy.setdefault('table',[]).append(dict(shape='capsule',**{'from':bottom.tolist(),'to':up.tolist(),'radius':.024}))
   if version>=3:box('table',(bottom[0],bottom[1],.011),(.033,.025,.022),wood,.002)
  a2=a*.82+b*.18;b2=a*.18+b*.82;a2[2]=b2[2]=.37;rod('table',a2,b2,.020,wood)
 rod('table',[(tp[0][0]+tp[3][0])/2,(tp[0][1]+tp[3][1])/2,.44],[(tp[1][0]+tp[2][0])/2,(tp[1][1]+tp[2][1])/2,.44],.023,wood)
 # Chairs: ray-fitted seat polygon, real thin foam pad, curved low back and tapered legs.
 def chair(e,seat_uv,foot_uv,back_uv,zseat):
  q=[inv(p,z=zseat) for p in seat_uv];center=np.mean(q,axis=0);mesh(e,q,[(0,1,2,3)],wood,.025,.005)
  pad=[v+(center-v)*.05+[0,0,.019] for v in q];o=mesh(e+'_cushion',pad,[(0,1,2,3)],green,.03,.012);record(e+'_cushion','seat_cushion',.77,'green padded raised seat visible in source crop; internal foam inferred')
  for k in range(4):
   up=q[k]+(center-q[k])*.10;up[2]-=.01;bottom=inv(foot_uv[k],z=.012)
   if version>=3:bottom[:2]=bottom[:2]*.5+up[:2]*.5
   rod(e,bottom,up,.012,wood);proxy.setdefault(e,[]).append(dict(shape='capsule',**{'from':bottom.tolist(),'to':up.tolist(),'radius':.014}))
   if version>=3:rod(e,(bottom[0],bottom[1],.001),(bottom[0],bottom[1],.014),.012,black)
  # Back is behind the seat, continuous low bowed wood strip, no invented armrests.
  bq=[inv(p,z=zseat+.225) for p in back_uv];mid=(bq[0]+bq[1])/2;mid[2]-=.025
  curve(e,[bq[0],mid,bq[1]],.022,wood)
  for a,b in [(bq[0],q[0]),(bq[1],q[1])]:rod(e,a,b,.012,wood)
  return pad
 chair('chair_near',[[766,638],[824,626],[860,645],[798,664]],[[764,713],[829,701],[858,698],[833,739]],[[773,610],[862,593]],.44)
 chair('chair_far',[[643,605],[674,600],[704,615],[668,627]],[[642,691],[667,679],[706,683],[666,710]],[[625,568],[674,559]],.44)
 
# Garment rack axis reconstructed by projecting the observed top rail to z=1.45.
ra=inv([1064,419],z=1.45);rb=inv([1380,419],z=1.45);axis=rb-ra;axis[2]=0;axis/=np.linalg.norm(axis);n=np.array([-axis[1],axis[0],0]);rackfeet=[]
for end,uvfoot in [(ra,[1019,765]),(rb,[1320,766])]:
 for sign in [-1,1]:
  foot=end+n*sign*.18;foot[2]=.015;rackfeet.append(foot);top=end+[0,0,.015];rod('rack',top,foot,.012,wood);proxy.setdefault('rack',[]).append(dict(shape='capsule',**{'from':foot.tolist(),'to':top.tolist(),'radius':.012}))
  if version>=3:rod('rack',(foot[0],foot[1],.001),(foot[0],foot[1],.017),.012,wood)
rod('rack',ra-axis*.075,rb+axis*.10,.012,wood)
for frac in np.linspace(-.9,.9,6):
 a=ra+n*frac*.18;a[2]=.16;b=rb+n*frac*.18;b[2]=.16;rod('rack',a,b,.008,wood)
for end in [ra,rb]:a=end-n*.18;a[2]=.16;b=end+n*.18;b[2]=.16;rod('rack',a,b,.012,wood)
# Clothing surfaces: tailored shoulder/sleeve outlines and depth waves, not boxes.
garment_data=[('coat_0',.24,.44,.84,darkcloth),('coat_1',.38,.42,.92,darkcloth),('coat_2',.49,.42,.92,teal),('coat_3',.61,.40,.94,darkcloth),('coat_4',.72,.38,1.02,pale),('coat_red',.82,.37,.80,red)]
profiles={
 'coat_0':[(444,1125,1145),(456,1113,1165),(495,1098,1167),(543,1090,1160),(568,1098,1158),(646,1095,1159)],
 'coat_1':[(444,1150,1167),(450,1143,1179),(475,1132,1185),(521,1135,1187),(600,1131,1192),(656,1137,1198)],
 'coat_2':[(434,1202,1214),(450,1189,1226),(481,1178,1231),(538,1179,1230),(596,1170,1235),(654,1180,1228)],
 'coat_3':[(446,1218,1230),(467,1205,1245),(513,1201,1245),(576,1194,1240),(659,1201,1236)],
 'coat_4':[(445,1262,1277),(461,1246,1284),(503,1241,1281),(559,1229,1276),(636,1220,1269),(687,1206,1248)],
 'coat_red':[(454,1285,1294),(473,1280,1306),(510,1270,1317),(519,1272,1304),(578,1268,1300),(631,1260,1281)]}
def on_garment_plane(uv,center,depth=0):
 ray=np.r_[(np.array(uv)-PP)/F,1]@R;return C+ray*(np.dot(n,center-C)/np.dot(n,ray))+n*depth
for e,fraction,width,length,material in garment_data:
 center=ra+(rb-ra)*fraction;center[2]-=.12
 # Profiles include short shoulder rise, sleeves and rounded hem. Mesh uses rows for actual cloth topology.
 vs=[];fs=[];nx=12;nz=22
 for j in range(nz+1):
  v=j/nz;z=center[2]-length*v;half=width*(.31 if v<.08 else .58 if v<.28 else .44 if v<.80 else .46)
  for i in range(nx+1):
   u=i/nx*2-1;zlocal=z+(.05*(1-abs(u)) if v<.1 else .014*math.sin(i*.9) if v>.95 else 0);depth=.009*math.sin(i*1.4+j*.11)+.008*math.cos(j*.45+i*.2)
   if version>=2:
    prof=np.array(profiles[e]);py=prof[0,0]+v*(prof[-1,0]-prof[0,0]);xl=np.interp(py,prof[:,0],prof[:,1]);xr=np.interp(py,prof[:,0],prof[:,2]);px=xl+(xr-xl)*i/nx;p=on_garment_plane([px,py],center,-.035+depth)
   else:p=center+axis*u*half+n*(-.035+depth);p[2]=zlocal
   vs.append(p.tolist())
 for j in range(nz):
  for i in range(nx):a=j*(nx+1)+i;fs.extend([(a,a+1,a+nx+2),(a,a+nx+2,a+nx+1)])
 o=mesh(e,vs,fs,material,.0018);record(e,'garment',.87,'observed hanging clothes; hidden folds and seams estimated')
 for poly in o.data.polygons:poly.use_smooth=True
 mod=o.modifiers.new('smooth_fabric','SUBSURF');mod.levels=1
 if version>=2:
  midline=[np.array(vs[j*(nx+1)+nx//2])-n*.004 for j in range(2,nz+1)];curve(e,midline,.0013,black if material!=darkcloth else teal)
  # Folded collar edges, placed on the actual garment neckline.
  collar=[np.array(vs[0]),np.array(vs[nx//2])+[0,0,-.02],np.array(vs[nx])];curve(e,collar,.004,material)
 hook=center+[0,0,.1];curve('hangers',[hook-axis*.15+[0,0,-.06],hook+[0,0,.0],hook+axis*.15+[0,0,-.06]],.003,black);curve('hangers',[hook,hook+[0,0,.05],hook+axis*.02+[0,0,.08],hook+axis*.035+[0,0,.04]],.0025,metal)
 if e=='coat_red':(OUT/'cloth_rest.json').write_text(json.dumps(dict(entity=e,points_world=vs,elements=fs,pinned_vertices=list(range(nx+1))),indent=2))
# Ribbed black cabinet: observed envelope, function deliberately left unassigned.
cabz=.735;cabtop=[inv(p,z=cabz) for p in [[1238,635],[1456,668],[1524,754],[1216,705]]];bot=[inv(p,z=.025) for p in [[1199,883],[1430,942],[1448,1080],[1164,994]]]
cabfaces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(3,0,4,7)]
if version<3:cabfaces.append((2,3,7,6))
mesh('cabinet', [p.tolist() for p in bot+cabtop],cabfaces,black,0,.006)
if version>=3:
 ctr=np.mean(bot,axis=0)
 for p in bot:
  p=p*.90+ctr*.10;box('cabinet',(p[0],p[1],.015),(.032,.032,.03),black,.004)
frontleft=cabtop[3];frontright=cabtop[2];bottomleft=bot[3];bottomright=bot[2]
if version<3:
 for j in range(6):
  f=(j+.65)/6.7;a=frontleft*(1-f)+bottomleft*f;b=frontright*(1-f)+bottomright*f;aa=a*.89+b*.11;bb=a*.11+b*.89;curve('cabinet',[aa,[*(aa*.5+bb*.5)[:2],(aa[2]+bb[2])/2+.012],bb],.006,black)
else:
 # Actual shallow pressed grooves with rounded ends, rather than protruding drawer handles.
 vtx=[];faces=[];nu=110;nv=150;ww=np.linalg.norm(frontright-frontleft);hh=np.linalg.norm(bottomleft-frontleft);normal=np.cross(frontright-frontleft,bottomleft-frontleft);normal/=np.linalg.norm(normal)
 if np.dot(normal,C-frontleft)<0:normal=-normal
 for j in range(nv+1):
  v=j/nv
  for i in range(nu+1):
   u=i/nu;p=frontleft*(1-u)*(1-v)+frontright*u*(1-v)+bottomright*u*v+bottomleft*(1-u)*v;dep=0
   for k in range(6):
    center=(k+.85)/7;du=max(.14-u,0,u-.86)*ww;dv=(v-center)*hh;distance=math.sqrt(du*du+dv*dv);rad=.019
    if distance<rad:dep=max(dep,.004*(.5+.5*math.cos(math.pi*distance/rad)))
   vtx.append((p-normal*dep).tolist())
 for j in range(nv):
  for i in range(nu):a=j*(nu+1)+i;faces.append((a,a+1,a+nu+2,a+nu+1))
 panel=mesh('cabinet',vtx,faces,black)
 for face in panel.data.polygons:face.use_smooth=True
# Right carry loop and small blank stickers; unreadable source text is not invented.
a=cabtop[2]*.93+cabtop[1]*.07;curve('cabinet',[a+[0,0,-.04],a+[.025,0,-.06],a+[.026,0,-.19],a+[0,0,-.22]],.008,black)
for px,py in [(1246,716),(1281,649)]:p=inv([px,py],z=cabz if py<680 else .69);box('cabinet',p,(.08,.002,.021),wall)
# Small wastebasket, with real thin shell and uneven liner rim.
bc=inv([667,739],z=.012);br=.095;bh=.23
vs=[];fs=[];N=48
for j in range(2):
 for i in range(N):ang=2*math.pi*i/N;rr=br*(.75+.25*j);vs.append((bc[0]+rr*math.cos(ang),bc[1]+rr*math.sin(ang),.012+bh*j))
for i in range(N):fs.append((i,(i+1)%N,(i+1)%N+N,i+N))
mesh('wastebasket',vs,fs,black,.002);curve('wastebasket',[vs[N+i]+np.array([0,0,.008*math.sin(i*3)]) for i in range(N)]+[vs[N]],.003,black)
if version>=3:rod('wastebasket',(bc[0],bc[1],.001),(bc[0],bc[1],.014),br*.75,black,48)
# Cleaning cart visible at left: independently authored frame, bins, handles, caution sign, caster wheels.
cartbase=inv([170,964],z=.10);cartyaw=-.1;cx,cy=cartbase[:2];cartw=.61;cartd=.48
box('cleaning_cart',(cx,cy,.13),(cartw,.52,.04),metal,.008)
for x in [cx-cartw/2,cx+cartw/2]:
 for y in [cy-cartd/2,cy+cartd/2]:
  rod('cleaning_cart',(x,y,.06),(x,y,.16),.014,metal);o=rod('cleaning_cart',(x-.015,y,.055),(x+.015,y,.055),.04,black,20)
for x in [cx-.27,cx+.27]:rod('cleaning_cart',(x,cy+.2,.15),(x,cy+.2,1.0),.018,metal)
box('cleaning_cart',(cx,cy+.12,.95),(.60,.31,.025),metal,.008)
for k,m in enumerate([bin_green,black]):
 x=cx-.15+k*.29
 if version<2:
  box('cleaning_cart',(x,cy-.04,.43),(.27,.37,.49),m,.028);box('cleaning_cart',(x,cy-.04,.68),(.29,.39,.035),black,.02)
 else:
  uvbin=([[105,771],[200,748],[244,879],[142,928]] if k==0 else [[213,747],[300,725],[337,854],[252,884]])
  front=[inv(uv,z=.59 if i<2 else .19) for i,uv in enumerate(uvbin)];back=[v+[0,.23,0] for v in front];mesh('cleaning_cart',[v.tolist() for v in front+back],[(0,1,2,3),(0,4,5,1),(1,5,6,2),(3,2,6,7),(0,3,7,4)],m,0,.012)
  # White label frame and recycling triangle lie on the visible front panel.
  def bf(u,v):return front[0]*(1-u)*(1-v)+front[1]*u*(1-v)+front[2]*u*v+front[3]*(1-u)*v+np.array([0,-.003,0])
  curve('cleaning_cart',[bf(.15,.15),bf(.85,.15),bf(.85,.72),bf(.15,.72),bf(.15,.15)],.0015,wall)
  curve('cleaning_cart',[bf(.36,.33),bf(.5,.22),bf(.66,.34),bf(.36,.33)],.002,wall)
  for v in [.43,.48,.56]:curve('cleaning_cart',[bf(.28,v),bf(.71,v)],.0015,wall)
box('warning_sign',(cx,cy+.04,.79),(.31,.035,.31),yellow,.008)
for i in range(3):box('warning_sign',(cx,cy+.019,.76+i*.032),(.17,.002,.007),black)
curve('cleaning_tools',[(cx+.19,cy,.71),(cx+.15,cy,1.08),(cx+.14,cy,1.15)],.010,black)
if version>=2:
 # Replace the generic cart envelope with the photographed trapezoidal tray and visible paired bins.
 for o in list(bpy.data.objects):
  if o.get('entity_id') in ['cleaning_cart','warning_sign']:bpy.data.objects.remove(o,do_unlink=True)
 cart_top=[inv(p,z=.93) for p in [[0,560],[179,548],[226,591],[40,625]]]
 cart_base=[inv(p,z=.10) for p in [[110,967],[325,876],[370,901],[153,1023]]]
 mesh('cleaning_cart',cart_top,[(0,1,2,3)],metal,.017,.004);mesh('cleaning_cart',cart_base,[(0,1,2,3)],metal,.025,.004)
 for a,b in [([12,575],[156,1013]),([202,586],[370,908])]:rod('cleaning_cart',inv(a,z=.93),inv(b,z=.095),.020,metal)
 for p in cart_base:
  p=p.copy();p[2]=.038;rod('cleaning_cart',p+[-.014,0,0],p+[.014,0,0],.033,black,20)
 for k,m in enumerate([bin_green,black]):
  uvbin=([[105,771],[200,748],[244,879],[142,928]] if k==0 else [[213,747],[300,725],[337,854],[252,884]])
  front=[inv(uv,z=.59 if i<2 else .19) for i,uv in enumerate(uvbin)];back=[v+[-.15,.045,0] for v in front];mesh('cleaning_cart',[v.tolist() for v in front+back],[(0,1,2,3),(0,4,5,1),(1,5,6,2),(3,2,6,7),(0,3,7,4),(4,7,6,5)],m,0,.009)
  def bfront(u,v):return front[0]*(1-u)*(1-v)+front[1]*u*(1-v)+front[2]*u*v+front[3]*(1-u)*v+np.array([.002,-.002,0])
  for points in [[(.15,.15),(.85,.15),(.85,.74),(.15,.74),(.15,.15)],[(.35,.35),(.5,.22),(.67,.35),(.35,.35)],[(.27,.46),(.73,.46)],[(.27,.52),(.73,.52)],[(.27,.58),(.73,.58)]]:
   label=curve('cleaning_cart',[bfront(u,v) for u,v in points],.0015,wall)
   for p in label.data.splines[0].bezier_points:p.handle_left_type='VECTOR';p.handle_right_type='VECTOR'
 sign=[inv(p,z=.80 if i<2 else .53) for i,p in enumerate([[56,614],[177,603],[197,706],[74,720]])];mesh('warning_sign',sign,[(0,1,2,3)],yellow,.007,.003)
 for v in [.37,.47,.57]:
  a=sign[0]*(.8*(1-v))+sign[1]*(.2*(1-v))+sign[2]*(.2*v)+sign[3]*(.8*v);b=sign[0]*(.2*(1-v))+sign[1]*(.8*(1-v))+sign[2]*(.8*v)+sign[3]*(.2*v);rod('warning_sign',a+[.002,-.002,0],b+[.002,-.002,0],.004,black)
 rod('cleaning_tools',inv([158,500],z=1.05),inv([234,699],z=.66),.010,black)
 # Crumpled liner on the top tray is a visible source detail, not a new scene object.
 liner=mat('cart_liner_gray_plastic',(.31,.33,.30),.42);vv=[];ff=[]
 for j in range(7):
  for i in range(13):
   u=.08+.82*i/12;v=.08+.60*j/6;p=cart_top[0]*(1-u)*(1-v)+cart_top[1]*u*(1-v)+cart_top[2]*u*v+cart_top[3]*(1-u)*v;p[2]+=.016+.008*math.sin(i*2+j*1.9);vv.append(p.tolist())
 for j in range(6):
  for i in range(12):a=j*13+i;ff.append((a,a+1,a+14,a+13))
 mesh('cart_liner',vv,ff,liner,.0007)
# Cropped foreground glass partition/door edge observed on the left of the original.
if version>=2:
 edge=inv([205,1275],z=0);leaf_width=.88
 box('left_foreground_frame',(edge[0],edge[1],1.4),(.018,.03,2.8),black,.003)
 box('left_foreground_glass',(edge[0]-leaf_width/2,edge[1]+.008,1.35),(leaf_width,.008,2.7),glass,.003)
 box('left_foreground_frame',(edge[0]-.045,edge[1]-.045,.25),(.13,.055,.04),metal,.003)
 record('left_foreground_frame','doorway_frame',.75,'visible dark cropped left edge; vertical placement fitted; unseen mounting and full leaf width inferred')
# Door at near right, visible thin leaf / silver handle. Main doorway completion is an explicit hypothesis.
doorx=xmax-.15 if version<2 else 4.08;doory=-2.25 if version<2 else -1.83;doorw=.84;doorh=2.18
box('door_leaf',(doorx,doory-doorw/2,doorh/2),(.009,doorw,doorh),glass,.003)
for y in [doory,doory-doorw]:rod('door_leaf',(doorx,y,.02),(doorx,y,doorh),.008,metal)
if version<2:rod('door_leaf',(doorx-.035,doory-doorw+.10,.91),(doorx-.035,doory-doorw+.28,.91),.014,metal)
if version>=2:
 handle=inv([1650,885],x=doorx-.035);rod('door_leaf',handle,handle+[0,-.16,0],.014,metal)
 for k in range(2):rod('door_leaf',handle+[0,-.06-k*.014,-.012],handle+[-.01,-.09-k*.014,-.10],.003,metal)
record('ceiling_luminaire','ceiling_lamp',.1,'unobserved completion hypothesis: ceiling panel, switched off in daylight reconstruction')
box('ceiling_luminaire',(2,-2.1,height-.013),(.59,.59,.025),wall,.003)
# Camera and illumination.
bpy.ops.object.camera_add(location=C);cam=bpy.context.object;cam.name='source_camera';cam.rotation_euler=(Matrix(R.tolist()).transposed()@Matrix(((1,0,0),(0,-1,0),(0,0,-1)))).to_euler();cam.data.sensor_fit='HORIZONTAL';cam.data.sensor_width=36;cam.data.lens=F*36/W;cam.data.shift_x=(W/2-PP[0])/W;cam.data.shift_y=(PP[1]-H/2)/W;cam.data.clip_start=.01;sc.camera=cam
world=bpy.data.worlds.new('daylight_world');sc.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.76,1,1);world.node_tree.nodes['Background'].inputs[1].default_value=(.45 if version<3 else 2.0) if mode=='lit' else .8
def light(name,kind,pos,energy,color,size,target):
 data=bpy.data.lights.new(name,kind);data.energy=energy;data.color=color
 if kind=='AREA':data.shape='RECTANGLE';data.size=size;data.size_y=size
 obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=pos;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();return obj
if mode=='neutral':light('neutral_calibration_area','AREA',(2,-2,2.65),450,(1,1,1),3,(2,-1,0))
else:
 light('window_sky','AREA',(2,1.5,2.4),320 if version<3 else 1800,(.80,.88,1),4,(2,-2,1));sun=light('daylight_sun','SUN',(5,5,7) if version<3 else (3,6,9),2.7 if version<3 else 3.2,(1,.94,.79),1,(-1,-3,0) if version<3 else (3,-1,0));sun.data.angle=.015
 light('left_window_sky','AREA',(-1,-.6,2),70,(.82,.9,1),1,(2,-.6,.5))
# Entity roots / bounds and collision recipes use world coordinates, root at identity.
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
for e,data in entities.items():
 objs=[o for o in bpy.data.objects if o.get('entity_id')==e and o.type in ['MESH','CURVE']];verts=[]
 for o in objs:
  ev=o.evaluated_get(deps);me=ev.to_mesh();verts.extend([list(o.matrix_world@v.co) for v in me.vertices]);ev.to_mesh_clear()
 a=np.array(verts);lo=a.min(axis=0);hi=a.max(axis=0);data.update(position=((lo+hi)/2).tolist(),dimensions=np.maximum(hi-lo,.001).tolist())
 if e in proxy:data['parameters']['collision_proxies']=proxy[e]
 # Existing first mesh names are retained for shell checks; static world mesh coordinates are explicit.
 if e not in ['floor','ceiling','wall_back','wall_front','wall_left','wall_right']:
  old=bpy.data.objects.get(e)
  if old:old.name=e+'__part'
  rt=bpy.data.objects.new(e,None);bpy.context.collection.objects.link(rt);rt['entity_id']=e
  for o in objs:o.parent=rt
scene=dict(schema_version='real2sim.scene/1.0',case_id='utility_single_external_example',branch='A',units='m',up_axis='Z',room=room,camera=cal,objects=list(entities.values()),assumptions=['camera and visible window endpoints fitted to source; actual room-right corner is outside those endpoints','opaque room-right return width 0.68m inferred','unobserved front wall and ceiling lamp are completion hypotheses','external building and foliage schematic, not surveyed','black ribbed item function unconfirmed','all dimensions estimated in ceiling-height gauge; no metric truth'],model_version=version,render_mode=mode,structure=furniture_structure if version>=4 else None)
(OUT/'scene.json').write_text(json.dumps(scene,indent=2));(OUT/'construction_parameters.json').write_text(json.dumps(dict(calibration=cal,table_height=th,room=room,rack_rail=[ra.tolist(),rb.tolist()],source_coordinates=top_uv if version<4 else None,version=version,mode=mode),indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model.blend'));sc.render.filepath=str(OUT/'preview.png');bpy.ops.render.render(write_still=True) if not os.environ.get('R2S_SKIP_PREVIEW') else None
print('CASE_MODEL_WRITTEN',OUT)
