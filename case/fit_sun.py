import bpy,sys,json
import numpy as np
from pathlib import Path
from mathutils import Vector
r=Path(__file__).resolve().parents[1];out=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else r/'evidence/shadow_fit';sc=bpy.context.scene;sc.render.resolution_x=1702;sc.render.resolution_y=1276;sc.render.resolution_percentage=25;sc.cycles.samples=2;sc.cycles.max_bounces=0;sc.cycles.use_denoising=False;sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=0
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 sc.cycles.device='GPU'
except:pass
def material(name,col):
 m=bpy.data.materials.new(name);m.use_nodes=True;ns=m.node_tree.nodes;ns.clear();d=ns.new('ShaderNodeBsdfDiffuse');d.inputs[0].default_value=(*col,1);o=ns.new('ShaderNodeOutputMaterial');m.node_tree.links.new(d.outputs[0],o.inputs['Surface']);return m
white=material('sun_probe_white',(1,1,1));black=material('sun_probe_black',(0,0,0))
for o in list(sc.objects):
 if o.type=='LIGHT':bpy.data.objects.remove(o,do_unlink=True);continue
 if o.type in ['MESH','CURVE']:
  o.data.materials.clear();o.data.materials.append(white if o.get('entity_id')=='floor' else black)
 if o.get('entity_id')=='exterior_backdrop':o.visible_shadow=False;o.visible_diffuse=False
sc.world.node_tree.nodes['Background'].inputs[1].default_value=0
sun=bpy.data.lights.new('sun_probe','SUN');sun.energy=3;sun.angle=.012;o=bpy.data.objects.new('sun_probe',sun);sc.collection.objects.link(o)
def read_mask(path):
 im=bpy.data.images.load(str(path),check_existing=False);a=np.array(im.pixels[:]).reshape(im.size[1],im.size[0],4)[:,:,0];bpy.data.images.remove(im);return a
target=read_mask(out/'target.png')>.5;roi=read_mask(out/'roi.png')>.5;results=[]
for dx in [-1.2,-.8,-.4,0,.4,.8,1.2]:
 for dz in [.8,1.1,1.4,1.8,2.2]:
  direction=Vector((dx,-1,-dz));o.rotation_euler=direction.to_track_quat('-Z','Y').to_euler();fn=f'sun_x{dx:+.1f}_z{dz:.1f}.png';sc.render.filepath=str(out/fn);bpy.ops.render.render(write_still=True);pred=read_mask(out/fn)>.1;pred&=roi;inter=(pred&target).sum();union=(pred|target).sum();iou=float(inter/max(1,union));results.append(dict(dx=dx,dy=-1,dz=-dz,iou=iou,intersection_pixels=int(inter),predicted_pixels=int(pred.sum()),target_pixels=int(target.sum()),image=fn));print('SHADOW',results[-1],flush=True)
results.sort(key=lambda x:-x['iou']);(out/'sun_fit_results.json').write_text(json.dumps(results,indent=2));print('BEST',results[:5])
