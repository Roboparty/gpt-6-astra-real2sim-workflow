import os
import bpy,sys,json,hashlib
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];out=Path(args[0]);out.mkdir(parents=True,exist_ok=True);variant=int(args[1]) if len(args)>1 else 1
sc=bpy.context.scene
# The labelled image-only exterior plate is not an inferred opaque building.
# It must not block the independently fitted sun/sky illumination.
for o in sc.objects:
 if o.get('entity_id')=='exterior_backdrop':o.visible_shadow=False;o.visible_diffuse=False
# Only lights/world change. Camera, geometry, albedo and exposure are fixed.
for o in list(bpy.data.objects):
 if o.type=='LIGHT':bpy.data.objects.remove(o,do_unlink=True)
def light(name,kind,pos,energy,color,size,target):
 d=bpy.data.lights.new(name,kind);d.energy=energy;d.color=color
 if kind=='AREA':d.shape='RECTANGLE';d.size=size;d.size_y=size
 o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=pos;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
sky=[1.4,2.5,3.2][min(variant-1,2)];power=[1400,2600,3500][min(variant-1,2)];sunpower=3.2
if variant==4:sky=.02;power=0;sunpower=12
if variant==5:sky=1.0;power=900;sunpower=16
if variant==6:sky=.5;power=450;sunpower=16
if variant==7:sky=.65;power=650;sunpower=16
if variant==8:sky=.65;power=650;sunpower=16
if variant==9:sky=.65;power=650;sunpower=12
if variant==10:sky=.65;power=650;sunpower=24
sc.world.node_tree.nodes['Background'].inputs[0].default_value=(.78,.86,1,1);sc.world.node_tree.nodes['Background'].inputs[1].default_value=sky
light('window_sky','AREA',(2,1.5,2.4),power,(.88,.94,1),4,(2,-2,1));sunpos=(3,6,9) if variant!=5 else (2.4,10,11.8);suntarget=(3,-1,0) if variant!=5 else (0,0,0)
if variant==6:sunpos=(-14,10,13);suntarget=(0,0,0)
if variant==7:sunpos=(-3.5,10,14.5);suntarget=(0,0,0)
if variant==8:sunpos=(4,10,8);suntarget=(0,0,0)
if variant==9:sunpos=(4,10,8);suntarget=(0,0,0)
if variant==10:sunpos=(9,10,8);suntarget=(0,0,0)
sun=light('daylight_sun','SUN',sunpos,sunpower,(1,.94,.78),1,suntarget);sun.data.angle=.018
if variant==10:sun.data.color=(1,.98,.65)
light('left_window_sky','AREA',(-1,-.6,2),power*.25,(.91,.96,1),1,(2,-.6,.5))
if variant==5:light('inferred_broad_secondary_illumination','AREA',(2.5,-4.4,2.1),250,(1,.97,.90),3.2,(1.8,0,1.6))
if variant==6:light('inferred_broad_secondary_illumination','AREA',(2.5,-4.4,2.1),100,(1,.97,.90),3.2,(1.8,0,1.6))
if variant==7:light('inferred_broad_secondary_illumination','AREA',(2.5,-4.4,2.1),130,(1,.97,.90),3.2,(1.8,0,1.6))
if variant==8:light('inferred_broad_secondary_illumination','AREA',(3.6,-1.4,1.7),130,(1,.97,.90),2.5,(.4,-1.4,1.7))
if variant==9:light('inferred_broad_secondary_illumination','AREA',(2.5,-4.4,2.1),180,(1,.97,.90),3.2,(1.8,0,1.6))
if variant==10:light('inferred_broad_secondary_illumination','AREA',(2.5,-4.4,2.1),180,(1,.97,.90),3.2,(1.8,0,1.6))
sc.render.resolution_percentage=100;sc.cycles.samples=48
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 sc.cycles.device='CPU' if os.environ.get('R2S_CPU')=='1' else 'GPU'
except:pass
sc.render.filepath=str(out/'lighting.png');bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));bpy.ops.render.render(write_still=True)
(out/'light_parameters.json').write_text(json.dumps(dict(variant=variant,world_strength=sky,window_area_watts=power,left_window_watts=power*.25,sun_strength=sunpower,sun_direction=list(Vector(suntarget)-Vector(sunpos)),sun_angle_rad=.018,exterior_plate_shadow=False,exterior_plate_diffuse=False,secondary_illumination='inferred broad reflected-light approximation, not recovered fixture; 250 W' if variant==5 else None,exposure=sc.view_settings.exposure,color_management=sc.view_settings.view_transform,camera_matrix=[list(x) for x in sc.camera.matrix_world],lights=[dict(name=o.name,type=o.data.type,energy=o.data.energy,color=list(o.data.color),position=list(o.location)) for o in sc.objects if o.type=='LIGHT']),indent=2))
