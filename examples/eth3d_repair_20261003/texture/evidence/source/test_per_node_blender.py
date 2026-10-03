"""Actual saved-scene per-node audit fixtures plus unchanged frozen-asset audit; no visual acceptance."""
import bpy,copy,json,pathlib,sys,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--frozen',required=True);p.add_argument('--out',required=True);p.add_argument('--frozen-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);sys.path.insert(0,a.package);from blender_appearance import audit,vector_sources
O=pathlib.Path(a.out);O.mkdir(parents=True,exist_ok=True);sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();cases=[]
def active_textures(mat):
 reached=set()
 def visit(n):
  if n.name in reached:return
  reached.add(n.name)
  for s in n.inputs:
   for link in s.links:visit(link.from_node)
 for n in mat.node_tree.nodes:
  if n.type=='OUTPUT_MATERIAL' and n.is_active_output:visit(n)
 return [n for n in mat.node_tree.nodes if n.name in reached and n.type.startswith('TEX_') and n.type!='TEX_COORD']
# Adapt declarations only; soft classification and frozen model stay untouched.
frozen=pathlib.Path(a.frozen);before=sha(frozen);bpy.ops.wm.open_mainfile(filepath=str(frozen),load_ui=False,use_scripts=False);data=json.load(open(frozen.parent/'material_calibration.json'))
for row in data['materials']:
 maps={}
 for matname in row['material_names']:
  mat=bpy.data.materials[matname];nodes=active_textures(mat)
  if not nodes:continue
  specs={}
  for n in nodes:
   coords=vector_sources(n.inputs['Vector']) if 'Vector' in n.inputs else set();assert len(coords)==1,(matname,n.name,coords);kind,uv=next(iter(coords));spec={'mapping':kind}
   if kind=='uv':spec['uv_map']=uv or 'PhotoAtlas'
   specs[n.name]=spec
  maps[matname]=specs
 if maps:
  assert set(maps)==set(row['material_names']);row['texture_scope']['mapping']='per_node';row['texture_scope']['node_mappings']=maps;row['texture_scope'].pop('uv_map',None)
adapted=O/'frozen_per_node';adapted.mkdir(exist_ok=True);(adapted/'material_calibration.json').write_text(json.dumps(data,indent=2));result=audit(adapted);assert sha(frozen)==before;assert result['failures'] and all('Soft texture does not follow surface UV' in s for s in result['failures']),result['failures'];cases.append({'case':'frozen_graph','status':'rigid_mixed_layers_verified_soft_failures_retained','failures':len(result['failures']),'model_sha256':before})
if a.frozen_only:
 (O/'test_results.json').write_text(json.dumps({'cases':cases,'frozen_model_unchanged':True,'frozen_sha256':before,'implementation_sha256':sha(pathlib.Path(a.package)/'blender_appearance.py'),'status':'rigid_bindings_verified_soft_failures_retained'},indent=2));print('FROZEN_PER_NODE_AUDIT',len(result['failures']),'soft failures retained');sys.exit(0)
# Independent small fixture exercises positive and negative shader coordinate contracts.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.name='panel';obj['entity_id']='fixture';obj.data.uv_layers.active.name='FixtureUV';mat=bpy.data.materials.new('MixedMat');mat.use_nodes=True;obj.data.materials.append(mat);ns=mat.node_tree.nodes;ps=ns['Principled BSDF'];ps.inputs['Roughness'].default_value=.5
uv=ns.new('ShaderNodeUVMap');uv.name='UV';uv.uv_map='FixtureUV';tex=ns.new('ShaderNodeTexImage');tex.name='Photo';tex.image=bpy.data.images.new('test_image',width=8,height=8);tex.image.generated_color=(.3,.5,.7,1);tex.image.pack();tex.extension='EXTEND';geo=ns.new('ShaderNodeNewGeometry');noise=ns.new('ShaderNodeTexNoise');noise.name='Noise';mix=ns.new('ShaderNodeMixRGB');links=mat.node_tree.links;links.new(uv.outputs['UV'],tex.inputs['Vector']);links.new(geo.outputs['Position'],noise.inputs['Vector']);links.new(noise.outputs['Color'],mix.inputs[1]);links.new(tex.outputs['Color'],mix.inputs[2]);links.new(mix.outputs['Color'],ps.inputs['Base Color']);bpy.ops.wm.save_as_mainfile(filepath=str(O/'rigid_fixture.blend'))
row={'entity':'fixture','objects':['panel'],'material_names':['MixedMat'],'soft_surface':False,'material_class':'dielectric','pbr_parameters':{'MixedMat':{'Roughness':.5,'Metallic':0}},'texture_scope':{'application':'local','mapping':'per_node','node_mappings':{'MixedMat':{'Photo':{'mapping':'uv','uv_map':'FixtureUV'},'Noise':{'mapping':'world'}}}}}
def run(name,r,expect=None):
 d=O/name;d.mkdir(exist_ok=True);(d/'material_calibration.json').write_text(json.dumps({'materials':[r]},indent=2));fail=audit(d)['failures']
 if expect is None:assert not fail,(name,fail)
 else:assert any(expect in f for f in fail),(name,fail)
 cases.append({'case':name,'passed':True,'expected_failure_fragment':expect,'actual_failures':fail})
