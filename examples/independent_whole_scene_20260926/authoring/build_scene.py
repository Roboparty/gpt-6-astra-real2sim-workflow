"""Independent reconstruction authored 2026-09-26 from the authorized photo.
No prior scene, fitted parameter file or external furniture mesh is consumed.
"""
import bpy,sys,json,math,random,shutil,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
import numpy as np
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow/r2s'))
fit=json.loads((R/'authoring/fit.json').read_text());rc=json.loads((R/'authoring/room.json').read_text());P=fit['parameters'];room=rc['room']
bed_revision=json.loads((R/'authoring/bed_revision.json').read_text()) if (R/'authoring/bed_revision.json').exists() else None
if bed_revision:
 _,_,_,P['bed_width'],P['bed_rail_top'],P['bed_head_top'],_=bed_revision['parameters']
state=json.loads((R/'case/runs/state.json').read_text());out=Path(state['stages']['agent_model']['directory']);obsdir=Path(state['stages']['agent_observe']['directory'])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.unit_settings.system='METRIC';sc.render.engine='CYCLES';sc.cycles.samples=40;sc.cycles.use_denoising=True;sc.cycles.max_bounces=8;sc.render.resolution_percentage=100
sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=0;sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
sc.world=bpy.data.worlds.new('day_world');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.65,.73,.8,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
def mat(name,color,rough=.7,metal=0,trans=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Transmission Weight'].default_value=trans;return m
white=mat('painted_ivory',(.72,.73,.69));wall=mat('wall_paint',(.77,.78,.73),.84);wood=mat('honey_wood',(.43,.27,.12),.6);dark=mat('window_charcoal',(.016,.021,.02),.48);blind=mat('blind_taupe',(.30,.31,.27),.9);carpet=mat('carpet_greytaupe',(.14,.135,.115),.98);cloth=mat('botanical_cotton',(.67,.73,.69),.95);sheet=mat('bluegrey_sheet',(.28,.39,.39),.95);glass=mat('window_glass',(.90,.96,.96),.055,0,1);board=mat('board_glass',(.66,.72,.66),.12,0,.08);metal=mat('brushed_steel',(.42,.43,.40),.4,.8);ivory=mat('fixture_white',(.78,.77,.7),.6)
def own(o,e):o['entity_id']=e;return o
def cube(name,center,size,m,e,bev=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=center);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if m:o.data.materials.append(m)
 own(o,e)
 if bev:
  mod=o.modifiers.new('softened_edges','BEVEL');mod.width=bev;mod.segments=3
  o.modifiers.new('weighted_normals','WEIGHTED_NORMAL')
 return o
def join(name,objs,e):
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();o=objs[0];o.name=name;own(o,e);return o
def ellipsoid(name,loc,scale,m,e):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);own(o,e)
 for p in o.data.polygons:p.use_smooth=True
 o.data.uv_layers.active.name='FabricUV';return o
def uvcloth(o):
 if o.data.uv_layers:o.data.uv_layers.active.name='FabricUV'
 return o
xl,xr,yf,yb,h=[room[k] for k in ['x_min','x_max','y_min','y_max','height']];xm=(xl+xr)/2;ym=(yf+yb)/2;t=room['thickness']
cube('floor',(xm,ym,-.06),(xr-xl,yb-yf,.12),carpet,'floor')
cube('ceiling',(xm,ym,h+.06),(xr-xl,yb-yf,.12),wall,'ceiling')
cube('wall_back',(xm,yb+.06,h/2),(xr-xl,.12,h),wall,'wall_back')
cube('wall_front',(xm,yf-.06,h/2),(xr-xl,.12,h),wall,'wall_front')
cube('wall_right',(xr+.06,ym,h/2),(.12,yb-yf,h),wall,'wall_right')
wi=rc['window'];wy0,wy1,wz0,wz1=[wi[k] for k in ['y0','y1','bottom','top']]
shell=[]
for name,cy,sy,cz,sz in [('near',(yf+wy0)/2,wy0-yf,h/2,h),('far',(wy1+yb)/2,yb-wy1,h/2,h),('sill',(wy0+wy1)/2,wy1-wy0,wz0/2,wz0),('lintel',(wy0+wy1)/2,wy1-wy0,(wz1+h)/2,h-wz1)]:shell.append(cube('left_'+name,(xl-.06,cy,cz),(.12,sy,sz),wall,'wall_left'))
join('wall_left',shell,'wall_left')
# Continuous skirting remains in room, without pretending hidden segments measured.
cube('back_skirt',(xm,yb-.012,.04),(xr-xl,.026,.08),white,'wall_back',.003)
cube('left_sill',(xl+.06,(wy0+wy1)/2,wz0-.015),(.16,wy1-wy0,.055),white,'window',.006)
ys=[wy0,rc['blinds'][0]['y1']+.012,rc['blinds'][1]['y1']+.012,wy1]
for i,y in enumerate(ys):cube(f'window_mullion_{i}',(xl+.01,y,(wz0+wz1)/2),(.065,.042,wz1-wz0),dark,'window',.003)
for z in [wz0,.99,wz1]:cube(f'window_horizontal_{z:.2f}',(xl+.01,(wy0+wy1)/2,z),(.065,wy1-wy0,.045),dark,'window',.003)
for i in range(15):cube(f'safety_bar_{i}',(xl+.03,wy0+.07+(wy1-wy0-.14)*i/14,(wz0+.99)/2),(.025,.018,.99-wz0),dark,'window',.002)
for i,(a,b) in enumerate(zip(ys,ys[1:])):cube(f'glass_{i}',(xl-.02,(a+b)/2,(wz0+wz1)/2),(.008,b-a-.04,wz1-wz0-.025),glass,'window')
for i,b in enumerate(rc['blinds']):
 y=(b['y0']+b['y1'])/2;z=(b['bottom']+b['top'])/2
 uvcloth(cube(f'blind_panel_{i}',(xl+.07,y,z),(.009,b['y1']-b['y0'],b['top']-b['bottom']),blind,'blinds',.002))
 # The thin hem stays part of the single panel edge, not an extra relief strip.
 curve=bpy.data.curves.new('bead_loop','CURVE');curve.dimensions='3D';curve.bevel_depth=.002;curve.bevel_resolution=2;s=curve.splines.new('POLY');s.points.add(79)
 for j in range(80):
  a=2*math.pi*j/79;s.points[j].co=(xl+.11,b['y1']-.015+.012*math.sin(a),(b['top']+b['bottom']-.28)/2+(b['top']-b['bottom']+.28)/2*math.cos(a),1)
 o=bpy.data.objects.new(f'blind_chain_{i}',curve);bpy.context.collection.objects.link(o);o.data.materials.append(ivory);own(o,'blinds')
