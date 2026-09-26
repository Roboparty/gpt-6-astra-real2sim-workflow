"""Blender regression: canonical bounds are world AABBs, never bottom origins."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow/r2s'))
from viewpoints import safe_camera_position
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1));o=bpy.context.object;o.dimensions=(2,2,2);o['entity_id']='cabinet'
bpy.context.view_layer.update()
scene={'room':{'x_min':-3,'x_max':3,'y_min':-3,'y_max':3,'height':3},'objects':[{'id':'cabinet','kind':'furniture','position':[0,0,1],'dimensions':[2,2,2],'rotation_z':.7}]}
# Above the true top (2m), with a clear view of its center. Old bottom-origin
# logic rejected this ideal point and selected a different camera.
ideal=(0,0,2.8)
assert tuple(safe_camera_position(scene,ideal))==ideal
# Narrow world bounds must not be rotated a second time.
o.dimensions=(2,.2,2);scene['objects'][0]['dimensions']=[2,.2,2];bpy.context.view_layer.update()
ideal=(0,.8,1)
assert tuple(safe_camera_position(scene,ideal))==ideal
print('VIEWPOINT_WORLD_AABB_OK')
