"""Run inside Blender: test actual asymmetric/off-axis projection after transfer."""
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix,Vector
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow'))
from r2s.blender_camera import apply_camera

reports=[]
for fx,fy in [(762.8,762.8),(710.,530.),(490.,830.)]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;bpy.ops.object.camera_add();camera=bpy.context.object
    spec=dict(image_size=[640,480],position=[1,2,3],rotation_world_to_cv=[[0,1,0],[-1,0,0],[0,0,1]],focal_px=fx,focal_y_px=fy,principal_point=[287.3,251.2],pixel_coordinates='integer_centers')
    apply_camera(scene,camera,spec);scene.render.resolution_percentage=100;bpy.context.view_layer.update()
    errors=[]
    for u,v in [(0,0),(639,0),(0,479),(639,479),(320,240)]:
        world=Vector(spec['position'])+Matrix(spec['rotation_world_to_cv']).transposed()@Vector(((u-287.3)/fx,(v-251.2)/fy,1))
        projected=world_to_camera_view(scene,camera,world)
        errors.append(float(np.linalg.norm([projected.x*640-.5-u,(1-projected.y)*480-.5-v])))
    assert max(errors)<.001,(fx,fy,errors)
    reports.append(dict(fx=fx,fy=fy,maximum_projection_error_px=max(errors)))
print('CAMERA_BLENDER_PASSED',json.dumps(reports))