# Original seam depth is uncertain: retain a continuous ceiling and use flat
# appearance linework at the material stage, not unsupported raised strips.
def source_on_plane(u,v,axis,value):
 c=fit['camera'];C=np.array(c['position']);d=np.array(c['rotation_world_to_cv']).T@np.array([(u-851)/c['focal_px'],(v-638)/c['focal_px'],1]);return C+d*(value-C[axis])/d[axis]
panel_spec=json.loads((obsdir/'observation.json').read_text()).get('ceiling_white_panel')
if panel_spec:
 points=[source_on_plane(u,v,2,h-.0008) for u,v in panel_spec['source_polygon_xy']]
 if np.cross(points[1]-points[0],points[2]-points[0])[2]>0:points.reverse()
 me=bpy.data.meshes.new('flush_insert_surface');me.from_pydata(points,[],[(0,1,2,3)]);me.update();o=bpy.data.objects.new('observed_ceiling_insert',me);bpy.context.collection.objects.link(o);own(o,'ceiling_fixtures');o['interpretation']='Appearance-only flush white insert; possible diffuser, powered state unknown';me.materials.append(mat('ceiling_insert_white',(.92,.94,.90),.65))
vx,vy,_=source_on_plane(1352,126,2,h-.02)
vent=cube('ceiling_vent',(vx,vy,h-.016),(.56,.43,.025),ivory,'ceiling_fixtures',.006)
for i in range(15):cube(f'vent_slot_{i}',(vx,vy-.19+i*.027,h-.031),(.50,.009,.005),dark,'ceiling_fixtures')
fx,fy,_=source_on_plane(1632,43,2,h-.025);ellipsoid('round_ceiling_fitting',(fx,fy,h-.025),(.07,.07,.022),ivory,'ceiling_fixtures')
fx,fy,_=source_on_plane(1083,130,2,h-.04);cube('sprinkler_mount',(fx,fy,h-.04),(.025,.025,.08),metal,'ceiling_fixtures',.004)
cube('inferred_ceiling_lamp',(1.5,-1.75,h-.025),(.5,.5,.045),ivory,'ceiling_fixtures',.01)
# Plate reflectance uses dielectric glass, never painted window highlights.
b=rc['board'];cube('wall_board',((b['x0']+b['x1'])/2,yb-.025,(b['z0']+b['z1'])/2),(b['x1']-b['x0'],.008,b['z1']-b['z0']),board,'reflective_board',.004)
# Three independently modelled furniture frames.
assemblies=[]
def assembly(entity,parts,joints,supports,lmmap):
 for id,o in parts.items():o['furniture_id']=entity;o['part_id']=id
 lms=[]
 for row in fit['correspondences']:
  if row['id'].startswith(entity+'_'):
   v={k:row[k] for k in ['id','world','uv']};v.update(visibility='observed',part=lmmap[row['id'].removeprefix(entity+'_')]);lms.append(v)
 assemblies.append(dict(entity=entity,frame={'yaw_rad':0},parts=[dict(id=k,object=o.name) for k,o in parts.items()],joints=[dict(parts=[a,b],anchor_world=list(v),tolerance_m=.008) for a,b,v in joints],floor_supports=[dict(part=x,plane_z=0,tolerance_m=.006) for x in supports],source_observation_ids=[v['id'] for v in lms],fit={'landmarks':lms}))
