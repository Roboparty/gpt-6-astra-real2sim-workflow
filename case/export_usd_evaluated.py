"""Export a faithful evaluated USD snapshot; preserve the editable .blend on disk."""
import bpy,sys,json
from pathlib import Path
out=Path(sys.argv[sys.argv.index('--')+1]);sc=bpy.context.scene;deps=bpy.context.evaluated_depsgraph_get();items=[]
for o in list(sc.objects):
 if o.type in ['MESH','CURVE']:
  me=bpy.data.meshes.new_from_object(o.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps);items.append((o,me))
for o,me in items:
 name=o.name;me.name=name
 if o.type=='MESH':o.modifiers.clear();o.data=me
 else:
  cols=list(o.users_collection);parent=o.parent;matrix=o.matrix_world.copy();props=dict(o.items());bpy.data.objects.remove(o,do_unlink=True);n=bpy.data.objects.new(name,me)
  for col in cols:col.objects.link(n)
  n.parent=parent;n.matrix_world=matrix
  for key,value in props.items():n[key]=value
for o in sc.objects:
 if o.type=='CAMERA':o.data.name=o.name
bpy.context.view_layer.update();bpy.ops.wm.usd_export(filepath=str(out),export_materials=True,generate_preview_surface=True,export_textures=True,relative_paths=True,export_custom_properties=True,author_blender_name=True,export_cameras=True,export_subdivision='TESSELLATE',evaluation_mode='VIEWPORT')
(out.parent/'usd_export_adapter.json').write_text(json.dumps(dict(status='exported',evaluation='evaluated viewport geometry, same as canonical geometry audit',subdivision='baked mesh; no implicit extra subdivision on import',curves='evaluated mesh copies',camera_names='camera data names normalized to stable object ids',native_blend_modified=False,roundtrip_validation='required separately'),indent=2))
