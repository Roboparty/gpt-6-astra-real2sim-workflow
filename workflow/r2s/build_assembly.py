"""Case-independent editable assembly backend. Blender --python ... -- scene.json model.blend.
Agents supply explicit geometry; unsupported categories are not silently substituted.
"""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector,Matrix
args=sys.argv[sys.argv.index('--')+1:];src=Path(args[0]).resolve();dest=Path(args[1]).resolve();S=json.loads(src.read_text())
if S.get('schema_version')!='real2sim.scene/1.0' or S.get('units')!='m' or S.get('up_axis')!='Z':raise ValueError('Invalid canonical scene')
if not S['room'].get('preserve_full_shell'):raise ValueError('Full enclosure is mandatory')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
materials={}
for key,p in S.get('materials',{'default':{'color':[.75,.75,.72],'roughness':.7}}).items():
 m=bpy.data.materials.new(key);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*p.get('color',[.75,.75,.72]),1);bs.inputs['Roughness'].default_value=p.get('roughness',.7);bs.inputs['Metallic'].default_value=p.get('metallic',0)
 if p.get('image'):
  image=(src.parent/p['image']).resolve()
  if not image.is_relative_to(src.parent):raise ValueError('Texture escapes explicitly staged model directory')
  tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(image));m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color'])
 materials[key]=m
default=next(iter(materials.values()))
def build_part(p,parent,entity):
 typ=p['type'];loc=p.get('position',[0,0,0]);dims=p.get('dimensions',[1,1,1])
 if typ=='box':bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 elif typ=='cylinder':bpy.ops.mesh.primitive_cylinder_add(vertices=p.get('segments',48),radius=p['radius'],depth=p['depth'],location=loc);o=bpy.context.object
 elif typ=='sphere':bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1,location=loc);o=bpy.context.object;o.scale=[x/2 for x in dims]
 elif typ in {'mesh','extrusion'}:
  if typ=='mesh':verts=p['vertices'];faces=p['faces']
  else:
   ring=p['outline_xy'];n=len(ring);verts=[[*v,z] for z in p['z_bounds'] for v in ring];faces=[list(range(n-1,-1,-1)),list(range(n,2*n))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
  me=bpy.data.meshes.new(p['name']);me.from_pydata(verts,[],faces);me.update();o=bpy.data.objects.new(p['name'],me);bpy.context.collection.objects.link(o);o.location=loc
  if p.get('uv'):
   uv=me.uv_layers.new()
   for poly in me.polygons:
    for li in poly.loop_indices:uv.data[li].uv=p['uv'][me.loops[li].vertex_index]
 elif typ=='curve':
  cu=bpy.data.curves.new(p['name'],'CURVE');cu.dimensions='3D';cu.bevel_depth=p['radius'];cu.bevel_resolution=3;sp=cu.splines.new('POLY');sp.points.add(len(p['points'])-1)
  for point,xyz in zip(sp.points,p['points']):point.co=(*xyz,1)
  sp.use_cyclic_u=p.get('closed',False);o=bpy.data.objects.new(p['name'],cu);bpy.context.collection.objects.link(o);o.location=loc
 else:raise ValueError('Unsupported primitive '+typ+'; Agent must author an explicit mesh or custom builder')
 o.name=p['name'];o.parent=parent;o.rotation_euler=p.get('rotation_euler',[0,0,0]);o['entity_id']=entity;o['evidence']=json.dumps(p.get('evidence',[]));o['layout_locked']=True;o.data.materials.append(materials.get(p.get('material'),default))
 if p.get('bevel') and o.type=='MESH':b=o.modifiers.new('editable bevel','BEVEL');b.width=p['bevel'];b.segments=4
 if p.get('smooth') and o.type=='MESH':
  for face in o.data.polygons:face.use_smooth=True
 return o
r=S['room'];xm,xM,ym,yM,h,t=[r[k] for k in ['x_min','x_max','y_min','y_max','height','thickness']]
shell=[('floor',[(xm+xM)/2,(ym+yM)/2,-t/2],[xM-xm,yM-ym,t]),('ceiling',[(xm+xM)/2,(ym+yM)/2,h+t/2],[xM-xm,yM-ym,t]),('wall_back',[(xm+xM)/2,yM+t/2,h/2],[xM-xm+2*t,t,h]),('wall_front',[(xm+xM)/2,ym-t/2,h/2],[xM-xm+2*t,t,h]),('wall_left',[xm-t/2,(ym+yM)/2,h/2],[t,yM-ym,h]),('wall_right',[xM+t/2,(ym+yM)/2,h/2],[t,yM-ym,h])]
for name,pos,dims in shell:build_part({'name':name,'type':'box','position':pos,'dimensions':dims,'material':r.get('material'),'evidence':['room enclosure specification']},None,name)
for entity in S['objects']:
 if S.get('branch','A')=='A' and entity.get('asset_resolution',{}).get('mode')=='exact':raise ValueError('Exact external geometry forbidden in A')
 parts=entity.get('parameters',{}).get('parts')
 if not parts:raise ValueError(entity['id']+' has no explicit parts; use a custom Agent builder')
 bpy.ops.object.empty_add();root=bpy.context.object;root.name=entity['id'];root.location=entity['position'];root.rotation_euler[2]=entity.get('rotation_z',0);root['scene_spec']=json.dumps(entity);root['entity_id']=entity['id'];root['layout_locked']=entity.get('layout_lock',True)
 for p in parts:build_part(p,root,entity['id'])
cam=S['camera'];bpy.ops.object.camera_add(location=cam['position']);camera=bpy.context.object;camera.name='source_camera';camera.rotation_euler=(Matrix(cam['rotation_world_to_cv']).transposed()@Matrix(((1,0,0),(0,-1,0),(0,0,-1)))).to_euler();W,H=cam['image_size'];camera.data.sensor_fit='HORIZONTAL';camera.data.sensor_width=36;camera.data.lens=cam['focal_px']*36/W;camera.data.shift_x=(W/2-cam['principal_point'][0])/W;camera.data.shift_y=(cam['principal_point'][1]-H/2)/W
for i,light in enumerate(S.get('illumination',[])):
 bpy.ops.object.light_add(type='AREA',location=light['position']);o=bpy.context.object;o.name=light.get('id',f'illumination_{i}');o.data.energy=light['power'];o.data.size=light['size'];o.rotation_euler=(Vector(light['target'])-o.location).to_track_quat('-Z','Y').to_euler();o['evidence']=json.dumps(light.get('evidence',[]))
sc=bpy.context.scene;sc.camera=camera;sc.render.engine='CYCLES';sc.cycles.samples=64;sc.cycles.use_denoising=True;sc.render.resolution_x=W;sc.render.resolution_y=H;sc.render.resolution_percentage=100;sc['case_id']=S['case_id'];sc['input_provenance']=json.dumps(S.get('input_provenance',{}));bpy.ops.file.pack_all();dest.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(dest))
