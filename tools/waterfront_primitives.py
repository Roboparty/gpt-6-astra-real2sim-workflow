"""Editable static furnishings for the waterfront bedroom; import inside Blender.

Metres, room-local XYZ: X across bed->cabinet, Y toward window, Z up.
Primitive centers are geometric centers. build_furniture centers and plant
centers are footprint centers at their supporting floor Z. Furniture local
head/back is -Y; optional rotation_z rotates the complete assembly about Z.
All dimensions/materials/hidden construction are assumptions, not measurements.
No scene reset, file IO, render, asset import, dynamics, or external dependencies.
"""
import math
import random

import bpy
from mathutils import Vector


def _finish(obj, name, material=None, assembly=None, smooth=False):
    if name in bpy.data.objects and bpy.data.objects[name] != obj:
        raise ValueError('Object name already exists: '+name)
    obj.name=name;obj.data.name=name+'_mesh'
    obj['assembly']=assembly or name.split('_')[0];obj['entity_id']=obj['assembly']
    obj['part_id']=name;obj['prior_status']='assumed';obj['assumed']=True
    obj['prior_source']='Waterfront source-frame visual authoring; unmeasured dimensions/materials and unseen surfaces'
    obj['static_authoring']=True
    if material:obj.data.materials.append(material)
    if smooth:
        for polygon in obj.data.polygons:polygon.use_smooth=True
    return obj


def box(name, center, size, material, bevel=0, *, assembly=None):
    """Editable box mesh with optional non-destructive rounded edges."""
    if len(size)!=3 or min(size)<=0:raise ValueError('Positive XYZ size required')
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    obj=bpy.context.object;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    _finish(obj,name,material,assembly)
    if bevel:
        mod=obj.modifiers.new('soft_edges','BEVEL');mod.width=min(bevel,min(size)*.48);mod.segments=4
        mod=obj.modifiers.new('weighted_corner_normals','WEIGHTED_NORMAL');mod.keep_sharp=True
    return obj


def cushion(name, center, size, material, bevel=None, *, assembly=None, rotation=(0,0,0)):
    obj=box(name,center,size,material,min(size)*.42 if bevel is None else bevel,assembly=assembly)
    obj.rotation_euler=rotation
    for polygon in obj.data.polygons:polygon.use_smooth=True
    return obj


def ellipsoid(name, center, size, material, *, assembly=None, rotation=(0,0,0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=1,location=center)
    obj=bpy.context.object;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.rotation_euler=rotation
    return _finish(obj,name,material,assembly,True)


def _mesh(name, vertices, faces, material, assembly=None, center=(0,0,0)):
    mesh=bpy.data.meshes.new(name+'_mesh');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.location=center
    return _finish(obj,name,material,assembly,True)


def cloth(name, center, size, material, fold=.04, seed=0, *, assembly=None, drape=0, edge=.14):
    """Static editable folded grid; size Z is thickness, drape lowers its skirt.

    Folds are analytic assumptions, never a cloth simulation. The supplied center
    is the nominal cloth surface center, not the evaluated folded bounding box.
    """
    if min(size)<=0 or fold<0 or drape<0 or not 0<edge<.5:raise ValueError('Invalid cloth dimensions/folds')
    rng=random.Random(seed);phases=[rng.uniform(0,2*math.pi) for _ in range(6)]
    nx,ny=40,52;vertices=[]
    for j in range(ny+1):
        v=j/ny-.5
        for i in range(nx+1):
            u=i/nx-.5
            ripple=fold*(.48*math.sin(21*u+7*v+phases[0])+.30*math.sin(11*v-13*u+phases[1])+.15*math.sin(46*u+19*v+phases[2]))
            ridge=fold*.7*math.exp(-((u-.14*math.sin(v*9+phases[3]))/.11)**2)*math.sin(v*12+phases[4])
            rim=max(0,(max(abs(u),abs(v))-(.5-edge))/edge);rim=rim*rim*(3-2*rim)
            vertices.append((u*size[0],v*size[1],ripple+ridge-drape*rim))
    faces=[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)]
    obj=_mesh(name,vertices,faces,material,assembly,center)
    mod=obj.modifiers.new('static_fabric_thickness','SOLIDIFY');mod.thickness=size[2];mod.offset=-1
    obj['cloth_simulation']=False;obj['fold_seed']=seed
    return obj


def _cylinder(name, center, radius, height, material, assembly=None, radius_top=None):
    bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=radius,radius2=radius if radius_top is None else radius_top,depth=height,location=center)
    return _finish(bpy.context.object,name,material,assembly,True)


def _stem(name, start, end, radius, material, assembly):
    a,b=Vector(start),Vector(end);obj=_cylinder(name,(a+b)/2,radius,(b-a).length,material,assembly)
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return obj


