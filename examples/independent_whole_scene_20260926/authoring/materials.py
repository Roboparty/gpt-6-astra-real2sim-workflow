"""Author real scene materials, with source-scoped whole-object declarations."""
import bpy,sys,json,shutil,hashlib
from pathlib import Path
from collections import defaultdict
R=Path('/home/wqz/real2sim_whole_scene_20260926');sys.path.insert(0,str(R/'repo/workflow/r2s'))
state=json.loads((R/'case/runs/state.json').read_text());out=Path(state['stages']['agent_materials']['directory']);model=Path(state['stages']['agent_model']['directory']);obsdir=Path(state['stages']['agent_observe']['directory'])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(model/'model.blend'));sc=bpy.context.scene;scene=json.loads((model/'scene.json').read_text());obs=json.loads((obsdir/'observation.json').read_text());targets={t['entity']:t for t in obs['appearance_targets']}
out.joinpath('textures').mkdir(exist_ok=True)
for p in (R/'authoring/textures').iterdir():shutil.copyfile(p,out/'textures'/p.name)
for p in obsdir.glob('source_*.png'):shutil.copyfile(p,out/p.name)
def setup_uv(m,uvname='FabricUV'):
 nt=m.node_tree;n=nt.nodes.new('ShaderNodeUVMap');n.uv_map=uvname;return nt,n.outputs['UV']
def micro(m,amount=.00013):
 nt,uv=setup_uv(m);noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=750;noise.inputs['Roughness'].default_value=.55;nt.links.new(uv,noise.inputs['Vector']);bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.20;bump.inputs['Distance'].default_value=amount;nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],nt.nodes['Principled BSDF'].inputs['Normal']);return nt,uv
softmaterials=set();soft_prefixes=('bed_duvet','bed_pillow','bed_mattress','bed_sheet_','head_toy','pillow_toy','blind_panel')
rigid_materials={m.name for o in sc.objects if o.type in {'MESH','CURVE'} and not o.name.startswith(soft_prefixes) for m in o.data.materials if m};soft_copies={}
for o in sc.objects:
 if o.type!='MESH':continue
 soft=o.name.startswith(soft_prefixes)
 if soft:
  o['soft_surface']=True
  for slot in o.material_slots:
   if slot.material and slot.material.name in rigid_materials:
    name=slot.material.name
    if name not in soft_copies:soft_copies[name]=slot.material.copy();soft_copies[name].name=name+'_fabric_use'
    slot.material=soft_copies[name]
  if o.data.uv_layers:o.data.uv_layers.active.name='FabricUV'
  softmaterials.update(m.name for m in o.data.materials if m)
for name in softmaterials:
 micro(bpy.data.materials[name]);bpy.data.materials[name].node_tree.nodes['Principled BSDF'].inputs['Sheen Weight'].default_value=.12
cotton=bpy.data.materials['botanical_cotton'];nt,uv=setup_uv(cotton);tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(out/'textures/duvet_inferred_botanical.png'));tex.extension='EXTEND';nt.links.new(uv,tex.inputs['Vector']);nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
# Pillow occupies a physically smaller area in the same inferred cloth sheet.
for o in sc.objects:
 if o.name=='bed_pillow':
  for loop in o.data.uv_layers['FabricUV'].data:loop.uv=(loop.uv.x*.58+.2,loop.uv.y*.28+.50)
floor=bpy.data.objects['floor'];uv=floor.data.uv_layers.active;uv.name='FloorUV'
for loop in floor.data.loops:
 p=floor.matrix_world@floor.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=((p.x-scene['room']['x_min'])/(scene['room']['x_max']-scene['room']['x_min']),(p.y-scene['room']['y_min'])/(scene['room']['y_max']-scene['room']['y_min']))