bw=P['bed_width'];bz=P['bed_rail_top'];hz=P['bed_head_top'];bedparts={};bedj=[]
bedparts['foot_frame']=cube('bed_foot_frame',(0,0,bz-.055),(bw+.03,.065,.11),wood,'bed',.005)
for name,x,y in [('left_foot',-bw/2,0),('right_foot',bw/2,0),('left_head_leg',-bw/2,2),('right_head_leg',bw/2,2)]:
 bedparts[name]=cube('bed_'+name,(x,y,bz/2),(.052,.065,bz),wood,'bed',.004)
 if y==0:bedj.append((name,'foot_frame',(x,y,bz-.04)))
for name,x in [('left_rail',-bw/2),('right_rail',bw/2)]:
 bedparts[name]=cube('bed_'+name,(x,1,bz-.05),(.04,2,.1),wood,'bed',.004)
 for leg,y in [(('left_foot' if x<0 else 'right_foot'),.02),(('left_head_leg' if x<0 else 'right_head_leg'),1.98)]:bedj.append((name,leg,(x,y,bz-.04)))
 bedj.append((name,'foot_frame',(x,.015,bz-.04)))
headobjs=[cube('head_back',(0,2.018,(hz+.23)/2),(bw+.045,.045,hz-.23),wood,'bed',.008),cube('head_shelf',(0,1.965,hz-.01),(bw+.06,.13,.026),wood,'bed',.007)]
headobjs.append(cube('head_cubby_shelf',(0,1.957,hz-.115),(bw+.025,.145,.026),wood,'bed',.004))
for idx,x in enumerate([-bw*.245,bw*.245]):
 panel=cube('head_inset',(x,1.991,.59),(bw*.46,.018,.25),wood,'bed',.003);group=panel.vertex_groups.new(name=f'head_panel_{idx}');group.add(list(range(len(panel.data.vertices))),1,'REPLACE');headobjs.append(panel)
