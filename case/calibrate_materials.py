import os
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];args=sys.argv[sys.argv.index('--')+1:];out=Path(args[0]);out.mkdir(parents=True,exist_ok=True)
def geom_hash():
 data=[]
 for o in sorted(bpy.context.scene.objects,key=lambda o:o.name):
  if o.type not in ['MESH','CURVE','CAMERA']:continue
  item=[o.name,o.type,list(sum((list(row) for row in o.matrix_world),[]))]
  if o.type=='MESH':item.append([list(v.co) for v in o.data.vertices]);item.append([list(p.vertices) for p in o.data.polygons])
  if o.type=='CURVE':item.append([[list(p.co) for p in sp.bezier_points] for sp in o.data.splines])
  if o.type=='CAMERA':item.extend([o.data.lens,o.data.shift_x,o.data.shift_y])
  data.append(item)
 return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
before=geom_hash()
for material in bpy.data.materials:
 if not material.use_nodes:continue
 ns=material.node_tree.nodes;lk=material.node_tree.links
 for noise in list(ns):
  if noise.type!='TEX_NOISE':continue
  tc=ns.new('ShaderNodeTexCoord');lk.new(tc.outputs['Object'],noise.inputs['Vector'])
  if 'woven' in material.name:noise.inputs['Scale'].default_value=250
for i in range(2):
 m=bpy.data.materials['carpet_tile_'+str(i)];ns=m.node_tree.nodes;lk=m.node_tree.links;p=ns['Principled BSDF']
 for link in list(lk):
  if link.to_node==p:lk.remove(link)
 tc=ns.new('ShaderNodeTexCoord');scale=ns.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=2;lk.new(tc.outputs['Object'],scale.inputs[0]);add=ns.new('ShaderNodeVectorMath');add.operation='ADD';add.inputs[1].default_value=(.5,.5,0);lk.new(scale.outputs[0],add.inputs[0]);tex=ns.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/f'evidence/carpet_calibrated_{i}.png'));lk.new(add.outputs[0],tex.inputs['Vector']);lk.new(tex.outputs['Color'],p.inputs['Base Color']);b=ns.new('ShaderNodeBump');b.inputs['Strength'].default_value=.33;b.inputs['Distance'].default_value=.0008;lk.new(tex.outputs['Color'],b.inputs['Height']);lk.new(b.outputs[0],p.inputs['Normal']);p.inputs['Roughness'].default_value=.96
# Cabinet powder coat receives its own measured-from-photo appearance prior, not the window frame material.
cm=bpy.data.materials['black_powdercoat'].copy();cm.name='cabinet_charcoal_powdercoat';cm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.010,.011,.0104,1);cm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.65
bpy.data.materials['roller_blind_woven'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.133,.124,.085,1)
for o in bpy.data.objects:
 if o.get('entity_id')=='cabinet' and o.type in ['MESH','CURVE']:
  for slot in o.material_slots:
   if slot.material and slot.material.name=='black_powdercoat':slot.material=cm
after=geom_hash();assert before==after,'Material edit changed geometry/camera'
sc=bpy.context.scene;sc.render.resolution_percentage=100;sc.cycles.samples=48;sc.render.filepath=str(out/'neutral_materials.png')
try:
 p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='CUDA';p.get_devices()
 for d in p.devices:d.use=d.type=='CUDA'
 sc.cycles.device='CPU' if os.environ.get('R2S_CPU')=='1' else 'GPU'
except:pass
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'));bpy.ops.render.render(write_still=True)
(out/'geometry_lock.json').write_text(json.dumps(dict(before=before,after=after,identical=True),indent=2))
records=[]
for m in bpy.data.materials:
 if not m.use_nodes:continue
 p=m.node_tree.nodes.get('Principled BSDF')
 if not p:continue
 noises=[n for n in m.node_tree.nodes if n.type=='TEX_NOISE'];scale=.5 if 'carpet_tile' in m.name else 1/float(noises[0].inputs['Scale'].default_value) if noises else 0
 records.append(dict(entity=m.name,pbr_parameters={k:list(p.inputs[k].default_value) if k=='Base Color' else float(p.inputs[k].default_value) for k in ['Base Color','Roughness','Metallic','Transmission Weight']},texture_scale_m=scale,evidence=['original source appearance and enlarged material regions','neutral_materials.png'],uncertainty='appearance estimate; reflectance not independently measured; procedural texture world coordinates; scale 0 means no texture, constant PBR color'))
(out/'material_calibration.json').write_text(json.dumps(dict(materials=records,neutral_light_previews=['neutral_materials.png'],geometry_lock_sha256=before,texture_provenance='procedural carpet seed 2209, tile width 0.50m, alternating orientation; outdoor-only source background separately labelled'),indent=2))
