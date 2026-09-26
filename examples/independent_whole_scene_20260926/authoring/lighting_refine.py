import bpy,sys,json,shutil
from pathlib import Path
from mathutils import Vector
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow/r2s'))
from blender_appearance import snapshot
state=json.loads((R/'case/runs/state.json').read_text());out=Path(state['stages']['agent_calibrate_lighting']['directory']);matdir=Path(state['stages']['agent_materials']['directory']);scene=json.loads((matdir/'scene.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(matdir/'model.blend'));sc=bpy.context.scene;accepted=snapshot()
for name in ['material_source_preview.png','material_neutral.png']:shutil.copyfile(matdir/name,out/name)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
sc.cycles.device='GPU';sc.cycles.samples=48
light=bpy.data.objects['window_daylight'];light.location=(scene['room']['x_min']+.20,.40,.85);light.rotation_euler=(Vector((.4,.5,.15))-light.location).to_track_quat('-Z','Y').to_euler();light.data.shape='RECTANGLE';light.data.size=2.15;light.data.size_y=.80;light.data.color=(1,.98,.95)
# This area is an illumination proxy, not a physical white board outside window.
for prop in ['visible_camera','visible_glossy','visible_transmission']:
 assert hasattr(light,prop);setattr(light,prop,False)
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=4.0
data=bpy.data.lights.new('exterior_sun','SUN');data.energy=3.0;data.angle=.35;sun=bpy.data.objects.new('exterior_sun',data);sc.collection.objects.link(sun);sun.rotation_euler=Vector((.6,.25,-.75)).to_track_quat('-Z','Y').to_euler()
for power in [40,55,70]:
 light.data.energy=power;sc.render.filepath=str(out/f'lighting_rect_{power}.png');bpy.ops.render.render(write_still=True)
 assert snapshot()==accepted
 bpy.ops.wm.save_as_mainfile(filepath=str(out/f'lighting_rect_{power}.blend'))
(out/'rect_trials.json').write_text(json.dumps(dict(area_power_W=[40,55,70],world_strength=4.0,sun_energy=3.0,sun_angle_rad=.35,area_position=list(light.location),area_direction='Toward (.4,.5,.15), downward daylight hypothesis to match darker ceiling and bright bedding',material_state_unchanged=True,proxy_ray_visibility='Rectangular daylight proxy at lower window, just inside glazing. Hidden from camera/glossy/transmission rays, but directly lights room. Physical exterior stays visible. Approximation of incident daylight, not recovered physical luminaire.',scope='Fitted lighting hypothesis; no material edits'),indent=2));shutil.copyfile(R/'authoring/lighting_refine.py',out/'lighting_rect.py')
