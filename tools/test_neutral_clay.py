"""Real render regression for an enclosed room with no interior source light."""
import sys,tempfile
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workflow/r2s'))
from blender_appearance import neutral_view
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=4;sc.render.resolution_x=48;sc.render.resolution_y=48;sc.render.resolution_percentage=100
for pos,sz in [((0,0,-.05),(4,4,.1)),((0,0,3.05),(4,4,.1)),((0,2,1.5),(4,.1,3)),((0,-2,1.5),(4,.1,3)),((2,0,1.5),(.1,4,3)),((-2,0,1.5),(.1,4,3))]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);bpy.context.object.dimensions=sz
world=bpy.data.worlds.new('black');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Strength'].default_value=0;sc.world=world
bpy.ops.object.camera_add(location=(0,-1,1.5));cam=bpy.context.object;cam.rotation_euler=(Vector((0,1,1.5))-cam.location).to_track_quat('-Z','Y').to_euler();sc.camera=cam
clay=bpy.data.materials.new('clay');clay.use_nodes=True;sc.view_layers[0].material_override=clay;sc.view_settings.exposure=1.2
scene={'room':dict(x_min=-2,x_max=2,y_min=-2,y_max=2,height=3),'objects':[]}
lights=set(o for o in sc.objects if o.type=='LIGHT')
with tempfile.TemporaryDirectory() as tmp:
 neutral_view(tmp,scene,'source_clay.png')
 image=bpy.data.images.load(str(Path(tmp)/'source_clay.png'));pixels=list(image.pixels);assert max(pixels[0::4])>.1
 assert sc.world==world and sc.camera==cam and abs(sc.view_settings.exposure-1.2)<1e-6
 assert sc.view_layers[0].material_override==clay and set(o for o in sc.objects if o.type=='LIGHT')==lights
print('NEUTRAL_CLAY_ENCLOSURE_OK')
