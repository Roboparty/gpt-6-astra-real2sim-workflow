"""Read-only dependency and editability checks on assembled models."""
import bpy,json,sys
from pathlib import Path
r=Path(sys.argv[sys.argv.index('--')+1]).resolve()
result={}
for b in ['A','B']:
 records=[]
 for ext in ['blend','usdc','glb']:
  f=r/'outputs'/b/('scene.'+ext)
  if ext=='blend':bpy.ops.wm.open_mainfile(filepath=str(f))
  else:
   bpy.ops.wm.read_factory_settings(use_empty=True)
   if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(f))
   else:bpy.ops.wm.usd_import(filepath=str(f))
  images=[]
  for im in bpy.data.images:
   if im.source in ['VIEWER','GENERATED']:continue
   path=Path(bpy.path.abspath(im.filepath)).resolve() if im.filepath else None
   packed=bool(im.packed_file) or bool(im.packed_files)
   portable=packed or (path is not None and path.is_relative_to(r) and path.exists())
   images.append(dict(name=im.name,packed=packed,portable=portable,path=(str(path.relative_to(r)) if path and path.is_relative_to(r) else ('packed_original_reference' if packed else str(path)))))
  records.append(dict(file=f.name,objects=len(bpy.data.objects),mesh_objects=sum(o.type=='MESH' for o in bpy.data.objects),modifier_count=sum(len(o.modifiers) for o in bpy.data.objects),images=images))
  assert all(i['portable'] for i in images),(b,ext,images)
 result[b]=records
(r/'evidence/package_blender_dependencies.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
