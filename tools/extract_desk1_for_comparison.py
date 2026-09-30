"""Read-only Blender geometry/camera audit; never save or alter the input blend."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from bpy_extras.object_utils import world_to_camera_view

def main():
    p=argparse.ArgumentParser();p.add_argument('--blend',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);before=hashlib.sha256(a.blend.read_bytes()).hexdigest()
    if a.output.exists():raise ValueError('Preserve previous audit')
    bpy.ops.wm.open_mainfile(filepath=str(a.blend));scene=bpy.context.scene;cam=scene.camera;rows=[]
    for obj in scene.objects:
        if obj.type!='MESH' or not obj.get('object_id'):continue
        v=[obj.matrix_world@vertex.co for vertex in obj.data.vertices];pixels=[]
        for x in v:
            uv=world_to_camera_view(scene,cam,x);pixels.append([float(uv.x*1280),float((1-uv.y)*720)])
        rows.append({'name':obj.name,'object_id':obj['object_id'],'vertices_world':[list(x) for x in v],
            'projected_vertices_1280':pixels,'faces':[list(p.vertices) for p in obj.data.polygons]})
    after=hashlib.sha256(a.blend.read_bytes()).hexdigest();assert before==after
    a.output.write_text(json.dumps({'model_sha256':before,'source_model_unchanged':True,'objects':rows,
        'camera_world_matrix':[list(row) for row in cam.matrix_world],'camera_lens_mm':cam.data.lens},indent=2));print(a.output)

if __name__=='__main__':main()
