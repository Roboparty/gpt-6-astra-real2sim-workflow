"""Run in Blender: stale transformed/modifier/curve AABBs must fail then synchronize."""
import sys, math
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow/r2s'))
from blender_metadata import synchronize
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(1,2,1)); obj=bpy.context.object; obj['entity_id']='chair'
obj.rotation_euler.z=.4; obj.scale=(.2,.3,.5)
mod=obj.modifiers.new('expanded actual surface','SOLIDIFY'); mod.thickness=.077
scene={'objects':[{'id':'chair','position':[0,0,0],'dimensions':[1,1,1]}]}
try:synchronize(scene)
except ValueError:pass
else:raise AssertionError('Stale metadata was accepted')
synchronize(scene,True); synchronize(scene)
before=scene['objects'][0]['dimensions'][:]
obj.data.vertices[0].co.y-=.5
try:synchronize(scene)
except ValueError:pass
else:raise AssertionError('Local edit was not detected')
synchronize(scene,True); synchronize(scene)
assert scene['objects'][0]['dimensions']!=before
curve=bpy.data.curves.new('tube','CURVE');curve.dimensions='3D';curve.bevel_depth=.1
sp=curve.splines.new('POLY');sp.points.add(1);sp.points[0].co=(0,0,0,1);sp.points[1].co=(1,1,1,1)
ob=bpy.data.objects.new('tube',curve);bpy.context.collection.objects.link(ob);ob['entity_id']='chair';ob.location=(3,0,1)
synchronize(scene,True);synchronize(scene)
assert scene['objects'][0]['dimensions'][0]>2
ob.hide_render=True;synchronize(scene,True);synchronize(scene)
# A modifier that changes the actual envelope, plus a transformed parent. This
# fails if the implementation reads base vertices or ignores evaluated matrices.
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj['entity_id']='array'
mod=obj.modifiers.new('Evaluated duplicate','ARRAY');mod.count=2;mod.relative_offset_displace=(1.5,0,0)
parent=bpy.data.objects.new('Rotated parent',None);bpy.context.collection.objects.link(parent)
parent.location=(.127,.077,0);parent.rotation_euler.z=math.pi/2;obj.parent=parent
scene={'objects':[{'id':'array','position':[0,0,0],'dimensions':[1,1,1]}]}
synchronize(scene,True)
for actual,expected in zip(scene['objects'][0]['dimensions'],[2,5,2]):assert abs(actual-expected)<1e-5
for actual,expected in zip(scene['objects'][0]['position'],[.127,1.577,0]):assert abs(actual-expected)<1e-5
synchronize(scene)
print('EVALUATED_METADATA_REGRESSION_PASSED')