def plant(name, center, height, material, pot_material, *, stem_material=None, soil_material=None, leaf_count=16, seed=17):
    """Separate curved broadleaf meshes, petioles, planter and soil; returns list."""
    if height<=0 or leaf_count<3:raise ValueError('Plant needs positive height and at least three leaves')
    stem_material=stem_material or material;soil_material=soil_material or pot_material
    base=Vector(center);rng=random.Random(seed);created=[];pot_h=height*.27;pot_r=height*.16
    created.append(_cylinder(name+'_pot',base+Vector((0,0,pot_h/2)),pot_r*.74,pot_h,pot_material,name,pot_r))
    created.append(_cylinder(name+'_soil',base+Vector((0,0,pot_h*.96)),pot_r*.90,.014*height,soil_material,name))
    for k in range(leaf_count):
        phi=k*2.39996+rng.uniform(-.18,.18);length=height*rng.uniform(.33,.55);width=length*rng.uniform(.47,.66)
        root=base+Vector((0,0,pot_h*.9));origin=base+Vector((math.cos(phi)*height*.10,math.sin(phi)*height*.10,height*rng.uniform(.48,.84)))
        created.append(_stem(f'{name}_stem_{k:02d}',root,origin,height*.006,stem_material,name))
        forward=Vector((math.cos(phi),math.sin(phi),0));side=Vector((-math.sin(phi),math.cos(phi),0));verts=[];nu,nv=14,8
        for i in range(nu+1):
            u=i/nu;profile=max(.006,math.sin(math.pi*u)**.72)
            for j in range(nv+1):
                v=j/nv*2-1;point=origin+forward*(length*u)+side*(width*.5*profile*v)
                point.z+=length*(.31*math.sin(math.pi*u)-.36*u*u-.10*v*v*math.sin(math.pi*u))
                verts.append(tuple(point))
        faces=[(i*(nv+1)+j,(i+1)*(nv+1)+j,(i+1)*(nv+1)+j+1,i*(nv+1)+j+1) for i in range(nu) for j in range(nv)]
        leaf=_mesh(f'{name}_leaf_{k:02d}',verts,faces,material,name)
        mod=leaf.modifiers.new('leaf_thickness','SOLIDIFY');mod.thickness=.0015*height;created.append(leaf)
    return created


def _materials(provided):
    palette={'white':(.77,.77,.72,0),'cream':(.61,.56,.44,0),'navy':(.009,.017,.045,0),
        'pink':(.43,.24,.19,0),'blue':(.035,.12,.18,0),'rust':(.40,.12,.075,0),
        'black':(.015,.019,.022,0),'green':(.028,.13,.035,0),'stem':(.08,.15,.035,0),
        'pot':(.022,.027,.026,0),'soil':(.016,.010,.007,0),'brass':(.46,.25,.065,.78),
        'bronze':(.065,.052,.035,.65),'wood':(.09,.065,.035,0)}
    materials=dict(provided)
    for key,rgba in palette.items():
        if key in materials:continue
        mat=bpy.data.materials.new('waterfront_assumed_'+key);mat.use_nodes=True
        bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(*rgba[:3],1)
        bsdf.inputs['Metallic'].default_value=rgba[3];bsdf.inputs['Roughness'].default_value=.29 if rgba[3] else .82
        mat['prior_status']='assumed';mat['prior_source']='Visual palette initialization; not measured reflectance';materials[key]=mat
    return materials