m=bpy.data.materials['carpet_greytaupe'];nt,uvsource=setup_uv(m,'FloorUV');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(out/'textures/carpet_whole_inferred.png'));tex.extension='EXTEND';nt.links.new(uvsource,tex.inputs['Vector']);nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color']);bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.00035;bump.inputs['Strength'].default_value=.3;nt.links.new(tex.outputs['Color'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],nt.nodes['Principled BSDF'].inputs['Normal'])
# Low-amplitude directional grain, explicitly inferred. No shadows baked into wood.
m=bpy.data.materials['honey_wood'];nt=m.node_tree;tc=nt.nodes.new('ShaderNodeTexCoord');v=nt.nodes.new('ShaderNodeVectorMath');v.operation='MULTIPLY';v.inputs[1].default_value=(2,65,65);nt.links.new(tc.outputs['Object'],v.inputs[0]);n=nt.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=3;nt.links.new(v.outputs['Vector'],n.inputs['Vector']);ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.38,.225,.105,1);ramp.color_ramp.elements[1].color=(.57,.37,.18,1);nt.links.new(n.outputs['Fac'],ramp.inputs['Fac']);nt.links.new(ramp.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
axis_materials={}
for axis,scale in [('Y',(65,2,65)),('Z',(65,65,2))]:
 clone=m.copy();clone.name='honey_wood_'+axis;next(n for n in clone.node_tree.nodes if n.type=='VECT_MATH').inputs[1].default_value=scale;axis_materials[axis]=clone
for obj in sc.objects:
 axis='Y' if obj.name in ['bed_left_rail','bed_right_rail'] else 'Z' if obj.name in ['bed_left_foot','bed_right_foot','bed_left_head_leg','bed_right_head_leg'] else None
 if axis:
  for slot in obj.material_slots:
   if slot.material==m:slot.material=axis_materials[axis]
ceiling=bpy.data.materials['wall_paint'].copy();ceiling.name='ceiling_flat_tiles';bpy.data.objects['ceiling'].data.materials.clear();bpy.data.objects['ceiling'].data.materials.append(ceiling);nt=ceiling.node_tree;tc=nt.nodes.new('ShaderNodeTexCoord');brick=nt.nodes.new('ShaderNodeTexBrick');brick.offset=0;brick.inputs['Scale'].default_value=1;brick.inputs['Mortar Size'].default_value=.002;brick.inputs['Mortar Smooth'].default_value=.0005;brick.inputs['Brick Width'].default_value=.60;brick.inputs['Row Height'].default_value=.60;brick.inputs['Color1'].default_value=(.72,.74,.70,1);brick.inputs['Color2'].default_value=(.75,.76,.72,1);brick.inputs['Mortar'].default_value=(.42,.44,.40,1);nt.links.new(tc.outputs['Object'],brick.inputs['Vector']);nt.links.new(brick.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
bp=bpy.data.materials['board_glass'].node_tree.nodes['Principled BSDF'];bp.inputs['Base Color'].default_value=(.70,.75,.71,1);bp.inputs['Transmission Weight'].default_value=0;bp.inputs['Roughness'].default_value=.045;bp.inputs['Specular IOR Level'].default_value=.7;bp.inputs['Coat Weight'].default_value=1;bp.inputs['Coat Roughness'].default_value=.02
# Whole-board observation: sharper window reflection at left, diffuse haze at
# right. This restrained finish hypothesis changes roughness, never albedo.
nt=bpy.data.materials['board_glass'].node_tree;span=bpy.data.objects['wall_board'].dimensions.x;tc=nt.nodes.new('ShaderNodeTexCoord');add=nt.nodes.new('ShaderNodeVectorMath');add.operation='ADD';add.inputs[1].default_value=(span/2,0,0);nt.links.new(tc.outputs['Object'],add.inputs[0]);scale=nt.nodes.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(1/span,1,1);nt.links.new(add.outputs['Vector'],scale.inputs[0]);g=nt.nodes.new('ShaderNodeTexGradient');g.gradient_type='LINEAR';nt.links.new(scale.outputs['Vector'],g.inputs['Vector']);ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.003,.003,.003,1);ramp.color_ramp.elements[1].color=(.18,.18,.18,1)
for pos,value in [(.45,.006),(.65,.09)]:ramp.color_ramp.elements.new(pos).color=(value,value,value,1)
nt.links.new(g.outputs['Fac'],ramp.inputs['Fac']);nt.links.new(ramp.outputs['Color'],bp.inputs['Roughness']);nt.links.new(ramp.outputs['Color'],bp.inputs['Coat Roughness'])
bpy.data.materials['window_glass'].node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.015
from blender_metadata import synchronize
synchronize(scene,update=True);(out/'scene.json').write_text(json.dumps(scene,indent=2));bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'model.blend'))
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='CUDA';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='CUDA'
sc.cycles.device='GPU';sc.cycles.samples=40
from blender_appearance import neutral_view
neutral_view(out,scene,'material_neutral.png')
sc.render.filepath=str(out/'material_source_preview.png');bpy.ops.render.render(write_still=True)
# Calibrations enumerate actual visible assignments, including hidden-shell hypotheses.
groups=defaultdict(list)
for o in sc.objects:
 if o.type not in {'MESH','CURVE','SURFACE','FONT','META'} or o.hide_render:continue
 for m in o.data.materials:
  if m:groups[(o.get('entity_id',o.name),m.name,bool(o.get('soft_surface',False)))].append(o.name)