headobjs.append(cube('head_center_divider',(0,1.972,.58),(.025,.03,.27),wood,'bed',.003))
bedparts['headboard']=join('bed_headboard',headobjs,'bed')
for name,x in [('left_head_leg',-bw/2),('right_head_leg',bw/2)]:bedj.append(('headboard',name,(x,2.015,bz-.025)))
slats=[cube(f'bed_slat_{i}',(0,.10+i*.15,bz-.015),(bw,.06,.025),wood,'bed') for i in range(13)]
bedparts['slats']=join('bed_slats',slats,'bed')
for name,x in [('left_rail',-bw/2+.012),('right_rail',bw/2-.012)]:bedj.append(('slats',name,(x,.10,bz-.022)))
bedparts['mattress']=uvcloth(cube('bed_mattress',(0,1.0,bz+.075),(bw+.01,1.98,.15),sheet,'bed',.045));bedj.append(('mattress','slats',(0,.1,bz)))
# Observed blue-grey fitted cloth hangs over the long rails; it is not merely
# the mattress's smooth side face. Keep the front wooden rail exposed.
for side,label in [(-1,'left'),(1,'right')]:
 sv=[];sf=[];sn,sm=96,20
 for j in range(sn+1):
  y=.04+1.89*j/sn
  for i in range(sm+1):
   v=i/sm;wave=(.004*math.sin(29*y)+.003*math.sin(63*y))*v*v;x=side*(bw/2+.007+.040*v*v+wave);z=bz+.115-.18*v+(.006*math.sin(12*y)+.004*math.sin(37*y))*v*v;sv.append((x,y,z))
 for j in range(sn):
  for i in range(sm):
   a=j*(sm+1)+i;face=(a,a+1,a+sm+2,a+sm+1);sf.append(face if side>0 else tuple(reversed(face)))
 me=bpy.data.meshes.new('fitted_sheet_'+label);me.from_pydata(sv,[],sf);me.update();o=bpy.data.objects.new('bed_sheet_'+label,me);bpy.context.collection.objects.link(o);own(o,'bed');me.materials.append(sheet);uv=me.uv_layers.new(name='FabricUV')
 for poly in me.polygons:
  poly.use_smooth=True
  for li in poly.loop_indices:
   vi=me.loops[li].vertex_index;uv.data[li].uv=((vi//(sm+1))/sn*1.89,(vi%(sm+1))/sm*.18)
 sol=o.modifiers.new('sheet_thickness','SOLIDIFY');sol.thickness=.0015;bedparts['sheet_'+label]=o;bedj.append(('sheet_'+label,'mattress',(side*(bw/2+.007),1.0,bz+.115)))
# Broad asymmetrical drape, generated in fabric coordinates, closed by Solidify.
nx,ny=112,192;verts=[];faces=[];qwidth=bw+.32;qlength=1.8+math.pi*.01+.45+.12
wrinkle_rng=random.Random(917);creases=[(wrinkle_rng.uniform(-bw*.51,bw*.51),wrinkle_rng.uniform(.02,1.8),wrinkle_rng.uniform(0,math.tau),wrinkle_rng.uniform(.007,.022),wrinkle_rng.uniform(.045,.28),wrinkle_rng.uniform(.0015,.006),wrinkle_rng.uniform(-2,2)) for _ in range(145)]
def edge_drape(distance,radius):
 if distance<=0:return 0,0
 if distance<math.pi*radius/2:return radius*math.sin(distance/radius),radius*(1-math.cos(distance/radius))
 return radius,radius+distance-math.pi*radius/2
for j in range(ny+1):
 v=j/ny;flat_y=-.12+qlength*v;fold_lift=0
 if flat_y<=1.8:y=flat_y
 elif flat_y<1.8+math.pi*.01:
  a=(flat_y-1.8)/.01;y=1.8+.01*math.sin(a);fold_lift=.01*(1-math.cos(a))
 else:y=1.8-(flat_y-1.8-math.pi*.01);fold_lift=.02
 front_offset,front_drop=edge_drape(max(0,-flat_y),.035)
 if flat_y<0:y=-front_offset
 for i in range(nx+1):
  u=i/nx;flat_x=(u-.5)*qwidth;edge=bw/2+.005;offset,side_drop=edge_drape(max(0,abs(flat_x)-edge),.065);x=math.copysign(edge+offset,flat_x) if abs(flat_x)>edge else flat_x
  fold=.001*math.sin(39*x+12*y)+.001*math.sin(31*y+6*x)
  for cx,cy,a,width,length,amp,curve in creases:
   d=(x-cx)*math.cos(a)+(y-cy)*math.sin(a);along=-(x-cx)*math.sin(a)+(y-cy)*math.cos(a);d+=curve*along*along;fold+=amp*math.exp(-(d/width)**2-(along/length)**4)
  fold=max(0,fold)*(1-math.exp(-((x/.15)**2+((y-1.63)/.12)**2)))
  z=bz+.159+fold+fold_lift-math.hypot(side_drop,front_drop)
  verts.append((x,y,z))
for j in range(ny):
 for i in range(nx):a=j*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
mesh=bpy.data.meshes.new('draped_duvet_mesh');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('bed_duvet',mesh);bpy.context.collection.objects.link(o);own(o,'bed');o.data.materials.append(cloth)
uv=mesh.uv_layers.new(name='FabricUV')
for poly in mesh.polygons:
 poly.use_smooth=True
 for li in poly.loop_indices:
  vi=mesh.loops[li].vertex_index;uv.data[li].uv=((vi%(nx+1))/nx,(vi//(nx+1))/ny)
sol=o.modifiers.new('cloth_thickness','SOLIDIFY');sol.thickness=.009;sol.offset=-1
bedparts['duvet']=o
contact=min((v for v in verts if abs(v[0])<bw*.35 and .15<v[1]<1.6),key=lambda v:v[2]);bedj.append(('duvet','mattress',(contact[0],contact[1],contact[2]-.009)))
# Sewn pillow volume with a shared perimeter seam and two curved cloth panels.
pn,pm=48,28;pv=[];pf=[];p_uv=[];index={};pw=bw*.63;pd=.40;pbase=bz+.188
for layer in [0,1]:
 for j in range(pm+1):
  v=j/pm
  for i in range(pn+1):
   u=i/pn;boundary=i in [0,pn] or j in [0,pm];key=(i,j,0 if boundary else layer)
   if key in index:continue
   x=(u-.5)*pw*(1-.06*(2*v-1)**8);y=1.63+(v-.5)*pd*(1-.06*(2*u-1)**8);bulge=(max(0,math.sin(math.pi*u)*math.sin(math.pi*v)))**.55
   z=pbase+.06+(1 if layer==0 else -1)*.06*bulge
   if layer==0:z+=.0018*math.sin(27*u+13*v)*bulge
   index[key]=len(pv);pv.append((x,y,z));p_uv.append((u,v))
for layer in [0,1]:
 def idx(i,j):return index[(i,j,0 if i in [0,pn] or j in [0,pm] else layer)]
 for j in range(pm):
  for i in range(pn):
   f=(idx(i,j),idx(i+1,j),idx(i+1,j+1),idx(i,j+1));pf.append(f if layer==0 else tuple(reversed(f)))
me=bpy.data.meshes.new('sewn_pillow_mesh');me.from_pydata(pv,[],pf);me.update();pillow=bpy.data.objects.new('bed_pillow',me);bpy.context.collection.objects.link(pillow);own(pillow,'bed');me.materials.append(cloth);layer=me.uv_layers.new(name='FabricUV')
for poly in me.polygons:
 poly.use_smooth=True
 for li in poly.loop_indices:layer.data[li].uv=p_uv[me.loops[li].vertex_index]
bedparts['pillow']=pillow;bedj.append(('pillow','duvet',(0,1.63,pbase)))
# Small decorative toys are independent soft volumes with observed pastel palette.
toycolors=[(.79,.56,.59),(.7,.72,.58),(.7,.86,.83),(.26,.52,.65),(.65,.55,.72)]
for i in range(7):
 x=-bw*.37+i*bw*.115;m=mat(f'toy_color_{i}',toycolors[i%5],.94);z=hz-.070;o=ellipsoid(f'head_toy_{i}',(x,1.925,z),(.040,.034,.033),m,'bed');toy=[o]
 for side in [-1,1]:
  toy.append(ellipsoid('toy_ear',(x+side*.024,1.927,z+.024),(.013,.012,.015),m,'bed'))
  toy.append(ellipsoid('toy_eye',(x+side*.013,1.892,z+.005),(.004,.003,.004),dark,'bed'))
 o=join(f'head_toy_{i}',toy,'bed');bedparts[f'toy_{i}']=o;bedj.append((f'toy_{i}','headboard',(x,1.925,hz-.102)))
for i,x in enumerate([-bw*.46,bw*.46]):
 contact=min(verts,key=lambda v:(v[0]-x)**2+(v[1]-1.61)**2);z=contact[2]
 m=mat(f'pillow_toy_color_{i}',(.74,.58,.17),.98);o=ellipsoid(f'pillow_toy_{i}',(contact[0],contact[1],z+.065),(.065,.065,.065),m,'bed');pieces=[o]
 green=mat(f'plush_leaves_{i}',(.3,.46,.12),.96)
 for j in range(5):
  a=j*math.tau/5;pieces.append(ellipsoid('plush_leaf',(contact[0]+.033*math.cos(a),contact[1]+.033*math.sin(a),z+.129),(.017,.024,.030),green,'bed'))
 o=join(f'pillow_toy_{i}',pieces,'bed');bedparts[f'pillow_toy_{i}']=o;bedj.append((f'pillow_toy_{i}','duvet',contact))
assembly('bed',bedparts,bedj,['left_foot','right_foot','left_head_leg','right_head_leg'],{'foot_left_top':'foot_frame','foot_right_top':'foot_frame','foot_left_floor':'left_foot','foot_right_floor':'right_foot','head_left_top':'headboard','head_right_top':'headboard'})
if bed_revision:
 ox,oy,a,_,_,_,inset=bed_revision['parameters'];T=Matrix.Translation((ox,oy,0))@Matrix.Rotation(a,4,'Z')
 for o in bpy.data.objects:
  if o.get('entity_id')=='bed':o.matrix_world=T@o.matrix_world
 for joint in assemblies[-1]['joints']:joint['anchor_world']=list(T@Vector(joint['anchor_world']))
 for lm,point in zip(assemblies[-1]['fit']['landmarks'],bed_revision['world_points']):lm['world']=point
 assemblies[-1]['frame']['yaw_rad']=a
# Wardrobe official candidate dimensions, plain panel construction.
wx,wy=P['wardrobe_left_x'],P['wardrobe_front_y'];ww,wd,wh=.794,.565,2.01
pieces=[]
bodyheight=wh-.088;bodyz=.07+bodyheight/2
for name,loc,sz in [('left',(wx+.009,wy+wd/2,bodyz),(.018,wd,bodyheight)),('right',(wx+ww-.009,wy+wd/2,bodyz),(.018,wd,bodyheight)),('top',(wx+ww/2,wy+wd/2,wh-.009),(ww,wd,.018)),('base',(wx+ww/2,wy+wd/2,.035),(ww,wd,.07)),('back',(wx+ww/2,wy+wd-.007,bodyz),(ww-.036,.014,bodyheight)),('divider',(wx+ww/2,wy+(wd-.014)/2,bodyz),(.018,wd-.014,bodyheight))]:pieces.append(cube('wardrobe_'+name,loc,sz,white,'wardrobe',.0015))
wp={'carcass':join('wardrobe_carcass',pieces,'wardrobe')};wj=[]
for name,x,z,height in [('long_door',wx+ww*.25,1.037,1.936),('short_door',wx+ww*.75,1.293,1.424),('upper_drawer',wx+ww*.75,.444,.26),('lower_drawer',wx+ww*.75,.176,.26)]:
 wp[name]=cube('wardrobe_'+name,(x,wy-.006,z),(ww/2-.004,.02,height),white,'wardrobe',.002)
 wj.append((name,'carcass',(wx+.016 if 'long' in name else wx+ww-.016,wy+.003,z)))
 xhandle=(wx+ww*.46 if name=='long_door' else wx+ww*.54 if name=='short_door' else x);zhandle=1.03 if 'door' in name else z
 knob=ellipsoid('wardrobe_knob_'+name,(xhandle,wy-.03,zhandle),(.014,.017,.011),white,'wardrobe');wp['knob_'+name]=knob;wj.append(('knob_'+name,name,(xhandle,wy-.015,zhandle)))
assembly('wardrobe',wp,wj,['carcass'],dict(top_left='carcass',top_right='carcass',bottom_left='carcass',bottom_right='carcass'))
# Shoe cabinet is not identified: proportions from current image only.
sx,sy,sw,sh=P['cabinet_front_x'],P['cabinet_far_y'],1.15,P['cabinet_height'];sd=.36;near=sy-sw
spieces=[]
bodyheight=sh-.07;bodyz=.05+bodyheight/2
for name,loc,sz in [('near',(sx-sd/2,near+.009,bodyz),(sd,.018,bodyheight)),('far',(sx-sd/2,sy-.009,bodyz),(sd,.018,bodyheight)),('top',(sx-sd/2,(near+sy)/2,sh-.01),(sd,sw,.02)),('base',(sx-sd/2,(near+sy)/2,.025),(sd,sw,.05)),('back',(sx-sd+.009,(near+sy)/2,bodyz),(.018,sw-.036,bodyheight)),('divider',(sx-(sd-.018)/2,sy-.25,bodyz),(sd-.018,.018,bodyheight))]:spieces.append(cube('shoe_'+name,loc,sz,white,'shoe_cabinet',.002))
for z in [.26,.50,.75]:spieces.append(cube('shoe_open_shelf',(sx-(sd-.018)/2,sy-.125,z),(sd-.018,.214,.016),white,'shoe_cabinet'))
sp={'carcass':join('shoe_carcass',spieces,'shoe_cabinet')};sj=[];doorparts=[]
for i in range(2):
 cy=near+(sw-.25)*(i+.5)/2;width=(sw-.25)/2-.005;height=sh-.222;z=.065+height/2
 frame=[cube('door_center',(sx+.003,cy,z),(.015,width-.065,height-.075),white,'shoe_cabinet',.001)]
 for y in [cy-width/2+.016,cy+width/2-.016]:frame.append(cube('door_stile',(sx+.012,y,z),(.026,.032,height),white,'shoe_cabinet',.002))
 for zz in [z-height/2+.018,z+height/2-.018]:frame.append(cube('door_rail',(sx+.012,cy,zz),(.026,width-.064,.036),white,'shoe_cabinet',.002))
 doorparts.extend(frame)
sp['doors']=join('shoe_doors',doorparts,'shoe_cabinet');sj.append(('doors','carcass',(sx,sy-.25,.5)))
for i in range(2):
 cy=near+(sw-.25)*(i+.5)/2
 sp[f'drawer_{i}']=cube(f'shoe_drawer_{i}',(sx+.005,cy,sh-.085),(.024,(sw-.25)/2-.008,.12),white,'shoe_cabinet',.002);sj.append((f'drawer_{i}','carcass',(sx-.003,near+.014 if i==0 else sy-.255,sh-.08)))
 for k,z in [('drawer',sh-.085),('door',sh-.26)]:
  handle=ellipsoid(f'shoe_knob_{i}_{k}',(sx+.028,cy,z),(.018,.012,.012),dark,'shoe_cabinet');sp[f'knob_{i}_{k}']=handle;sj.append((f'knob_{i}_{k}',f'drawer_{i}' if k=='drawer' else 'doors',(sx+.011,cy,z)))
for row,z in enumerate([.088,.306,.546,.796]):
 for j in range(2):
  o=ellipsoid(f'shoe_{row}_{j}',(sx-.14,sy-.18+j*.1,z),(.13,.041,.037),mat(f'shoe_tone_{row}_{j}',[(.04,.045,.04),(.23,.20,.13),(.45,.40,.27),(.09,.09,.08)][row],.9),'shoe_cabinet')
  for vertex in o.data.vertices:vertex.co.z=max(-.026,vertex.co.z*(1-.6*vertex.co.x/.13))
  sole=cube('shoe_sole',(sx-.14,sy-.18+j*.1,z-.029),(.245,.079,.016),dark,'shoe_cabinet',.007)
  opening=ellipsoid('shoe_opening',(sx-.205,sy-.18+j*.1,z+.041),(.04,.026,.006),dark,'shoe_cabinet')
  sp[f'footwear_{row}_{j}']=join(f'shoe_{row}_{j}',[o,sole,opening],'shoe_cabinet')
  sj.append((f'footwear_{row}_{j}','carcass',(sx-.14,sy-.18+j*.1,z-.037)))
assembly('shoe_cabinet',sp,sj,['carcass'],dict(top_right='carcass',bottom_right='carcass',door_right_top='doors',door_right_bottom='doors'))
# Foreground glass partition estimate; original reveals only a narrow edge.
cube('partition_glass',(2.04,-.10,1.22),(.012,1.60,2.44),glass,'glass_partition')
cube('partition_trim',(2.05,.70,1.22),(.025,.028,2.44),metal,'glass_partition',.004)
# Exterior is an inferred, independently modelled depth scene, not a room billboard.
rng=random.Random(29);ground=mat('outside_ground',(.13,.14,.13),.95);cube('outside_ground',(xl-3,.5,-.55),(5,7,.1),ground,'exterior')
sidewalk=mat('outside_paving',(.34,.35,.32),.9);cube('outside_paving_strip',(xl-1.15,.5,-.49),(.65,7,.04),sidewalk,'exterior')
foliage_materials=[mat('foliage_'+str(i),(.05+i*.018,.14+i*.026,.025+i*.005),.94) for i in range(7)]
bark=mat('exterior_bark',(.12,.09,.045),.98)
def branch_between(name,a,b,radius):
 a,b=Vector(a),Vector(b);bpy.ops.mesh.primitive_cylinder_add(vertices=7,radius=radius,depth=(b-a).length,location=(a+b)/2);o=bpy.context.object;o.name=name;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();o.data.materials.append(bark);own(o,'exterior')
leafverts=[];leaffaces=[];leafmats=[]
for i in range(44):
 center=np.array((xl-1.7-rng.random()*2.0,-2+rng.random()*6,.40+rng.random()*.45));radius=.20+rng.random()*.20
 base=center.copy();base[2]=-.4;branch_between('exterior_stem',base,center,.011)
 for k in range(5):
  end=center+np.array([rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-.2,.8)])*radius;branch_between('exterior_twig',center-[0,0,.2],end,.004)
 for j in range(500):
  direction=np.array([rng.gauss(0,1) for _ in range(3)]);direction/=np.linalg.norm(direction);p=center+direction*radius*rng.random()**.333
  a=rng.uniform(0,math.tau);l=rng.uniform(.012,.028);v=np.array([math.cos(a)*l,math.sin(a)*l,rng.uniform(-.008,.008)]);b=np.cross(direction,v)*.5
  n=len(leafverts);leafverts.extend([p-v,p+b,p+v,p-b,p+direction*l*.12]);leaffaces.extend([(n,n+1,n+4),(n+1,n+2,n+4),(n+2,n+3,n+4),(n+3,n,n+4)]);idx=rng.randrange(7);leafmats.extend([idx]*4)
me=bpy.data.meshes.new('inferred_leaf_clusters');me.from_pydata(leafverts,[],leaffaces);me.update();o=bpy.data.objects.new('exterior_foliage',me);bpy.context.collection.objects.link(o);own(o,'exterior')
for m in foliage_materials:me.materials.append(m)
for poly,idx in zip(me.polygons,leafmats):poly.material_index=idx
rail=mat('exterior_pale_rail',(.65,.61,.34),.7)
rz=float(source_on_plane(644,529,0,xl-2)[2])
for z in [rz,rz+.18]:cube('outside_rail',(xl-2,.5,z),(.035,7,.035),rail,'exterior')
for y in np.arange(-3,4,.18):cube('outside_post',(xl-2,float(y),rz+.09),(.018,.018,.35),rail,'exterior')
for z in [rz+.10,rz+.34]:cube('far_urban_rail',(xl-3.5,.5,z),(.035,7,.035),rail,'exterior')
for y in np.arange(-3,4,.22):cube('far_urban_post',(xl-3.5,float(y),rz+.22),(.018,.018,.30),rail,'exterior')
concrete=mat('distant_concrete',(.36,.37,.32),.92)
facade=mat('distant_facade',(.18,.19,.17),.94);cube('distant_urban_facade',(xl-5.0,.5,.60),(.15,9,2.40),facade,'exterior')
for zz in [rz-.22,rz+.50]:cube('distant_concrete_beam',(xl-3.8,.5,zz),(.35,7,.14),concrete,'exterior')
signpos=source_on_plane(688,667,0,xl-.70);signmat=mat('exterior_blue_sign',(.015,.22,.48),.8);cube('outside_sign',signpos,(.014,.20,.20),signmat,'exterior')
for i in range(3):cube('unreadable_sign_mark',(signpos[0]+.009,signpos[1],signpos[2]-.06+i*.055),(.004,.145 if i!=1 else .11,.018),white,'exterior')
# Daylight enters through real window opening.
def light(name,pos,target,power,size,color):
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color;o=bpy.data.objects.new(name,data);sc.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
light('window_daylight',(xl-.5,.35,2.5),(.2,.8,.5),500,3.0,(1,.97,.88))
c=fit['camera'];bpy.ops.object.camera_add(location=c['position']);cam=bpy.context.object;cam.name='source_camera';cam.rotation_euler=(Matrix(c['rotation_world_to_cv']).transposed()@Matrix(((1,0,0),(0,-1,0),(0,0,-1)))).to_euler();cam.data.sensor_width=36;cam.data.sensor_fit='HORIZONTAL';cam.data.lens=c['focal_px']*36/1702;sc.camera=cam;sc.render.resolution_x=1702;sc.render.resolution_y=1276
# Keep calibration/declaration artifacts byte-for-byte source-bound.
for file in obsdir.iterdir():
 if file.name.startswith('source_') or file.name in ['surface_observation.json','furniture_observation.json','observation.json','bruksvara_product.jpg']:shutil.copyfile(file,out/file.name)
surfaceobs=json.loads((out/'surface_observation.json').read_text());real=[]
for r in surfaceobs['regions']:
 e=r['entity'];objects=[o.name for o in bpy.data.objects if o.type=='MESH' and o.get('entity_id')==e]
 # Front-facing surfaces for each region; all bound objects remain editable.
 normal=[1,0,0] if e in ['window','blinds','wall_left','shoe_cabinet'] else [0,0,1] if e=='floor' else [0,0,-1] if e in ['ceiling','ceiling_fixtures'] else [0,-1,0]
 up=[0,1,0] if normal[2] else [0,0,1];features=[]
 for f in r['features']:
  kind=f['classification'];row=dict(id=f['id'],representation=kind if kind in ['geometry','albedo','lighting'] else 'omitted')
  if e=='ceiling' and kind=='uncertain':row['representation']='albedo'
  if f['id']=='ceiling_white_panel':row['representation']='albedo'
  if kind=='geometry':
   refs=[{'object':f'blind_panel_{i}'} for i in range(3)] if e=='blinds' else [{'object':n} for n in ['wardrobe_long_door','wardrobe_short_door','wardrobe_upper_drawer','wardrobe_lower_drawer']]
   if f['id']=='bed_head_panels':refs=[{'object':'bed_headboard','vertex_group':f'head_panel_{i}'} for i in range(2)]
   if f['id']=='bed_continuous_duvet':refs=[{'object':'bed_duvet','whole_surface':True}]
   row.update(count=f['count'],mesh_refs=refs)
  features.append(row)
 real.append(dict(id=r['id'],entity=e,pattern=r['pattern'],inspection_objects=objects,normal_world=normal,up_world=up,features=features))
(out/'surface_realization.json').write_text(json.dumps(dict(observation_sha256=sha(out/'surface_observation.json'),regions=real),indent=2))
entities=sorted({o.get('entity_id') for o in bpy.data.objects if o.get('entity_id')});objects=[]
for e in entities:objects.append(dict(id=e,kind='ceiling_lamp' if e=='ceiling_fixtures' else 'room_surface' if e.startswith('wall_') or e in ['floor','ceiling'] else 'furniture' if e in ['bed','wardrobe','shoe_cabinet'] else 'scene_detail',position=[0,0,1],dimensions=[1,1,1],confidence=.75 if e in ['bed','wardrobe'] else .5,evidence=['Authorized original full image and source crop; hidden surfaces inferred'],layout_lock=True,asset_resolution={'mode':'procedural_A'}))
scene=dict(schema_version='real2sim.scene/1.0',units='m',up_axis='Z',branch='A',model_version='independent_009',room=room,camera=c,objects=objects,structure=dict(schema='real2sim.assembly/1',observation_sha256=sha(out/'furniture_observation.json'),parameter_sha256=sha(R/'authoring/fit.json'),assemblies=assemblies,acceptance={'landmark_median_px':9,'landmark_max_px':18},unexpected_interpenetration_tolerance_m=.006),dynamics={'not_applicable':'Static appearance reconstruction; no dynamic features requested'},assumptions=['Hidden shell extents and furniture internals inferred','Exterior restrained inferred depth geometry','Candidate wardrobe identity_unconfirmed','Separate footwear resting in shelf; visual contact evidence required'])
from blender_metadata import synchronize
construction={'camera_fit':fit,'bed_local_revision':bed_revision,'room_calibration':rc,'scope':'All metric construction inputs for this authored attempt; no old scene inputs.'}
(out/'construction_parameters.json').write_text(json.dumps(construction,indent=2));scene['structure']['parameter_sha256']=sha(out/'construction_parameters.json');scene['case_id']='ikea_independent_whole_scene_20260926_A'
for obj in scene['objects']:obj['parameters']={}
if bed_revision:shutil.copyfile(R/'authoring/bed_revision.json',out/'bed_revision.json')
synchronize(scene,update=True);(out/'scene.json').write_text(json.dumps(scene,indent=2));shutil.copyfile(R/'authoring/build_scene.py',out/'build_scene.py');shutil.copyfile(R/'authoring/fit.json',out/'fit.json');shutil.copyfile(R/'authoring/room.json',out/'room.json')
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
sc.render.resolution_percentage=60;sc.cycles.samples=24;sc.render.filepath=str(out/'author_preview.png')
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='CUDA'
 sc.cycles.device='GPU'
except Exception:sc.cycles.device='CPU'
bpy.ops.render.render(write_still=True)
files=[str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ['packet.json','response.json','record.json']]
(out/'response.json').write_text(json.dumps(dict(status='complete',parameters={'model_version':scene['model_version']},artifacts=files,evidence=['Independent build source','Original-bound fit and observation artifacts','Actual Blender preview'],reasoning_summary='First complete editable candidate, all six enclosing surfaces and fixtures retained. Geometry quality remains for executable audit and visual review; no visual pass claimed.'),indent=2))