run('rigid_mixed_positive',row)
for name,mutate,expect in [('missing_node',lambda x:x['texture_scope']['node_mappings']['MixedMat'].pop('Noise'),'differ from active nodes'),('extra_node',lambda x:x['texture_scope']['node_mappings']['MixedMat'].update(Ghost={'mapping':'world'}),'differ from active nodes'),('wrong_uv',lambda x:x['texture_scope']['node_mappings']['MixedMat']['Photo'].update(uv_map='WrongUV'),'coordinates'),('wrong_world',lambda x:x['texture_scope']['node_mappings']['MixedMat']['Noise'].update(mapping='object'),'coordinates'),('missing_material',lambda x:x['texture_scope'].update(node_mappings={}), 'every material'),('extra_material',lambda x:x['texture_scope']['node_mappings'].update(Ghost={}), 'every material'),('soft_world_rejected',lambda x:x.update(soft_surface=True),'Soft texture'),('extra_node_field',lambda x:x['texture_scope']['node_mappings']['MixedMat']['Noise'].update(uv_map='FixtureUV'),'fields differ')]:
 bad=copy.deepcopy(row);mutate(bad);run(name,bad,expect)
# Soft surfaces pass only when every actual active texture follows the named UV layer.
links.new(uv.outputs['UV'],noise.inputs['Vector']);soft=copy.deepcopy(row);soft['soft_surface']=True;soft['texture_scope']['node_mappings']['MixedMat']['Noise']={'mapping':'uv','uv_map':'FixtureUV'};bpy.ops.wm.save_as_mainfile(filepath=str(O/'soft_uv_fixture.blend'));run('soft_uv_positive',soft)
# Implicit UV must bind active_render, not the unrelated editor-active layer.
other=obj.data.uv_layers.new(name='OtherUV');obj.data.uv_layers.active_index=0;other.active_render=True
run('explicit_uv_ignores_editor_render_selection',soft)
uv.uv_map='';run('empty_uvmap_uses_render_layer',soft,'render-active');uv.uv_map='FixtureUV'
coord=ns.new('ShaderNodeTexCoord');links.new(coord.outputs['UV'],tex.inputs['Vector']);run('texcoord_implicit_wrong_render_layer',soft,'render-active')
correct=copy.deepcopy(soft);correct['texture_scope']['node_mappings']['MixedMat']['Photo']['uv_map']='OtherUV';run('per_node_two_named_uvs_positive',correct)
links.new(uv.outputs['UV'],tex.inputs['Vector']);ns.remove(coord)
# Active shader groups remain unsupported, even if texture declarations look complete.
group=bpy.data.node_groups.new('UnsupportedGroup','ShaderNodeTree');group.interface.new_socket(name='Shader',in_out='OUTPUT',socket_type='NodeSocketShader');gp=group.nodes.new('ShaderNodeBsdfPrincipled');go=group.nodes.new('NodeGroupOutput');group.links.new(gp.outputs[0],go.inputs[0]);gn=ns.new('ShaderNodeGroup');gn.node_tree=group;links.new(gn.outputs[0],ns['Material Output'].inputs['Surface']);bpy.ops.wm.save_as_mainfile(filepath=str(O/'group_fixture.blend'));run('active_group_rejected',row,'Shader group requires')
assert sha(frozen)==before;(O/'test_results.json').write_text(json.dumps({'cases':cases,'frozen_model_unchanged':True,'frozen_sha256':before,'implementation_sha256':sha(pathlib.Path(a.package)/'blender_appearance.py'),'status':'passed'},indent=2));print('PASS_PER_NODE_ACTUAL_BLENDER',len(cases),flush=True)
