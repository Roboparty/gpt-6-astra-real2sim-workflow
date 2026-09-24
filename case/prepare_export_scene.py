"""Capture authoritative evaluated geometry before any exporter cleanup.
The native editable scene stays unchanged on disk. Only an export copy is baked.
"""
import bpy,sys,json,hashlib
from pathlib import Path
from collections import defaultdict
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True);native=Path(bpy.data.filepath);deps=bpy.context.evaluated_depsgraph_get();items=[];groups=defaultdict(list)
for o in list(bpy.context.scene.objects):
 if o.type not in ['MESH','CURVE']:continue
 me=bpy.data.meshes.new_from_object(o.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps);groups[o.get('entity_id',o.name)].extend([list(o.matrix_world@v.co) for v in me.vertices]);items.append((o,me))
audit=dict(schema='real2sim.authority-bounds/1',source_native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),evaluation='native modifier-evaluated VIEWPORT geometry before export cleanup',units='m',entities={})
for key,vs in groups.items():audit['entities'][key]={'world_aabb':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]],'vertices':len(vs)}
(out/'authority_geometry_audit.json').write_text(json.dumps(audit,indent=2))
for o,me in items:
 name=o.name;me.name=name
 if o.type=='MESH':o.modifiers.clear();o.data=me
 else:
  cols=list(o.users_collection);parent=o.parent;matrix=o.matrix_world.copy();props=dict(o.items());bpy.data.objects.remove(o,do_unlink=True);n=bpy.data.objects.new(name,me)
  for col in cols:col.objects.link(n)
  n.parent=parent;n.matrix_world=matrix
  for key,value in props.items():n[key]=value
for o in bpy.context.scene.objects:
 if o.type=='CAMERA':o.data.name=o.name
bpy.context.view_layer.update();bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
