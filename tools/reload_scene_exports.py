"""Reopen actual Blender/GLB/USD exports and compare evaluated world bounds.
Run inside Blender: --python reload_scene_exports.py -- EXPORT_DIRECTORY.
Material portability is reported separately from geometric round-trip integrity.
"""
import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
root=Path(sys.argv[sys.argv.index('--')+1]).resolve();scene=json.loads((root/'scene.json').read_text());ids={o['id'] for o in scene['objects']};required_parts={p['object'] for a in scene.get('structure',{}).get('assemblies',[]) for p in a['parts']}
def owner(o):
 current=o
 while current:
  for key in ['entity_id','furniture_id','userProperties:entity_id']:
   value=current.get(key)
   if value in ids:return value
  if current.name in ids:return current.name
  current=current.parent
 return None
def evaluate():
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();bounds={};counts={}
 for inst in deps.object_instances:
  ob=inst.object;entity=owner(ob.original)
  if entity is None or ob.type not in {'MESH','CURVE','SURFACE','FONT','META'} or ob.original.hide_render:continue
  mesh=ob.to_mesh()
  try:
   for vertex in mesh.vertices:
    p=inst.matrix_world@vertex.co
    if entity not in bounds:bounds[entity]=[list(p),list(p)]
    for i in range(3):bounds[entity][0][i]=min(bounds[entity][0][i],p[i]);bounds[entity][1][i]=max(bounds[entity][1][i],p[i])
   counts[entity]=counts.get(entity,0)+len(mesh.vertices)
  finally:ob.to_mesh_clear()
 return bounds,counts
def images():
 rows=[]
 for im in bpy.data.images:
  if im.source in {'VIEWER','GENERATED'}:continue
  packed=bool(im.packed_file) or bool(im.packed_files);p=Path(bpy.path.abspath(im.filepath)).resolve() if im.filepath else None
  rows.append(dict(name=im.name,packed=packed,portable=packed or bool(p and p.is_relative_to(root) and p.exists())))
 return rows
bpy.ops.wm.open_mainfile(filepath=str(root/'scene.blend'));reference,_=evaluate();assert set(reference)==ids,'Authority scene lacks canonical entities';records=[]
cam=bpy.data.objects.get('source_camera');camera_matrix=[list(row) for row in cam.matrix_world] if cam else None
camera_frame_id=cam.get('frame_id') if cam else None
for ext in ['blend','glb','usdc']:
 path=root/('scene.'+ext)
 if ext!='blend':
  bpy.ops.wm.read_factory_settings(use_empty=True)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
  else:bpy.ops.wm.usd_import(filepath=str(path))
 actual,counts=evaluate();missing=sorted(ids-actual.keys());errors={e:max(abs(a-b) for row_a,row_b in zip(reference[e],actual[e]) for a,b in zip(row_a,row_b)) for e in ids&actual.keys()};imgs=images();failures=[]
 names={o.name for o in bpy.context.scene.objects}|{o.data.name for o in bpy.context.scene.objects if o.type in {'MESH','CURVE'}};missing_parts=sorted(required_parts-names)
 if missing_parts:failures.append('Missing editable furniture parts: '+str(missing_parts))
 if missing:failures.append('Missing canonical entities: '+str(missing))
 if any(v>.002 for v in errors.values()):failures.append('Evaluated bounds differ by more than 2 mm')
 if any(not im['portable'] for im in imgs):failures.append('Unpacked image references escape delivery or are missing')
 imported_camera=bpy.data.objects.get('source_camera');camera_error=None
 # USD may collapse Xform/Camera names. Use the preserved explicit frame identity,
 # never pick a camera by proximity to the expected transform.
 if imported_camera is None and camera_frame_id is not None:
  matches=[o for o in bpy.context.scene.objects if o.type=='CAMERA' and o.get('frame_id')==camera_frame_id]
  if len(matches)==1:imported_camera=matches[0]
 if camera_matrix and imported_camera:
  camera_error=max(abs(a-b) for ra,rb in zip(camera_matrix,imported_camera.matrix_world) for a,b in zip(ra,rb))
  if camera_error>1e-4:failures.append('Source camera transform differs after import')
 else:failures.append('Missing source camera after import')
 records.append(dict(format=ext,status='failed' if failures else 'passed',failures=failures,entity_count=len(actual),required_furniture_parts=len(required_parts),missing_parts=missing_parts,maximum_bound_error_m=max(errors.values(),default=0),bounds_error_by_entity_m=errors,vertices_by_entity=counts,source_camera_matrix_max_error=camera_error,source_camera_imported_name=imported_camera.name if imported_camera else None,images=imgs))
result=dict(status='passed' if all(r['status']=='passed' for r in records) else 'failed',records=records,scope='Actual file re-import, evaluated world bounds, source camera transform and texture references. Not independent real-world accuracy. Blender is authoritative; GLB/USD may approximate procedural shaders.')
(root/'reload_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['status']=='passed','Export reload validation failed'
