"""Fresh semantic delivery-hall model. No meshes or pixels from previous projects."""
import bpy, json, sys, math, random, hashlib
from pathlib import Path
from mathutils import Matrix, Vector
import numpy as np

ROOT=Path('/home/wqz/real2sim_agent_compare_20261003/OURS')
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
OUT=Path(args[0]) if args else ROOT/'models/v1'
OUT.mkdir(parents=True,exist_ok=True)
VERSION=OUT.name
sys.path.insert(0,str(ROOT/'code/workflow'))
from r2s.blender_camera import apply_camera
random.seed(260103)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene;sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1
sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=8;sc.cycles.use_denoising=True
sc.cycles.max_bounces=5;sc.cycles.diffuse_bounces=3;sc.cycles.glossy_bounces=2
sc.render.threads_mode='FIXED';sc.render.threads=2
sc.view_settings.view_transform='AgX';sc.view_settings.exposure=0
sc.render.image_settings.file_format='PNG'
world=bpy.data.worlds.new('warehouse_environment');world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.6,.68,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.18;sc.world=world
G=np.array(json.loads((ROOT/'model_from_input.json').read_text())['model_from_input'])
F=json.loads((ROOT/'inputs/packet.json').read_text())['frames']
P=json.loads((ROOT/'layout_parameters.json').read_text()) if (ROOT/'layout_parameters.json').exists() else {}
materials={};inventory=[];entities={};groups={};face_parts={}
def mat(name,color,rough=.6,metal=0,noise=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 if noise:
  t=n.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=3.8;t.inputs['Detail'].default_value=3
  geo=n.new('ShaderNodeNewGeometry');l.new(geo.outputs['Position'],t.inputs['Vector'])
  ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(*[c*(1-noise) for c in color],1);ramp.color_ramp.elements[1].color=(*[min(1,c*(1+noise)) for c in color],1)
  l.new(t.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs['Color'],p.inputs['Base Color'])
 materials[name]=m;return m
mat('floor',(.28,.265,.21),.7,noise=.28);mat('ceiling',(.17,.165,.14),.9,noise=.32)
mat('wall',(.65,.64,.58),.86,noise=.08);mat('door',(.62,.63,.62),.36,.15)
mat('steel',(.21,.23,.22),.34,.72);mat('bright_metal',(.5,.53,.52),.26,.78)
mat('blue',(.015,.095,.30),.42,.25);mat('orange',(.6,.095,.012),.52,.1)
mat('wood',(.28,.22,.15),.85,noise=.32);mat('lumber',(.64,.51,.30),.83,noise=.10)
mat('rust',(.32,.105,.042),.83,.22,noise=.2);mat('bag',(.7,.7,.62),.9,noise=.1)
mat('lime',(.46,.58,.055),.63,.15,noise=.14);mat('white_vehicle',(.75,.75,.69),.26,.16)
mat('black_vehicle',(.016,.019,.017),.24,.38);mat('glass',(.015,.028,.033),.12,.25)
mat('rubber',(.017,.019,.018),.9);mat('red',(.5,.02,.012),.25)
mat('yellow',(.78,.58,.02),.5);mat('dock',(.055,.075,.049),.86,noise=.2)
mat('blue_door',(.017,.17,.30),.6,.12);mat('light',(.9,.92,.86),.3)
materials['light'].node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value=(.92,.96,1,1)
materials['light'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=6
m=mat('hazard',(.65,.6,.045),.76,noise=0);n=m.node_tree.nodes;l=m.node_tree.links
geo=n.new('ShaderNodeNewGeometry');dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';dot.inputs[1].default_value=(1,1,1)
l.new(geo.outputs['Position'],dot.inputs[0]);mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=2.8;l.new(dot.outputs['Value'],mul.inputs[0])
mod=n.new('ShaderNodeMath');mod.operation='PINGPONG';mod.inputs[1].default_value=1;l.new(mul.outputs[0],mod.inputs[0]);r=n.new('ShaderNodeValToRGB');r.color_ramp.interpolation='CONSTANT';r.color_ramp.elements[0].color=(.025,.028,.025,1);r.color_ramp.elements[1].position=.5;r.color_ramp.elements[1].color=(.64,.57,.05,1);l.new(mod.outputs[0],r.inputs[0]);l.new(r.outputs[0],n['Principled BSDF'].inputs['Base Color'])

def finish(o,name,owner,ma,role='component',bevel=0):
 o.name=name;o['entity_id']=owner;o['component_id']=name;o['provenance']='Fresh custom authoring from source RGB and predicted-depth measurements';o['observed_or_assumed']='observed form; hidden backs inferred'
 o.data.materials.append(materials[ma]);groups.setdefault(owner,[]).append(o)
 if bevel:
  b=o.modifiers.new('small_manufactured_edge','BEVEL');b.width=bevel;b.segments=2
  o.modifiers.new('weighted_normals','WEIGHTED_NORMAL')
 inventory.append(dict(component=name,entity=owner,material=ma,geometry=role))
 return o
def box(name,loc,dim,ma,owner=None,bevel=0):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 return finish(o,name,owner or name,ma,'box',bevel)
def cyl(name,loc,r,depth,ma,owner=None,axis='Z',verts=16):
 bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc);o=bpy.context.object
 if axis=='X':o.rotation_euler[1]=math.pi/2
 if axis=='Y':o.rotation_euler[0]=math.pi/2
 return finish(o,name,owner or name,ma,'cylinder')
def mesh(name,verts,faces,ma,owner):
 me=bpy.data.meshes.new(name+'_mesh');me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(name,me);sc.collection.objects.link(o);return finish(o,name,owner,ma,'custom_mesh')
def beam(name,a,b,width,ma,owner):
 mid=(Vector(a)+Vector(b))/2;o=box(name,mid,(width,width,(Vector(b)-Vector(a)).length),ma,owner);o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler();return o
def slab_sections(name,sections,center,ma,owner):
 # Y longitudinal cross sections, X half width and rectangular Z bands.
 verts=[]
 for y,w,z0,z1 in sections:
  verts += [(center[0]-w,center[1]+y,z0),(center[0]+w,center[1]+y,z0),(center[0]+w,center[1]+y,z1),(center[0]-w,center[1]+y,z1)]
 faces=[(3,2,1,0)]
 for i in range(len(sections)-1):
  for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
 faces.append(tuple(range(4*(len(sections)-1),4*len(sections))))
 return mesh(name,verts,faces,ma,owner)

# Full outer shell; inaccessible outer extents are explicit closure hypotheses.
room=dict(x_min=-49.,x_max=16.,y_min=-11.5,y_max=19.4,height=4.68,thickness=.2,preserve_full_shell=True)
for name,loc,dim,ma in [
 ('floor',(-16.5,3.95,-.10),(65,30.9,.2),'floor'),('ceiling',(-16.5,3.95,4.78),(65,30.9,.2),'ceiling'),
 ('wall_left',(-49.1,3.95,2.34),(.2,30.9,4.68),'wall'),('wall_right',(16.1,3.95,2.34),(.2,30.9,4.68),'wall'),
 ('wall_front',(-16.5,-11.6,2.34),(65,.2,4.68),'wall'),('wall_back',(-16.5,19.5,2.34),(65,.2,4.68),'wall')]:box(name,loc,dim,ma)
box('main_side_wall',(-13.65,9.9,2.34),(.22,19.0,4.68),'wall')
box('corridor_north_wall',(-31.4,.55,2.34),(35.2,.22,4.68),'wall')
box('corridor_south_wall',(-30.8,-7.75,2.34),(36.4,.22,4.68),'ceiling')
box('cage_upper_wall',(-5.95,-8.0,3.49),(15.8,.22,2.38),'wall')
box('lumber_back_wall',(.7,-8.0,1.14),(4.5,.24,2.28),'wall')
box('garage_reveal',(5.35,.9,2.34),(.4,.6,4.68),'wall')
box('rack_back_wall',(10.7,10.94,2.34),(10.6,.22,4.68),'wall')
box('loading_platform',(-4.1,17.1,.43),(18.7,4.6,.86),'dock')
box('dock_blue_door',(-3.6,19.25,2.50),(4.6,.10,3.2),'blue_door')
box('far_corridor_door',(-48.8,-3.6,2.20),(.10,7.5,4.4),'blue_door')

# Tall concrete columns: paint boundary changes material, not shell dimensions.
for j,(x,y,dx,dy) in enumerate([(-4.3,10.7,.58,.75),(-4.25,1.06,.56,.68),(-4.21,.52,.40,.37),(-4.25,-7.8,.58,.62),(5.35,.82,.48,.6),(5.45,9.5,.5,.6),(-13.5,.35,.5,.5),(-13.5,-7.55,.4,.45)]):
 owner='column_'+str(j);box(owner+'_lower',(x,y,1.08),(dx,dy,2.16),'hazard',owner);box(owner+'_upper',(x,y,3.42),(dx,dy,2.52),'wall',owner)

# Seven sliding metal door leaves. Thin panel and frame, visible rail/hinges.
doorx=P.get('door_x',5.25);dstart=-7.2;dend=.55;pw=(dend-dstart)/7
for j in range(7):
 y=dstart+(j+.5)*pw
 for k,z in enumerate([1.0,3.0]):box(f'door_leaf_{j}_panel_{k}',(doorx+.035,y,z),(.07,pw-.065,1.89),'door','garage_door',.009)
 for edge in [-1,1]:box(f'door_leaf_{j}_upright_{edge}',(doorx-.022,y+edge*(pw/2-.018),2.0),(.065,.052,4.02),'steel','garage_door',.008)
 for k,z in enumerate([.03,2.,4.]):box(f'door_leaf_{j}_rail_{k}',(doorx-.025,y,z),(.065,pw,.052),'steel','garage_door')
 for k,z in enumerate([.35,1.15,2.55,3.45]):cyl(f'door_leaf_{j}_hinge_{k}',(doorx-.07,y-pw/2+.04,z),.022,.115,'bright_metal','garage_door')
box('door_upper_track',(doorx,.0+(dstart+dend)/2,4.2),(.35,8.0,.16),'steel','garage_door')
box('door_header',(doorx+.14,(dstart+dend)/2,4.43),(.52,8.3,.37),'wall','garage_door')

# Blue pallet rack and orange beams; irregular sacks are deformable bag-shaped meshes.
rx0,rx1,ry=5.9,14.7,10.05
for j,x in enumerate([rx0,8.85,11.80,rx1]):
 for k,y in enumerate([ry-.65,ry+.65]):box(f'rack_upright_{j}_{k}',(x,y,2.22),(.095,.095,4.44),'blue','storage_rack')
for level,z in enumerate([.18,1.35,2.52,3.68]):
 for side,y in enumerate([ry-.65,ry+.65]):box(f'rack_beam_{level}_{side}',((rx0+rx1)/2,y,z),(rx1-rx0,.12,.16),'orange','storage_rack')
 for bay in range(3):
  cx=rx0+(bay+.5)*(rx1-rx0)/3
  for k in range(6):box(f'rack_pallet_{level}_{bay}_{k}',(cx,ry-.5+k*.20,z+.14),(2.6,.16,.09),'lumber','storage_rack')
  if level<3:
   for bag in range(5):
    x=cx+(bag-2)*.5;y=ry-.1;h=.85+random.uniform(-.08,.05)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=(x,y,z+.16+h*.5));o=bpy.context.object;o.scale=(.24,.44,h*.54)
    for v in o.data.vertices:
     v.co.x*=1+random.uniform(-.08,.08);v.co.y*=1+random.uniform(-.09,.09)
    finish(o,f'rack_sack_{level}_{bay}_{bag}','storage_rack','bag','irregular_bag_mesh')

