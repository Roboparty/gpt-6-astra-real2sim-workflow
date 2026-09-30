"""Reopen saved Desk1 authoring outputs without modifying either model."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import bmesh

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def snapshot(path):
    bpy.ops.wm.open_mainfile(filepath=str(path));scene=bpy.context.scene;parts=[]
    for obj in sorted(scene.objects,key=lambda o:o.name):
        if obj.type!='MESH' or not obj.get('object_id'):continue
        bm=bmesh.new();bm.from_mesh(obj.data)
        parts.append(dict(name=obj.name,object_id=obj['object_id'],closed=all(e.is_manifold for e in bm.edges),
            volume_m3_abs=abs(bm.calc_volume()),vertices=[list(v.co) for v in obj.data.vertices],
            matrix_world=[list(r) for r in obj.matrix_world]))
        bm.free()
    camera=scene.camera
    return dict(parts=parts,camera={'matrix':[list(r) for r in camera.matrix_world],'lens':camera.data.lens,'sensor_width':camera.data.sensor_width},
                packed_images=[{'name':im.name,'sha256':hashlib.sha256(bytes(im.packed_file.data)).hexdigest()} for im in bpy.data.images if im.packed_file])

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
one=a.root/'authoring_001/scene.blend';two=a.root/'authoring_002/scene.blend';before={str(f):sha(f) for f in (one,two)}
x=snapshot(one);y=snapshot(two)
assert x['parts']==y['parts'] and x['camera']==y['camera']
assert len(y['parts'])==6 and len({p['object_id'] for p in y['parts']})==4
assert all(p['closed'] and p['volume_m3_abs']>0 for p in y['parts'])
assert any(im['sha256']=='f125bdbe59e6e978d22e5143131291a1ef5206239928007a01d26aabb1bb9578' for im in y['packed_images'])
assert before=={str(f):sha(f) for f in (one,two)}
report=dict(status='passed',model_sha256=before[str(two)],model_bytes=two.stat().st_size,object_count=4,foreground_mesh_parts=6,
    part_checks=[{k:p[k] for k in ('name','object_id','closed','volume_m3_abs')} for p in y['parts']],
    foreground_geometry_and_camera_unchanged_between_versions=True,packed_images=y['packed_images'],
    scope='Saved editable closed meshes and image packing verified; dimensions/camera are assumptions, no GT/physics accuracy claim.')
out=a.root/'authoring_002/model_check.json'
with out.open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
