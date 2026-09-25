import os
"""Shared Blender export/geometry audit; never modifies object placement."""
import bpy,bmesh,sys,json,math,hashlib
from pathlib import Path
from collections import defaultdict
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0,str(Path(__file__).parent))
from viewpoints import diagnostic_focus,safe_camera_position
args=sys.argv[sys.argv.index('--')+1:]; SPEC=Path(args[0]).resolve();OUT=Path(args[1]).resolve();OUT.mkdir(exist_ok=True,parents=True)
S=json.loads(SPEC.read_text());sc=bpy.context.scene;original_camera=sc.camera
from blender_metadata import synchronize
(OUT/'metadata_export_check.json').write_text(json.dumps(synchronize(S),indent=2))
try:
 cp=bpy.context.preferences.addons['cycles'].preferences;cp.compute_device_type='CUDA';cp.get_devices()
 for d in cp.devices:d.use=d.type=='CUDA'
 sc.cycles.device='GPU' if os.environ.get('R2S_CPU')!='1' and any(d.use for d in cp.devices) else 'CPU'
except Exception:sc.cycles.device='CPU'
groups=defaultdict(list)
for o in bpy.data.objects:
 if o.type in {'MESH','CURVE'}:groups[o.get('entity_id',o.name)].append(o)
semantic_roots_created=[]
for key,objects in groups.items():
 if bpy.data.objects.get(key) is None:
  root=bpy.data.objects.new(key,None);bpy.context.collection.objects.link(root);root['entity_id']=key;root['layout_locked']=True;semantic_roots_created.append(key)
  for obj in objects:
   transform=obj.matrix_world.copy();obj.parent=root;obj.matrix_world=transform
# Stable data names survive USD importers that merge parent Xforms into their mesh children.
for obj in bpy.context.scene.objects:
 if obj.type in {'MESH','CURVE'}:
  if obj.data.users>1:obj.data=obj.data.copy()
  obj.data.name=obj.name
sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1.0
required=['wall_back','wall_front','wall_left','wall_right','floor','ceiling']
assert all(k in groups for k in required),f'Missing full enclosure: {set(required)-set(groups)}'
assert all(not o.hide_render for k in required for o in groups[k]),'Enclosure hidden in render'
repaired=0
for o in bpy.data.objects:
 if o.type=='MESH':
  bm=bmesh.new();bm.from_mesh(o.data);n=len(bm.verts)
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-9)
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));repaired+=n-len(bm.verts);bm.to_mesh(o.data);bm.free()
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();report={'schema':'real2sim.geometry-audit/1','branch':S.get('branch','A'),'spec_sha256':hashlib.sha256(SPEC.read_bytes()).hexdigest(),'enclosure_present':required,'enclosure_hidden':False,'merged_duplicate_vertices':repaired,'semantic_roots_created':semantic_roots_created,'units':'metres','unit_scale':1.0,'entities':{},'warnings':[]}
meshdir=OUT/'meshes';meshdir.mkdir(exist_ok=True)
for key,obs in sorted(groups.items()):
 root=bpy.data.objects.get(key);rootmat=root.matrix_world.copy() if root and root.type=='EMPTY' else Matrix.Identity(4);inv=rootmat.inverted();vs=[];fs=[];world=[];bad=0;deg=0
 for o in obs:
  ev=o.evaluated_get(deps);me=ev.to_mesh();me.calc_loop_triangles();offset=len(vs);T=inv@o.matrix_world
  for v in me.vertices:
   co=T@v.co;wc=o.matrix_world@v.co
   if not all(math.isfinite(x) for x in co):bad+=1
   vs.append(tuple(co));world.append(tuple(wc))
  for tr in me.loop_triangles:
   if tr.area<1e-12:deg+=1;continue
   fs.append(tuple(offset+i for i in tr.vertices))
  ev.to_mesh_clear()
 assert bad==0 and vs and fs,f'Invalid geometry {key}'
 localmin=[min(v[i] for v in vs) for i in range(3)];localmax=[max(v[i] for v in vs) for i in range(3)];wmin=[min(v[i] for v in world) for i in range(3)];wmax=[max(v[i] for v in world) for i in range(3)]
 with (meshdir/f'{key}.obj').open('w') as f:
  f.write('# real2sim local entity mesh; metres Z up; visual geometry only\n')
  for v in vs:f.write('v '+' '.join(f'{x:.7f}' for x in v)+'\n')
  for tr in fs:f.write('f '+' '.join(str(x+1) for x in tr)+'\n')
 report['entities'][key]={'vertices':len(vs),'triangles':len(fs),'degenerate_triangles_removed':deg,'world_aabb':[wmin,wmax],'local_aabb':[localmin,localmax],'root_position':list(rootmat.translation),'root_quaternion_wxyz':list(rootmat.to_quaternion()),'visual_mesh':f'meshes/{key}.obj'}
 if key not in required and wmin[2]<-.005:report['warnings'].append({'entity':key,'type':'below_floor','min_z':wmin[2]})
