"""Reopen the saved artifact; verify editable parts and retained real-view cameras."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
import numpy as np


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);d=a.directory
if (d/'model_check.json').exists():raise ValueError('Retain previous model check')
before=sha(d/'scene.blend');receipt=json.loads((d/'receipt.json').read_text());assert before==receipt['model_sha256']
bpy.ops.wm.open_mainfile(filepath=str(d/'scene.blend'))
scene=bpy.context.scene;meshes=[o for o in scene.objects if o.type=='MESH'];cameras=[o for o in scene.objects if o.type=='CAMERA']
assert len(meshes)==receipt['mesh_parts']==173 and len(cameras)==6
assert all(len(o.data.vertices)>0 and len(o.data.polygons)>0 for o in meshes)
assert all(o.get('assembly') for o in meshes)
assert not any(o.rigid_body or any(m.type in {'CLOTH','SOFT_BODY'} for m in o.modifiers) for o in scene.objects)
recorded=json.loads((d/'cameras.json').read_text());errors=[]
for row in recorded:
    obj=bpy.data.objects[f'real_view_{row["frame"]:02d}'];error=float(np.max(abs(np.asarray(obj.matrix_world)-row['matrix_world'])))
    assert error<1e-5;errors.append(error)
packed=[im.name for im in bpy.data.images if im.packed_file]
assert packed and sha(d/'scene.blend')==before
result=dict(status='passed',model_sha256=before,model_bytes=(d/'scene.blend').stat().st_size,
    editable_mesh_parts=len(meshes),real_source_cameras=len(cameras),packed_images=packed,
    max_saved_camera_matrix_error=max(errors),active_dynamics=False,
    named_assemblies=receipt['assemblies'],scale_status='learned_unvalidated; author dimensions assumed',
    scope='Actual saved Blender reopen/structure/camera preservation only. Not visual acceptance, measured geometry, collision or robotics qualification.')
(d/'model_check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