def build_furniture(spec, materials):
    """Build optional spec['parts'] entries bed/chaise/plant/side_table.

    Each entry requires center=[x,y,floor_z]. Bed size defaults [1.9,2.2,.64],
    chaise [.90,1.65,.82]; their size is nominal overall width/length/height.
    Plant height defaults 1.15, table radius .22 and height .58. rotation_z
    defaults zero. Returns {assembly: {'root': Empty, 'objects': [mesh,...]}}.
    Provided material keys: white, cream, navy, pink, blue, rust, black, green,
    stem, pot, soil, brass, bronze, wood. Missing keys get assumed local materials.
    """
    m=_materials(materials);result={}
    for name,p in spec.get('parts',{}).items():
        if name not in {'bed','chaise','plant','side_table'}:continue
        if name in bpy.data.objects:raise ValueError('Assembly already exists: '+name)
        before=set(bpy.data.objects)
        if name=='bed':
            w,l,h=p.get('size',[1.9,2.2,.64])
            box('bed_base',(0,0,h*.24),(w*.97,l*.97,h*.36),m['cream'],.045,assembly=name)
            cushion('bed_mattress',(0,0,h*.66),(w,l,h*.40),m['white'],assembly=name)
            cushion('bed_headboard',(0,-l*.49,h*.92),(w*1.06,.12,h*1.32),m['cream'],assembly=name)
            cloth('bed_sheet',(0,.015,h*.875),(w*1.08,l*1.08,.007),m['white'],fold=.012,seed=11,drape=.12,assembly=name)
            for i,x in enumerate([-.26*w,.26*w]):
                cushion(f'bed_white_pillow_back_{i}',(x,-l*.36,h*1.12),(w*.45,.18,h*.76),m['white'],assembly=name,rotation=(-.18,0,(-1 if i else 1)*.07))
                cushion(f'bed_white_pillow_front_{i}',(x,-l*.24,h*1.04),(w*.40,.19,h*.59),m['white'],assembly=name,rotation=(-.22,0,0))
                cushion(f'bed_blush_pillow_{i}',(x*1.12,-l*.12,h*1.02),(w*.25,.17,h*.60),m['pink'],assembly=name,rotation=(-.14,(-1 if i else 1)*.08,0))
            pillow=cushion('bed_geometric_pillow',(0,-l*.13,h*.99),(w*.32,.18,h*.47),m['white'],assembly=name)
            for i in range(6):
                x=(i%3-1)*w*.09;z=(i//3-.5)*h*.20
                patch=_mesh(f'bed_geometric_patch_{i}',[(x-w*.043,.095,z-h*.09),(x+w*.043,.095,z-h*.09),(x+(w*.043 if i%2 else -w*.043),.095,z+h*.09)],[(0,1,2)],m['black'],name)
                patch.parent=pillow
            cloth('bed_navy_throw',(w*.10,l*.23,h*.96),(w*.87,l*.58,.013),m['navy'],fold=.075,seed=31,drape=.20,edge=.17,assembly=name)
        elif name=='chaise':
            w,l,h=p.get('size',[.90,1.65,.82])
            for i,x in enumerate([-.37*w,.37*w]):
                for j,y in enumerate([-.39*l,.39*l]):box(f'chaise_leg_{i}_{j}',(x,y,h*.10),(.065,.065,h*.20),m['wood'],.01,assembly=name)
            cushion('chaise_base',(0,0,h*.29),(w,l,h*.22),m['cream'],assembly=name)
            cushion('chaise_seat',(0,l*.035,h*.46),(w*.91,l*.87,h*.22),m['cream'],assembly=name)
            cushion('chaise_back',(0,-l*.40,h*.70),(w*.92,l*.15,h*.55),m['cream'],assembly=name,rotation=(-.13,0,0))
            for i,x in enumerate([-.45*w,.45*w]):cushion(f'chaise_arm_{i}',(x,-l*.22,h*.53),(w*.13,l*.51,h*.34),m['cream'],assembly=name)
            cushion('chaise_rust_pillow',(-w*.11,-l*.28,h*.72),(w*.54,.14,h*.44),m['rust'],assembly=name,rotation=(-.16,0,.12))
            cushion('chaise_blue_pillow',(w*.15,-l*.20,h*.66),(w*.43,.14,h*.36),m['blue'],assembly=name,rotation=(-.22,0,-.09))
            cloth('chaise_white_throw',(0,l*.25,h*.575),(w*1.01,l*.36,.007),m['white'],fold=.014,seed=8,drape=.12,assembly=name)
        elif name=='plant':plant(name,(0,0,0),p.get('height',1.15),m['green'],m['pot'],stem_material=m['stem'],soil_material=m['soil'])
        else:
            r,h=p.get('radius',.22),p.get('height',.58)
            _cylinder('side_table_lower',(0,0,.035),r,.05,m['brass'],name)
            _cylinder('side_table_waist',(0,0,h*.24),r*.53,h*.40,m['brass'],name,r*.75)
            _cylinder('side_table_middle',(0,0,h*.48),r,.028,m['brass'],name)
            for i in range(3):
                a=i*math.tau/3;_stem(f'side_table_post_{i}',(r*.65*math.cos(a),r*.65*math.sin(a),h*.49),(r*.65*math.cos(a),r*.65*math.sin(a),h*.98),.011,m['brass'],name)
            _cylinder('side_table_top',(0,0,h),r*.89,.025,m['brass'],name)
            box('side_table_sculpture_plinth',(0,0,h+.04),(r*.53,r*.43,.065),m['black'],.005,assembly=name)
            ellipsoid('side_table_sculpture_shoulders',(0,0,h+.15),(r*.85,r*.46,.14),m['bronze'],assembly=name)
            ellipsoid('side_table_sculpture_neck',(0,0,h+.23),(r*.28,r*.28,.13),m['bronze'],assembly=name)
            ellipsoid('side_table_sculpture_head',(0,0,h+.33),(r*.47,r*.42,.19),m['bronze'],assembly=name,rotation=(0,.12,-.14))
        created=[o for o in bpy.data.objects if o not in before]
        root=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(root)
        root['assembly']=name;root['part_id']=name+'_root';root['prior_status']='assumed';root['assumed']=True
        for obj in created:
            if obj.parent is None:obj.parent=root
        root.location=p['center'];root.rotation_euler.z=p.get('rotation_z',0)
        result[name]=dict(root=root,objects=created)
    return result