# Camera verification uses actual Blender projection, including principal-point shift.
cam=S['camera'];land=[]
for p in cam.get('fit_landmarks',[]):
 co=world_to_camera_view(sc,sc.camera,Vector(p['xyz']));uv=[co.x*cam['image_size'][0],(1-co.y)*cam['image_size'][1]];err=math.dist(uv,p['uv']);land.append({'target':p['uv'],'render':uv,'error_px':err})
report['camera_reprojection']=land
report['material_portability']='Blender preserves procedural shaders; GLB/USD preserve image textures and supported PBR inputs, but procedural wood/fabric may become flat approximations.'
(OUT/'geometry_audit.json').write_text(json.dumps(report,indent=2))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'scene.blend'))
# Portable visual export; every wall and lamp remains in the model.
bpy.ops.export_scene.gltf(filepath=str(OUT/'scene.glb'),export_format='GLB',export_apply=True,export_extras=True,export_cameras=True,export_lights=True)
try:
 # USD native curves can round-trip with different widths. Export evaluated mesh copies,
 # then restore the original editable curves for the Blender scene and further renders.
 temporary=[]
 for original in list(bpy.context.scene.objects):
  if original.type!='CURVE':continue
  name=original.name;collections=list(original.users_collection);evaluated=original.evaluated_get(deps);me=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=deps);original.name=name+'__native_curve_temp';me.name=name;obj=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(obj);obj.parent=original.parent;obj.matrix_parent_inverse=original.matrix_parent_inverse.copy();obj.matrix_basis=original.matrix_basis.copy()
  for key in original.keys():obj[key]=original[key]
  for collection in collections:collection.objects.unlink(original)
  temporary.append((original,name,collections,obj,me))
 bpy.context.view_layer.update()
 try:bpy.ops.wm.usd_export(filepath=str(OUT/'scene.usdc'),export_materials=True,generate_preview_surface=True,export_textures=True,relative_paths=True,export_custom_properties=True,author_blender_name=True)
 finally:
  for original,name,collections,obj,me in temporary:
   bpy.data.objects.remove(obj,do_unlink=True);bpy.data.meshes.remove(me);original.name=name
   for collection in collections:collection.objects.link(original)
  bpy.context.view_layer.update()
 report['usd_export']='success'
 report['usd_curve_policy']='evaluated mesh copies; editable native curves retained in scene.blend'
except Exception as e:report['usd_export']={'status':'failed','error':str(e)}
# Additional interior views are diagnostics of completed, unobserved geometry, not held-out real-photo tests.
r=S['room'];xm,xM,ym,yM,h=[r[k] for k in ['x_min','x_max','y_min','y_max','height']];dx=xM-xm;dy=yM-ym
focus=diagnostic_focus(S)
views=[('interior_reverse',(xm+dx*.2,yM-dy*.08,h*.65),focus),('interior_wide',(xM-dx*.12,ym+dy*.12,h*.73),focus),('interior_left',(xm+dx*.08,ym+dy*.25,h*.60),focus)]
sc.render.resolution_x=S['camera']['image_size'][0]*2;sc.render.resolution_y=S['camera']['image_size'][1]*2;sc.cycles.samples=128;sc.render.filepath=str(OUT/'source_view_high.png');bpy.ops.render.render(write_still=True)
sc.cycles.samples=64
for name,pos,target in views:
 pos=safe_camera_position(S,pos);bpy.ops.object.camera_add(location=pos);camera=bpy.context.object;camera.name='diagnostic_'+name;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=22;sc.camera=camera
 sc.render.resolution_x=960;sc.render.resolution_y=640;sc.render.resolution_percentage=100;sc.render.filepath=str(OUT/f'{name}.png');bpy.ops.render.render(write_still=True)
sc.camera=original_camera;W,H=cam['image_size'];sc.render.resolution_x=W;sc.render.resolution_y=H
# Emissive ID render has no textures, shadows or material confounds.
def linear(x):return x/12.92 if x<.04045 else ((x+.055)/1.055)**2.4
palette={}
for i,key in enumerate(sorted(groups)):
 rgb=[32+(i*73)%208,32+(i*107)%208,32+(i*151)%208];palette[key]=rgb
 m=bpy.data.materials.new('id_'+key);m.use_nodes=True;m.node_tree.nodes.clear();e=m.node_tree.nodes.new('ShaderNodeEmission');e.inputs[0].default_value=(*[linear(v/255) for v in rgb],1);out=m.node_tree.nodes.new('ShaderNodeOutputMaterial');m.node_tree.links.new(e.outputs[0],out.inputs['Surface'])
 for o in groups[key]:o.data.materials.clear();o.data.materials.append(m)
sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=0;sc.cycles.samples=1;sc.cycles.use_denoising=False;sc.render.filepath=str(OUT/'entity_ids.png');bpy.ops.render.render(write_still=True)
(OUT/'entity_palette.json').write_text(json.dumps(palette,indent=2));(OUT/'geometry_audit.json').write_text(json.dumps(report,indent=2))
print('EXPORT_AUDIT_COMPLETE',str(OUT),len(report['entities']))