# Two open wooden pallet crates; board count from visible horizontal seams.
for q,cy in enumerate([7.35,8.72]):
 cx=2.25;dx=1.43;dy=1.32
 for j,x in enumerate([cx-dx*.39,cx,cx+dx*.39]):box(f'crate{q}_foot{j}',(x,cy,.09),(.18,dy,.18),'wood','wood_crates')
 box(f'crate{q}_base',(cx,cy,.21),(dx,dy,.09),'wood','wood_crates')
 for layer in range(6):
  z=.34+layer*.18
  for side,s in enumerate([-1,1]):
   box(f'crate{q}_long_{layer}_{side}',(cx,cy+s*dy/2,z),(dx,.045,.165),'wood','wood_crates',.005)
   box(f'crate{q}_short_{layer}_{side}',(cx+s*dx/2,cy,z),(.045,dy,.165),'wood','wood_crates',.005)
 for j,(a,b) in enumerate([(-1,-1),(-1,1),(1,-1),(1,1)]):box(f'crate{q}_strap{j}',(cx+a*(dx/2+.012),cy+b*(dy/2-.065),.80),(.018,.12,1.26),'rust','wood_crates')

# Lime waste skips with taper and open top. Separate ribs, rim and feet.
for k,cy in enumerate([11.65,15.05]):
 cx=2.55;owner='lime_skips';z0=.18;z1=1.6
 verts=[]
 for z,dx,dy in [(z0,1.4,2.25),(z1,2.15,2.85)]:
  verts += [(cx+a*dx/2,cy+b*dy/2,z) for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]]
 # Open top retains actual wall thickness through solidify.
 o=mesh(f'skip{k}_shell',verts,[(0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'lime',owner);s=o.modifiers.new('plate_thickness','SOLIDIFY');s.thickness=.035
 for j,x in enumerate([cx-.7,cx+.7]):box(f'skip{k}_foot{j}',(x,cy,.09),(.16,1.8,.18),'lime',owner)
 for j,y in enumerate([cy-1.425,cy+1.425]):box(f'skip{k}_rim{j}',(cx,y,z1),(2.25,.1,.12),'lime',owner)
 for j,x in enumerate([cx-1.075,cx+1.075]):box(f'skip{k}_side_rim{j}',(x,cy,z1),(.1,2.9,.12),'lime',owner)

# Trailer, wheels, tow frame and freestanding no-parking sign.
box('trailer_box',(12.35,8.12,1.66),(4.35,1.96,2.15),'white_vehicle','white_trailer',.035)
box('trailer_floor',(12.35,8.12,.54),(4.65,2.08,.17),'steel','white_trailer')
for x in [12.9,13.65]:
 for side in [-1,1]:
  cyl(f'trailer_wheel_{x}_{side}',(x,8.12+side*1.0,.35),.35,.20,'rubber','white_trailer','Y',24)
  cyl(f'trailer_hub_{x}_{side}',(x,8.12+side*1.11,.35),.18,.015,'bright_metal','white_trailer','Y',16)
for k,x in enumerate([12.1,12.9]):box(f'trailer_window_{k}',(x,7.129,1.96),(.62,.023,.76),'glass','white_trailer',.07)
beam('trailer_towA',(10.15,7.25,.43),(8.5,8.12,.43),.09,'steel','white_trailer');beam('trailer_towB',(10.15,9,.43),(8.5,8.12,.43),.09,'steel','white_trailer')
box('flatbed_frame',(7.55,7.80,.39),(2.1,1.6,.16),'steel','white_trailer');box('flatbed_deck',(7.55,7.8,.50),(2.0,1.5,.07),'door','white_trailer')
for s in [-1,1]:cyl(f'flatbed_wheel{s}',(7.9,7.8+s*.86,.31),.31,.16,'rubber','white_trailer','Y',24)
box('sign_base',(6.2,7.85,.05),(.8,.5,.1),'steel');cyl('sign_pole',(6.2,7.85,.95),.025,1.8,'bright_metal')
cyl('no_parking_red',(6.2,7.84,1.84),.30,.025,'red',axis='Y',verts=32);cyl('no_parking_blue',(6.2,7.82,1.84),.245,.012,'blue',axis='Y',verts=32)
beam('no_parking_slashA',(6.04,7.806,1.64),(6.36,7.806,2.04),.045,'red','no_parking_red');beam('no_parking_slashB',(6.36,7.806,1.64),(6.04,7.806,2.04),.045,'red','no_parking_red')

# Custom van cab sectional mesh, cargo box, glazing and four realistic wheels.
vx,vy=P.get('van_x',-5.72),P.get('van_y',10.7)
slab_sections('van_cab_body',[(-2.25,.90,.48,1.06),(-2.05,1.01,.45,1.20),(-1.05,1.0,.45,1.56),(-.28,.97,.47,2.2),(.25,.98,.47,2.2)],(vx,vy),'white_vehicle','white_van')
box('van_cargo_box',(vx,vy+1.37,1.93),(2.18,3.24,2.34),'white_vehicle','white_van',.04)
box('van_chassis',(vx,vy+.1,.45),(1.75,5.35,.22),'steel','white_van')
mesh('van_windshield',[(vx-.84,vy-1.03,1.55),(vx+.84,vy-1.03,1.55),(vx+.81,vy-.30,2.12),(vx-.81,vy-.30,2.12)],[(0,1,2,3)],'glass','white_van')
for s in [-1,1]:
 mesh('van_side_glass'+str(s),[(vx+s*.993,vy-.93,1.49),(vx+s*.993,vy+.12,1.49),(vx+s*.96,vy+.12,2.10),(vx+s*.96,vy-.27,2.10)],[(0,1,2,3)],'glass','white_van')
 box('van_mirror'+str(s),(vx+s*1.17,vy-.65,1.57),(.19,.3,.24),'rubber','white_van',.035)
 for q,y in enumerate([vy-1.43,vy+1.70]):
  cyl(f'van_tyre{s}_{q}',(vx+s*1.00,y,.39),.39,.25,'rubber','white_van','X',32)
  cyl(f'van_hub{s}_{q}',(vx+s*1.14,y,.39),.23,.03,'bright_metal','white_van','X',20)
box('van_front_bumper',(vx,vy-2.27,.54),(1.94,.20,.25),'rubber','white_van',.045)
box('van_grille',(vx,vy-2.267,.90),(1.12,.018,.24),'rubber','white_van')
for s in [-1,1]:box('van_headlamp'+str(s),(vx+s*.78,vy-2.25,1.02),(.30,.03,.28),'door','white_van',.04)
box('van_cooler',(vx,vy+.03,2.97),(1.15,.40,.46),'white_vehicle','white_van',.08)

# Hatchback: joined rounded sections preserve roof/hood slopes; no stock vehicle asset.
cx,cy=P.get('car_x',-2.90),P.get('car_y',13.45)
slab_sections('car_lower_body',[(-1.95,.69,.36,.83),(-1.65,.87,.35,1.05),(.95,.86,.34,1.03),(1.8,.70,.38,.73)],(cx,cy),'black_vehicle','black_car')
slab_sections('car_upper_body',[(-1.65,.77,.82,1.08),(-.95,.70,.96,1.48),(.40,.69,1.0,1.47),(1.12,.75,.85,1.05)],(cx,cy),'black_vehicle','black_car')
mesh('car_rear_glass',[(cx-.7,cy-1.62,1.04),(cx+.7,cy-1.62,1.04),(cx+.61,cy-.96,1.43),(cx-.61,cy-.96,1.43)],[(0,1,2,3)],'glass','black_car')
for s in [-1,1]:
 for q,y in enumerate([cy-1.21,cy+1.15]):
  cyl(f'car_tyre{s}_{q}',(cx+s*.8,y,.31),.31,.19,'rubber','black_car','X',28)
  cyl(f'car_hub{s}_{q}',(cx+s*.901,y,.31),.17,.02,'steel','black_car','X',16)
 box('car_tail_light'+str(s),(cx+s*.66,cy-1.8,.94),(.24,.08,.22),'red','black_car',.04)

# Lumber cart frame and many individually editable boards.
cartx,carty=.55,-7.18
box('cart_floor_frame',(cartx,carty,.25),(1.9,.78,.10),'blue','lumber_cart')
for j,x in enumerate([cartx-.84,cartx,cartx+.84]):box(f'cart_upright{j}',(x,carty-.38,1.0),(.05,.05,1.60),'blue','lumber_cart')
box('cart_crossbar',(cartx,carty-.38,1.59),(1.73,.05,.06),'blue','lumber_cart')
for a in [-1,1]:
 for b in [-1,1]:cyl(f'cart_caster{a}_{b}',(cartx+a*.65,carty+b*.29,.12),.12,.07,'rubber','lumber_cart','Y',16)
for layer in range(9):
 for row in range(3):
  length=4.25+random.uniform(-.35,.25);x=cartx+random.uniform(-.23,.23);y=carty-.26+row*.17;z=.35+layer*.055
  box(f'lumber_board_{layer}_{row}',(x,y,z),(length,.15,.045),'lumber','lumber_cart',.003)

# Cages with physical bars; grids are separately editable coherent mesh panels.
for k,(a,b) in enumerate([(-3.85,-1.05),(-8.6,-4.75),(-12.8,-8.65)]):
 owner='mesh_cages';y=-7.91
 for j,x in enumerate([a,b]):box(f'cage{k}_side{j}',(x,y,1.14),(.04,.055,2.28),'bright_metal',owner)
 for j,z in enumerate([.03,2.26]):box(f'cage{k}_rail{j}',((a+b)/2,y,z),(b-a,.055,.04),'bright_metal',owner)
 for j,x in enumerate(np.arange(a+.06,b,.075)):box(f'cage{k}_wireV{j}',(x,y,1.145),(.007,.009,2.22),'steel',owner)
 for j,z in enumerate(np.arange(.075,2.25,.075)):box(f'cage{k}_wireH{j}',((a+b)/2,y,z),(b-a,.009,.007),'steel',owner)
box('cage_machine',(-2.45,-9.,.85),(1.4,1.,1.7),'door');cyl('cage_machine_fan',(-2.45,-8.49,1.22),.37,.03,'steel',axis='Y',verts=28)
for k,x in enumerate([-9.3,-10.2,-11.3]):box(f'cage_bin{k}',(x,-8.7,.53),(.63,.75,1.05),'rubber',bevel=.04)

# Visible corridor compactor and small fixed wall fittings.
box('compactor_body',(-20.5,-1.55,1.36),(2.5,2.3,2.72),'steel',bevel=.06)
box('compactor_hopper',(-20.5,-1.55,3.0),(2.7,2.5,1.0),'steel')
box('compactor_yellow_front',(-19.21,-1.55,1.2),(.1,1.8,1.6),'yellow')
box('fire_cabinet',(-13.48,3.8,1.5),(.1,.44,.6),'red');cyl('extinguisher',(-13.3,3.45,.62),.09,.7,'red')

# Fluorescent strips in both main hall and the long corridor, all retained.
for y in [-5.5,.0,5.5,11.0]:
 for x in [-10.,-5.3,-.6,4.1,8.8,13.0]:
  owner=f'luminaire_{x}_{y}';box(owner,(x,y,4.52),(3.4,.095,.075),'light')
  ld=bpy.data.lights.new(owner+'_emitter','AREA');ld.energy=125;ld.shape='RECTANGLE';ld.size=3.4;ld.size_y=.16
  ob=bpy.data.objects.new(owner+'_emitter',ld);sc.collection.objects.link(ob);ob.location=(x,y,4.43)
for x in range(-17,-49,-5):
 owner='corridor_luminaire_'+str(x);box(owner,(x,-3.6,4.46),(2.4,.095,.075),'light')
 ld=bpy.data.lights.new(owner+'_emitter','AREA');ld.energy=120;ld.shape='RECTANGLE';ld.size=2.4;ld.size_y=.2;ob=bpy.data.objects.new(owner+'_emitter',ld);sc.collection.objects.link(ob);ob.location=(x,-3.6,4.38)
for j,y in enumerate([-7.25,-6.96,-6.67]):cyl('ceiling_pipe'+str(j),(-.5,y,4.24),.055,29,'bright_metal',axis='X')
for j,x in enumerate([3.6,3.85,4.1]):cyl('main_ceiling_pipe'+str(j),(x,5.5,4.21),.065,26,'bright_metal',axis='Y')

# All supplied cameras are transformed by exactly one recorded rigid gauge.
cameras=[]
for i,f in enumerate(F):
 T=G@np.array(f['T_world_camera']);K=np.array(f['K'])
 c=dict(frame_id=f['frame_id'],role='reconstruction',position=T[:3,3].tolist(),rotation_world_to_cv=T[:3,:3].T.tolist(),focal_px=float(K[0,0]),focal_y_px=float(K[1,1]),principal_point=K[:2,2].tolist(),image_size=f['image_size'],pose_source=f['pose_source'],evidence=f['evidence'],input_index=i,source_sha256=f['sha256'],source_frame=None,pixel_coordinates='integer_centers')
 cameras.append(c);bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='source_camera' if i==0 else f'source_camera_{i:04d}';apply_camera(sc,cam,c)
apply_camera(sc,bpy.data.objects['source_camera'],cameras[0]);sc.render.resolution_percentage=100

# Keep individual component objects and exact ownership. Native graph and source
# landmarks are produced separately from this construction, never guessed here.
bpy.context.view_layer.update()
for owner,obs in groups.items():
 verts=[o.matrix_world@Vector(v) for o in obs for v in o.bound_box];lo=np.min(np.array(verts),axis=0);hi=np.max(np.array(verts),axis=0)
 entities[owner]=dict(id=owner,kind='lamp' if owner.startswith(('luminaire','corridor_luminaire')) else 'semantic_assembly' if owner in ['garage_door','storage_rack','wood_crates','lime_skips','white_trailer','white_van','black_car','lumber_cart','mesh_cages'] else 'architecture_or_fixture',position=((lo+hi)/2).tolist(),dimensions=(hi-lo).tolist(),evidence=['inputs/packet.json','rgb_annotations.json','measurement_raw.json','measurements_landmarks.json'],confidence=.7,layout_lock=True,asset_resolution=dict(mode='custom_A',reason='No external asset or model identity asserted'))
for o in sc.objects:
 if o.type=='MESH':
  o['collider']='static visible mesh; optional box proxy listed separately'
S=dict(schema_version='real2sim.scene/1.0',units='m',up_axis='Z',branch='A',model_version=VERSION,model_from_input=G.tolist(),room=room,camera=cameras[0],cameras=cameras,objects=list(entities.values()),assumptions=['Outer inaccessible shell closure is hypothesized','Metric gauge and input camera truth are supplied diagnostics','Hidden vehicle underside and bag backs inferred','Input-depth edges unreliable; coherent dimensions from interior patches'],metadata_geometry_convention='Evaluated world AABB; authoritative metadata updated by native worker')
(OUT/'scene.json').write_text(json.dumps(S,indent=2));(OUT/'component_inventory.json').write_text(json.dumps(inventory,indent=2));(OUT/'colliders.json').write_text(json.dumps([dict(entity=o['id'],type='aabb',position=o['position'],dimensions=o['dimensions'],status='technical static proxy; not physical acceptance') for o in entities.values()],indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'scene.glb'),export_format='GLB',export_cameras=True,export_lights=True,export_extras=True)
print('FRESH_SEMANTIC_MODEL',len(entities),len(inventory),str(OUT))