rows=[]
for (e,mname,soft),names in groups.items():
 m=bpy.data.materials[mname];p=m.node_tree.nodes['Principled BSDF'];textured=mname in softmaterials or mname in ['carpet_greytaupe','ceiling_flat_tiles','board_glass'] or mname.startswith('honey_wood');mapping='uv' if mname in softmaterials or mname=='carpet_greytaupe' else 'object' if mname.startswith('honey_wood') or mname in ['ceiling_flat_tiles','board_glass'] else 'none'
 scope=dict(source_kind='procedural' if textured else 'constant',application='whole_object' if textured else 'constant',mapping=mapping,uncertain_completion='Full appearance inferred from accepted full-object observation; hidden continuation restrained, no copied local source sample is expanded or tiled.')
 if mapping=='uv':scope['uv_map']='FloorUV' if e=='floor' else 'FabricUV'
 macro=targets[e]['appearance']['palette'] if e in targets else 'Neutral white hidden shell hypothesis'
 if mname=='botanical_cotton':macro='Dense fine sage/ivory botanical print across full cloth. Whole distribution newly drawn from observation; not the exact recovered print.'
 if mname=='carpet_greytaupe':macro='Full-floor alternating fibre direction in estimated 0.5m carpet tiles, moderate grey-taupe palette; no raised tile grid.'
 if mname=='ceiling_flat_tiles':macro='Flat 0.60m inferred tile linework with 0.002m tonal seams; uncertain seam depth is not modelled as relief.'
 if mname=='board_glass':macro='Pale opaque backing with dielectric clearcoat, representing the source glass-like white wall board; no painted reflection and no metallic reflectance.'
 row=dict(entity=e,material_names=[mname],objects=names,soft_surface=soft,material_class='metal' if p.inputs['Metallic'].default_value>.05 else 'dielectric',parameter_basis='Observed broad material class; roughness/IOR and microstructure are labelled plausible priors, not measured reflectometry.',pbr_parameters={mname:{k:('linked' if p.inputs[k].is_linked else float(p.inputs[k].default_value)) for k in ['Roughness','Metallic']}},texture_scale_m=.0015 if soft else .5 if e=='floor' else .025 if mname=='honey_wood' else 1,evidence=[f'source_{e}.png' if e in targets else 'material_neutral.png'],uncertainty='Reflectance-light ambiguity remains; final illumination fitted only after this material state accepted.',layers=dict(macro_pattern=macro,microstructure='Independent UV fine noise bump <=0.00013m' if soft else 'Fine inferred directional fibre/grain' if textured else 'Constant PBR finish, no synthetic noise detail',folds='Actual geometry; no fold shadow painted into albedo',illumination='Physical lighting and reflections; no source illumination baked into colour'),whole_object_evidence=[f'source_{e}.png' if e in targets else 'material_source_preview.png','material_neutral.png'],texture_scope=scope)
 if e not in targets:row['inferred_surface_reason']='Unobserved complete room enclosing face; appearance is a neutral painted wall hypothesis.'
 for key in ['IOR','Transmission Weight','Coat Weight','Coat Roughness','Specular IOR Level','Sheen Weight']:
  row['pbr_parameters'][mname][key]='linked' if p.inputs[key].is_linked else float(p.inputs[key].default_value)
 row['pbr_parameters'][mname]['Base Color']='linked' if p.inputs['Base Color'].is_linked else list(p.inputs['Base Color'].default_value)
 if mname.startswith('honey_wood'):
  axis=1 if mname.endswith('_Y') else 2 if mname.endswith('_Z') else 0;scale=[1/195]*3;scale[axis]=1/6;row['texture_scale_m']=scale;row['grain_direction_basis']='Member-local long axis; transverse/longitudinal characteristic scales follow actual Object-coordinate shader scaling, not measured grain.'
 if e=='floor':row['texture_scale_m']=[(scene['room']['x_max']-scene['room']['x_min'])/8,(scene['room']['y_max']-scene['room']['y_min'])/8];row['scale_basis']='Full-floor 8x8 inferred pattern; resulting physical tile axes are reported, not claimed measured 0.5m squares.'
 rows.append(row)
record=dict(appearance_source_sha256=obs['appearance_source']['sha256'],observation_sha256=sha(obsdir/'observation.json'),materials=rows,neutral_light_previews=['material_neutral.png'],geometry_freeze_sha256=sha(model/'model.blend'),limitations=['Print is inferred from whole cloth; not recovered product textile','No independent albedo/roughness measurements','No source photo pixels used as diffuse textures'])
(out/'material_calibration.json').write_text(json.dumps(record,indent=2))
shutil.copyfile(R/'authoring/materials.py',out/'materials.py');shutil.copyfile(R/'authoring/make_textures.py',out/'make_textures.py')
from blender_appearance import audit
audit(out)
print('MATERIAL_AUTHORING_READY_FOR_VISUAL_INSPECTION',str(out))
